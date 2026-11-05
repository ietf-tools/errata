# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations
from django.utils import timezone

# (group, replacement group, replacement list, replacement area, reason)
REPLACEMENTS = [
    ("bmwg", "bpm", "bpm@ietf.org", "ops", "Data migration for #92"),
    ("ippm", "bpm", "bpm@ietf.org", "ops", "Data migration for #92"),
    (
        "httpstate",
        "httpbis",
        "ietf-http-wg@w3.org",
        "wit",
        "Data migration for #100",
    ),
    ("sip", "sipcore", "sipcore@ietf.org", "art", "Data migration"),
    ("sipping", "sipcore", "sipcore@ietf.org", "art", "Data migration"),
]

# errata_auth.utils.SUCCESSOR_AREAS as of this migration, for reversing.
CLOSED_AREA_SUCCESSORS = {"app": "art", "rai": "art", "tsv": "wit"}


def forward(apps, schema_editor):
    GroupReplacement = apps.get_model("errata", "GroupReplacement")
    HistoricalGroupReplacement = apps.get_model("errata", "HistoricalGroupReplacement")
    RfcMetadata = apps.get_model("errata", "RfcMetadata")
    now = timezone.now()
    for group, replacement_group, list_email, area, reason in REPLACEMENTS:
        replacement = GroupReplacement.objects.create(
            group=group,
            replacement_group=replacement_group,
            replacement_list_email=list_email,
            replacement_area=area,
        )
        HistoricalGroupReplacement.objects.create(
            id=replacement.id,
            group=group,
            replacement_group=replacement_group,
            replacement_list_email=list_email,
            replacement_area=area,
            history_date=now,
            history_type="+",
            history_change_reason=reason,
        )
        # Historical models don't run GroupReplacement.save, which would
        # re-resolve these RFCs. None of the replacement groups is itself
        # replaced, so the routing is just the replacement's.
        rfcs = RfcMetadata.objects.filter(group_acronym=group)
        rfcs.update(
            resolved_group_acronym=replacement_group,
            resolved_group_list_email=list_email,
        )
        # The area applies to IETF stream RFCs, unless they have an assignment.
        rfcs.filter(stream="ietf", area_assignment__isnull=True).update(
            resolved_area=area
        )


def reverse(apps, schema_editor):
    GroupReplacement = apps.get_model("errata", "GroupReplacement")
    HistoricalGroupReplacement = apps.get_model("errata", "HistoricalGroupReplacement")
    RfcMetadata = apps.get_model("errata", "RfcMetadata")
    groups = [group for group, *_ in REPLACEMENTS]
    HistoricalGroupReplacement.objects.filter(group__in=groups).delete()
    GroupReplacement.objects.filter(group__in=groups).delete()
    rows = list(
        RfcMetadata.objects.filter(group_acronym__in=groups).select_related(
            "area_assignment"
        )
    )
    for metadata in rows:
        try:
            area = metadata.area_assignment.area
        except metadata._meta.model.area_assignment.RelatedObjectDoesNotExist:
            area = metadata.area_acronym
        metadata.resolved_area = CLOSED_AREA_SUCCESSORS.get(area, area)
        metadata.resolved_group_acronym = metadata.group_acronym
        metadata.resolved_group_list_email = metadata.group_list_email
    RfcMetadata.objects.bulk_update(
        rows,
        ["resolved_area", "resolved_group_acronym", "resolved_group_list_email"],
    )


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0011_groupreplacement"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
