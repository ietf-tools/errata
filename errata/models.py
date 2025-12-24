from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone


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
        "RfcMetadata", related_name="erratum", on_delete=models.PROTECT, null=False
    )
    status = models.ForeignKey(
        "Status",
        on_delete=models.PROTECT,
        default="reported",
        related_name="erratum",
        db_column="status_slug",
    )
    type = models.ForeignKey(
        "Type",
        on_delete=models.PROTECT,
        related_name="erratum",
        db_column="type_slug",
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
    format = ArrayField(
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


class Type(Name):
    pass


class Log(models.Model):
    """
    Model representing the log of changes or updates to erratum.
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
    type = models.ForeignKey(
        "Type",
        on_delete=models.PROTECT,
        related_name="logs_type",
        db_column="type_slug",
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
    area_assignment = models.CharField(max_length=32, blank=True)
    responsible_body = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"RFC {self.rfc_number}: {self.title}"
