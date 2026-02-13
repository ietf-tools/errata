# Copyright The IETF Trust 2025-2026, All Rights Reserved
import uuid
from collections.abc import Iterable
from email.policy import EmailPolicy

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.forms import SimpleArrayField
from django.db import models
from django.utils import timezone

from errata_project.mail import make_message_id, EmailMessage


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


class AutoDateTimeField(models.DateTimeField):
    def pre_save(self, model_instance, add):
        value = getattr(model_instance, self.attname)
        if value is None:
            value = timezone.now()
        return value


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
    updated_at = AutoDateTimeField()
    formats = ArrayField(
        models.CharField(
            max_length=10, choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")]
        ),
        default=list,
        blank=True,
        help_text="A list of formats. Possible values: 'HTML', 'PDF', and 'TXT'.",
    )

    def __str__(self):
        return f"Erratum {self.id} for RFC {self.rfc_number}"

    class Meta:
        verbose_name_plural = "Errata"


class Status(Name):
    class Meta:
        verbose_name_plural = "Statuses"

    pass


class ErratumType(Name):
    pass


class Log(models.Model):
    """
    Model representing the log of changes to errata objects.

    If designed from scratch, this would be SimpleHistory instead.
    """

    erratum = models.ForeignKey(
        "Erratum", on_delete=models.PROTECT, related_name="logs_erratum"
    )
    verifier_name = models.CharField(max_length=80, blank=True, null=True)
    verifier_email = models.EmailField(max_length=120, blank=True, null=True)
    status = models.ForeignKey(
        "Status",
        on_delete=models.PROTECT,
        related_name="logs_status",
        db_column="status_slug",
    )
    erratum_type = models.ForeignKey(
        "ErratumType",
        on_delete=models.PROTECT,
        related_name="logs_erratum_type",
        db_column="erratum_type_slug",
    )
    editor_email = models.EmailField(max_length=120, blank=True)
    section = models.TextField(blank=True)
    orig_text = models.TextField(blank=True)
    corrected_text = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Log {self.id} for Erratum {self.erratum_id}"


class RfcMetadata(models.Model):
    """
    Model representing metadata for RFCs.
    """

    rfc_number = models.PositiveIntegerField(primary_key=True)
    title = models.CharField(max_length=512)
    publication_year = models.PositiveIntegerField()
    publication_month = models.PositiveIntegerField()
    group_acronym = models.CharField(max_length=40, blank=True)
    area_acronym = models.CharField(max_length=40, blank=True)
    stream = models.CharField(max_length=40, blank=True)
    area_assignment = models.CharField(max_length=40, blank=True)
    obsoleted_by = models.CharField(max_length=160, blank=True)

    def __str__(self):
        return f"RFC {self.rfc_number}: {self.title}"

    def display_source(self):
        if self.group_acronym != "":
            result = self.group_acronym
            if self.area_acronym != "":
                result += f" ({self.area_acronym})"
            elif self.stream != "":
                result += f" ({self.stream})"
        elif self.area_acronym != "":
            result = f"{self.area_acronym} ({self.stream})"
        elif self.stream != "":
            if (
                self.stream == "ietf"
                and self.group_acronym == ""
                and self.area_acronym == ""
            ):
                result = "IETF - NON WORKING GROUP"
            else:
                result = self.stream
        else:
            result = ""
        return result

    def display_source_with_assignment(self):
        result = self.display_source()
        if self.area_assignment != "":
            result += f" ({self.area_assignment})"
        return result


class StagedErratumStatus(models.TextChoices):
    INCOMPLETE = "incomplete", "Incomplete"
    SUBMITTED = "submitted", "Submitted for Screening"


def get_default_staged_erratum_formats():
    return ["TXT"]


class StagedErratum(models.Model):
    """
    A place for holding errata reports for Erratum entry and RPC screening.

    Held as a separate table to make it less likely that
    unscreened erratum leak through the UI or APis.

    Entry objects that aren't submitted for screening are expected
    to be periodically cleaned by a scheduled task (such as daily
    cleaning such entries more than 7 days old)

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


class MailMessage(models.Model):
    """Email message to be delivered"""

    erratum = models.ForeignKey(
        "Erratum",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Erratum to which this message relates",
    )
    to = AddressListField(blank=False, max_length=1000)
    cc = AddressListField(blank=True, max_length=1000)
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
        return EmailMessage(
            subject=self.subject,
            body=self.body,
            to=self.to,
            cc=self.cc,
            headers={"message-id": self.message_id},
        )
