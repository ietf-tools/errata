# Copyright The IETF Trust 2025-2026, All Rights Reserved

import datetime
import uuid
from collections.abc import Iterable
from email.policy import EmailPolicy

from django import forms
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from errata_auth.utils import current_area
from errata_project.mail import EmailMessage, make_message_id


class Name(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=255)
    desc = models.TextField(blank=True)
    used = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Erratum(models.Model):
    """
    Model representing an erratum.
    """

    rfc_number = models.PositiveIntegerField()
    rfc_metadata = models.ForeignKey(
        "RfcMetadata",
        related_name="erratum",
        on_delete=models.PROTECT,
        null=False,
    )
    status = models.ForeignKey(
        "Status",
        on_delete=models.PROTECT,
        default="reported",
        related_name="erratum",
        db_column="status_slug",
    )
    erratum_type = models.ForeignKey(
        "ErratumType",
        on_delete=models.PROTECT,
        related_name="erratum",
        db_column="erratum_type_slug",
        null=True,
        blank=True,
    )
    section = models.TextField(blank=True)
    orig_text = models.TextField(blank=True)
    corrected_text = models.TextField(blank=True)
    submitter_name = models.CharField(max_length=80, blank=True)
    submitter_email = models.EmailField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verifier_name = models.CharField(max_length=80, blank=True, null=True)
    verifier_email = models.EmailField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    # updated_at has additional behavior in self.save
    updated_at = models.DateTimeField(null=True, blank=True)
    formats = ArrayField(
        models.CharField(
            max_length=10, choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")]
        ),
        default=list,
        blank=True,
        help_text="A list of formats. Possible values: 'HTML', 'PDF', and 'TXT'.",
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"Erratum {self.id} for RFC {self.rfc_number}"

    def save(self, *args, **kwargs):
        """Save, setting updated_at to now unless told to keep the given value.

        Setting _take_given_updated_at_value allows an updated_at that is not
        now, or even None.
        """
        if not getattr(self, "_take_given_updated_at_value", False):
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)
        DirtyBits.objects.filter(slug=DirtyBits.Slugs.ERRATA_JSON).update(
            dirty_time=datetime.datetime.now(datetime.UTC)
        )
        # Keeping this as proof_of_concept, but as the app is currently written,
        # updated_at will change on every save in production, so the extra calculation
        # here is unnecessary.
        #
        # h = self.history.last()
        # if h.prev_record is None:
        #     mark_errata_json_dirty = True
        # else:
        #     delta = h.diff_against(h.prev_record)
        #     fields = [change.field for change in delta.changes]
        #     if (
        #         len(
        #             set(fields).intersection(
        #                 set(
        #                     [
        #                         "status",
        #                         "erratum_type",
        #                         "section",
        #                         "orig_text",
        #                         "corrected_text",
        #                         "notes",
        #                         "submitted_at",
        #                         "submitter_name",
        #                         "verifier_name",
        #                         "updated_at",
        #                     ]
        #                 )
        #             )
        #         )
        #         > 0
        #     ):
        #         mark_errata_json_dirty = True
        #     if mark_errata_json_dirty:
        #         DirtyBits.objects.filter(slug=DirtyBits.Slugs.ERRATA_JSON).update(
        #             dirty_time=datetime.datetime.now(datetime.UTC)
        #         )

    class Meta:
        verbose_name_plural = "Errata"


class Status(Name):
    class Meta:
        verbose_name_plural = "Statuses"

    pass


class ErratumType(Name):
    pass


class AddressListField(models.CharField):
    def from_db_value(self, value, expression, connection):
        return self._parse_header_value(value)

    def get_prep_value(self, value: str | Iterable[str]):
        """Convert python value to query value"""
        # Parse the value to validate it, then convert to a string for the CharField.
        # A bit circular, but guarantees that only valid addresses are saved.
        if isinstance(value, str):
            parsed = self._parse_header_value(value)
        else:
            parsed = self._parse_header_value(",".join(value))
        return ",".join(parsed)

    def to_python(self, value: str | Iterable[str]):
        if isinstance(value, str):
            return self._parse_header_value(value)
        return self._parse_header_value(",".join(str(item) for item in value))

    def formfield(self, **kwargs):
        # n.b., the SimpleArrayField is intended for use with postgres ArrayField
        # but it works cleanly with this field. We are not using a special postgres-
        # only field in the model.
        defaults = {"form_class": SimpleArrayField, "base_field": forms.CharField()}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    @staticmethod
    def _parse_header_value(value: str):
        policy = EmailPolicy(utf8=True)  # allow direct UTF-8 in addresses
        header = policy.header_factory("To", value)
        if len(header.defects) > 0:
            raise ValidationError("; ".join(str(defect) for defect in header.defects))
        return [str(addr) for addr in header.addresses]


class RfcMetadata(models.Model):
    """
    Model representing metadata for RFCs.
    """

    rfc_number = models.PositiveIntegerField(primary_key=True)
    draft_name = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=512)
    author_names = models.CharField(max_length=1024, blank=True)
    author_emails = AddressListField(blank=True, max_length=2550)
    shepherd_email = models.EmailField(max_length=255, blank=True)
    doc_ad_email = models.EmailField(max_length=255, blank=True)
    area_ad_emails = AddressListField(blank=True, max_length=1020)
    std_level = models.CharField(max_length=40, blank=True)
    publication_year = models.PositiveIntegerField()
    publication_month = models.PositiveIntegerField()
    group_acronym = models.CharField(max_length=40, blank=True)
    group_name = models.CharField(max_length=255, blank=True)
    group_list_email = models.EmailField(max_length=64, blank=True)
    area_acronym = models.CharField(max_length=40, blank=True)
    stream = models.CharField(max_length=40, blank=True)
    obsoleted_by = models.CharField(max_length=1024, blank=True)
    updated_by = models.CharField(max_length=1024, blank=True)
    # Where this RFC's errata go, worked out by resolve_routing on every save.
    resolved_area = models.CharField(max_length=40, blank=True, editable=False)
    resolved_group_acronym = models.CharField(max_length=40, blank=True, editable=False)
    resolved_group_list_email = models.EmailField(
        max_length=64, blank=True, editable=False
    )

    def __str__(self):
        return f"RFC {self.rfc_number}: {self.title}"

    def save(self, *args, **kwargs):
        self.resolve_routing()
        super().save(*args, **kwargs)

    def resolve_routing(self, replacements=None, assigned_area=None):
        """Set the area, group and list address used for this RFC's errata.

        If the RFC's group has been replaced, the group and list address are
        the replacement's, following a chain of replacements to its end.
        Otherwise they are the datatracker's.

        The area is the first of:

        * the RFC's area assignment,
        * for IETF stream RFCs, the area of the group that replaced the RFC's
          group, if the GroupReplacement names one,
        * the area the datatracker reports,

        with a closed area replaced by the current area that took it over.

        ``replacements`` maps group acronyms to their GroupReplacement, and
        ``assigned_area`` is the RFC's area assignment. They are read from the
        database if not given.
        """
        if replacements is None:
            replacements = GroupReplacement.objects.in_bulk(field_name="group")
        group = self.group_acronym
        list_email = self.group_list_email
        replacement_area = ""
        seen = {group}
        while group in replacements:
            replacement = replacements[group]
            group = replacement.replacement_group
            list_email = replacement.replacement_list_email
            replacement_area = replacement.replacement_area or replacement_area
            if group in seen:
                break  # GroupReplacement.clean refuses loops; don't hang on one
            seen.add(group)
        area = self.assigned_area if assigned_area is None else assigned_area
        if area == "" and self.stream == "ietf":
            area = replacement_area
        self.resolved_area = current_area(area or self.area_acronym)
        self.resolved_group_acronym = group
        self.resolved_group_list_email = list_email

    def display_source(self):
        if self.stream == "ise":
            result = "INDEPENDENT"
        elif self.stream == "iab":
            result = "IAB"
        elif self.stream == "ietf" and (
            self.group_acronym in ["none", "gen"] or self.area_acronym == ""
        ):
            result = "IETF - NON WORKING GROUP"
        elif self.group_acronym != "none":
            result = self.group_acronym
            if self.stream == "ietf" and self.area_acronym != "":
                result += f" ({self.area_acronym})"
            elif self.stream != "":
                result += f" ({self.stream})"
        # This is intentionally separated from the first branches on stream
        elif self.stream != "":
            if self.stream == "legacy":
                result = "Legacy"
            else:
                result = self.stream.upper()
        else:
            result = ""
        return result

    def display_source_with_assignment(self):
        result = self.display_source()
        if self.assigned_area != "":
            result += f" ({self.assigned_area})"
        if self.has_replacement_group():
            result += f" (replaced by {self.resolved_group_acronym})"
        return result

    def has_replacement_group(self):
        return self.resolved_group_acronym != self.group_acronym

    def resolved_routing(self):
        return (
            self.resolved_area,
            self.resolved_group_acronym,
            self.resolved_group_list_email,
        )

    @property
    def assigned_area(self):
        """The area of this RFC's AreaAssignment, or "" if it has none."""
        try:
            return self.area_assignment.area
        except AreaAssignment.DoesNotExist:
            return ""


class AreaAssignment(models.Model):
    """An RFC whose errata are handled by an area other than its group's.

    The assignment takes precedence over the area the datatracker reports. It
    is set at the RPC's request. RfcMetadata is a cache of information from
    the datatracker, so assignments are kept in their own table. The link to
    RfcMetadata has no database constraint and isn't deleted with it, so
    assignments survive RfcMetadata being wiped and rebuilt.
    """

    rfc_metadata = models.OneToOneField(
        RfcMetadata,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        db_column="rfc_number",
        related_name="area_assignment",
    )
    area = models.CharField(max_length=40)
    history = HistoricalRecords()

    class Meta:
        ordering = ["rfc_metadata"]

    def __str__(self):
        return f"RFC {self.rfc_metadata_id}: {self.area}"

    def save(self, *args, **kwargs):
        previous_rfc_number = (
            AreaAssignment.objects.filter(pk=self.pk)
            .values_list("rfc_metadata_id", flat=True)
            .first()
        )
        super().save(*args, **kwargs)
        refresh_rfc_routing({previous_rfc_number, self.rfc_metadata_id})

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        refresh_rfc_routing({self.rfc_metadata_id})
        return result


def refresh_rfc_routing(rfc_numbers):
    """Re-resolve the routing of the given RFCs, for those that have metadata."""
    for metadata in RfcMetadata.objects.filter(rfc_number__in=rfc_numbers - {None}):
        metadata.save()


class GroupReplacement(models.Model):
    """A group whose RFCs' errata go to the group that replaced it.

    For example, errata on ippm and bmwg RFCs go to bpm. The replacement's
    list address, and optionally its area, are stored rather than looked up:
    the replacement may not have published an RFC to take them from, and its
    list need not be at ietf.org. Saving or deleting a replacement updates the
    resolved routing of the RFCs it affects.
    """

    group = models.CharField(max_length=40, unique=True)
    replacement_group = models.CharField(max_length=40)
    replacement_list_email = models.EmailField(max_length=64)
    replacement_area = models.CharField(
        max_length=40,
        blank=True,
        help_text="Leave blank to keep the area of each RFC.",
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["group"]

    def __str__(self):
        return f"{self.group} replaced by {self.replacement_group}"

    def clean(self):
        if self.group == self.replacement_group:
            raise ValidationError(
                {"replacement_group": "A group can't be replaced by itself."}
            )
        replaced_by = dict(
            GroupReplacement.objects.exclude(pk=self.pk).values_list(
                "group", "replacement_group"
            )
        )
        replaced_by[self.group] = self.replacement_group
        chain = [self.group]
        while chain[-1] in replaced_by:
            chain.append(replaced_by[chain[-1]])
            if chain[-1] == self.group:
                raise ValidationError(
                    {
                        "replacement_group": "This would make a loop of "
                        "replacements: " + " → ".join(chain)
                    }
                )

    def save(self, *args, **kwargs):
        previous_group = (
            GroupReplacement.objects.filter(pk=self.pk)
            .values_list("group", flat=True)
            .first()
        )
        super().save(*args, **kwargs)
        refresh_group_routing({self.group, previous_group})

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        refresh_group_routing({self.group})
        return result


def refresh_group_routing(changed_groups):
    """Re-resolve the routing of RFCs whose group replacements may have changed.

    Through a chain of replacements, a change to one group can affect RFCs of
    any group that has a replacement, so those are refreshed too.
    """
    replacements = GroupReplacement.objects.in_bulk(field_name="group")
    groups = (set(changed_groups) | set(replacements)) - {None}
    changed = []
    for metadata in RfcMetadata.objects.filter(group_acronym__in=groups).select_related(
        "area_assignment"
    ):
        before = metadata.resolved_routing()
        metadata.resolve_routing(replacements)
        if metadata.resolved_routing() != before:
            changed.append(metadata)
    RfcMetadata.objects.bulk_update(
        changed,
        ["resolved_area", "resolved_group_acronym", "resolved_group_list_email"],
    )


class StagedErratumStatus(models.TextChoices):
    INCOMPLETE = "incomplete", "Incomplete"
    SUBMITTED = "submitted", "Submitted for Screening"


def get_default_staged_erratum_formats():
    return ["TXT"]


class StagedErratum(models.Model):
    """
    A place for holding errata reports for Erratum entry and RPC screening.

    Held as a separate table to make it less likely that
    unscreened errata leak through the UI or APIs.

    Entry objects that aren't submitted for screening are expected
    to be periodically cleaned by a scheduled task (such as daily
    cleaning of such entries more than 7 days old).

    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_status = models.CharField(
        max_length=20,
        choices=StagedErratumStatus.choices,
        default=StagedErratumStatus.INCOMPLETE,
    )
    rfc_number = models.PositiveIntegerField()
    rfc_metadata = models.ForeignKey(
        "RfcMetadata",
        related_name="stagederratum",
        on_delete=models.PROTECT,
        null=False,
    )
    section = models.TextField(blank=True)
    orig_text = models.TextField(blank=True)
    corrected_text = models.TextField(blank=True)
    submitter_name = models.CharField(max_length=80, blank=True)
    submitter_email = models.EmailField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    formats = ArrayField(
        models.CharField(
            max_length=10, choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")]
        ),
        default=get_default_staged_erratum_formats,
        blank=True,
        help_text="A list of formats. Possible values: 'HTML', 'PDF', and 'TXT'.",
    )

    def __str__(self):
        return f"StagedErratum {self.id} for RFC {self.rfc_number}"

    class Meta:
        verbose_name_plural = "StagedErrata"


class MailMessage(models.Model):
    """Email message to be delivered"""

    erratum = models.ForeignKey(
        "Erratum",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Erratum to which this message relates",
    )
    to = AddressListField(blank=False, max_length=2550)
    cc = AddressListField(blank=True, max_length=2550)
    subject = models.CharField(max_length=1000)
    body = models.TextField()
    message_id = models.CharField(default=make_message_id, max_length=255)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent = models.BooleanField(default=False)
    sender = models.ForeignKey(
        "errata_auth.User",
        on_delete=models.PROTECT,
    )

    def as_emailmessage(self):
        """Instantiate an EmailMessage for delivery"""
        # Horrible hack for content-type - if it has to be touched,
        # refactor the class to make content-type explicit.

        msg = EmailMessage(
            subject=self.subject,
            body=self.body,
            to=self.to,
            cc=self.cc,
            headers={"message-id": self.message_id},
        )

        if self.body.strip().startswith("<html"):
            msg.content_subtype = "html"

        return msg


class DirtyBits(models.Model):
    """A weak semaphore mechanism for coordination with celery beat tasks

    Web workers will set the "dirty_time" value for a given dirtybit slug.
    Celery workers will do work if "processed_time" < "dirty_time" and update
    "processed_time".
    """

    class Slugs(models.TextChoices):
        ERRATA_JSON = "errata_json", "Errata JSON"

    slug = models.CharField(max_length=40, blank=False, choices=Slugs, unique=True)
    dirty_time = models.DateTimeField(null=True, blank=True)
    processed_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "dirty bits"
