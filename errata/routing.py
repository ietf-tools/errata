# Copyright The IETF Trust 2026, All Rights Reserved
"""Preview how a change to area assignments or group replacements reroutes errata."""

from dataclasses import dataclass, field

from .models import Erratum, GroupReplacement, RfcMetadata


@dataclass(frozen=True)
class Routing:
    area_assignment: str
    area: str
    group: str
    list_email: str


@dataclass
class RoutingChange:
    before: Routing
    after: Routing
    rfc_numbers: list = field(default_factory=list)


@dataclass
class RoutingPreview:
    changes: list
    errata_count: int
    reported_count: int

    @property
    def rfc_count(self):
        return sum(len(change.rfc_numbers) for change in self.changes)


def _routing(metadata, assigned_area):
    return Routing(
        area_assignment=assigned_area,
        area=metadata.resolved_area,
        group=metadata.resolved_group_acronym,
        list_email=metadata.resolved_group_list_email,
    )


def _preview(rfcs, change_rfc):
    """Apply change_rfc to each RFC in memory and collect what would change.

    change_rfc returns the RFC's assigned area after the change. Nothing is
    saved.
    """
    changes = {}
    for metadata in rfcs.select_related("area_assignment").order_by("rfc_number"):
        before = _routing(metadata, metadata.assigned_area)
        assigned_area = change_rfc(metadata)
        after = _routing(metadata, assigned_area)
        if after != before:
            change = changes.setdefault((before, after), RoutingChange(before, after))
            change.rfc_numbers.append(metadata.rfc_number)
    rfc_numbers = [n for change in changes.values() for n in change.rfc_numbers]
    errata = Erratum.objects.filter(rfc_number__in=rfc_numbers)
    return RoutingPreview(
        changes=sorted(changes.values(), key=lambda c: -len(c.rfc_numbers)),
        errata_count=errata.count(),
        reported_count=errata.filter(status_id="reported").count(),
    )


def preview_area_assignment(rfc_number, area):
    """Preview setting an RFC's area assignment to ``area``, or "" to remove it."""
    replacements = GroupReplacement.objects.in_bulk(field_name="group")

    def change_rfc(metadata):
        metadata.resolve_routing(replacements, assigned_area=area)
        return area

    return _preview(RfcMetadata.objects.filter(rfc_number=rfc_number), change_rfc)


def preview_group_replacement(replacement, previous_group=None, delete=False):
    """Preview saving, or with ``delete``, deleting an unsaved GroupReplacement.

    ``previous_group`` is the group the replacement had before an edit.
    """
    replacements = GroupReplacement.objects.in_bulk(field_name="group")
    affected = set(replacements) | {replacement.group, previous_group}
    replacements.pop(previous_group, None)
    replacements.pop(replacement.group, None)
    if not delete:
        replacements[replacement.group] = replacement

    def change_rfc(metadata):
        metadata.resolve_routing(replacements)
        return metadata.assigned_area

    return _preview(
        RfcMetadata.objects.filter(group_acronym__in=affected - {None}), change_rfc
    )
