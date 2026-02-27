# Copyright The IETF Trust 2025-2026, All Rights Reserved

import django.contrib.postgres.fields
import django.db.models.deletion
import django.utils.timezone
import errata.models
import errata_project.mail
import simple_history.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ErratumType",
            fields=[
                (
                    "slug",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("desc", models.TextField(blank=True)),
                ("used", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="RfcMetadata",
            fields=[
                (
                    "rfc_number",
                    models.PositiveIntegerField(primary_key=True, serialize=False),
                ),
                ("draft_name", models.CharField(blank=True, max_length=255)),
                ("title", models.CharField(max_length=512)),
                ("author_names", models.CharField(blank=True, max_length=1024)),
                (
                    "author_emails",
                    errata.models.AddressListField(blank=True, max_length=2550),
                ),
                ("shepherd_email", models.EmailField(blank=True, max_length=255)),
                ("doc_ad_email", models.EmailField(blank=True, max_length=255)),
                (
                    "area_ad_emails",
                    errata.models.AddressListField(blank=True, max_length=1020),
                ),
                ("std_level", models.CharField(blank=True, max_length=40)),
                ("publication_year", models.PositiveIntegerField()),
                ("publication_month", models.PositiveIntegerField()),
                ("group_acronym", models.CharField(blank=True, max_length=40)),
                ("group_name", models.CharField(blank=True, max_length=255)),
                ("group_list_email", models.EmailField(blank=True, max_length=64)),
                ("area_acronym", models.CharField(blank=True, max_length=40)),
                ("stream", models.CharField(blank=True, max_length=40)),
                ("area_assignment", models.CharField(blank=True, max_length=40)),
                ("obsoleted_by", models.CharField(blank=True, max_length=1024)),
                ("updated_by", models.CharField(blank=True, max_length=1024)),
            ],
        ),
        migrations.CreateModel(
            name="Status",
            fields=[
                (
                    "slug",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("desc", models.TextField(blank=True)),
                ("used", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name_plural": "Statuses",
            },
        ),
        migrations.CreateModel(
            name="Erratum",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rfc_number", models.PositiveIntegerField()),
                ("section", models.TextField(blank=True)),
                ("orig_text", models.TextField(blank=True)),
                ("corrected_text", models.TextField(blank=True)),
                ("submitter_name", models.CharField(blank=True, max_length=80)),
                ("submitter_email", models.EmailField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                (
                    "verifier_name",
                    models.CharField(blank=True, max_length=80, null=True),
                ),
                (
                    "verifier_email",
                    models.EmailField(blank=True, max_length=120, null=True),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "formats",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")],
                            max_length=10,
                        ),
                        blank=True,
                        default=list,
                        help_text="A list of formats. Possible values: 'HTML', 'PDF', and 'TXT'.",
                        size=None,
                    ),
                ),
                (
                    "erratum_type",
                    models.ForeignKey(
                        blank=True,
                        db_column="erratum_type_slug",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="erratum",
                        to="errata.erratumtype",
                    ),
                ),
                (
                    "rfc_metadata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="erratum",
                        to="errata.rfcmetadata",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        db_column="status_slug",
                        default="reported",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="erratum",
                        to="errata.status",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Errata",
            },
        ),
        migrations.CreateModel(
            name="MailMessage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("to", errata.models.AddressListField(max_length=2550)),
                ("cc", errata.models.AddressListField(blank=True, max_length=2550)),
                ("subject", models.CharField(max_length=1000)),
                ("body", models.TextField()),
                (
                    "message_id",
                    models.CharField(
                        default=errata_project.mail.make_message_id, max_length=255
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("sent", models.BooleanField(default=False)),
                (
                    "erratum",
                    models.ForeignKey(
                        blank=True,
                        help_text="Erratum to which this message relates",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="errata.erratum",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="StagedErratum",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "entry_status",
                    models.CharField(
                        choices=[
                            ("incomplete", "Incomplete"),
                            ("submitted", "Submitted for Screening"),
                        ],
                        default="incomplete",
                        max_length=20,
                    ),
                ),
                ("rfc_number", models.PositiveIntegerField()),
                ("section", models.TextField(blank=True)),
                ("orig_text", models.TextField(blank=True)),
                ("corrected_text", models.TextField(blank=True)),
                ("submitter_name", models.CharField(blank=True, max_length=80)),
                ("submitter_email", models.EmailField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "formats",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")],
                            max_length=10,
                        ),
                        blank=True,
                        default=errata.models.get_default_staged_erratum_formats,
                        help_text="A list of formats. Possible values: 'HTML', 'PDF', and 'TXT'.",
                        size=None,
                    ),
                ),
                (
                    "rfc_metadata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stagederratum",
                        to="errata.rfcmetadata",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "StagedErrata",
            },
        ),
        migrations.CreateModel(
            name="HistoricalErratum",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("rfc_number", models.PositiveIntegerField()),
                ("section", models.TextField(blank=True)),
                ("orig_text", models.TextField(blank=True)),
                ("corrected_text", models.TextField(blank=True)),
                ("submitter_name", models.CharField(blank=True, max_length=80)),
                ("submitter_email", models.EmailField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                (
                    "verifier_name",
                    models.CharField(blank=True, max_length=80, null=True),
                ),
                (
                    "verifier_email",
                    models.EmailField(blank=True, max_length=120, null=True),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "formats",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")],
                            max_length=10,
                        ),
                        blank=True,
                        default=list,
                        help_text="A list of formats. Possible values: 'HTML', 'PDF', and 'TXT'.",
                        size=None,
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "erratum_type",
                    models.ForeignKey(
                        blank=True,
                        db_column="erratum_type_slug",
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="errata.erratumtype",
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "rfc_metadata",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="errata.rfcmetadata",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        blank=True,
                        db_column="status_slug",
                        db_constraint=False,
                        default="reported",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="errata.status",
                    ),
                ),
            ],
            options={
                "verbose_name": "historical erratum",
                "verbose_name_plural": "historical Errata",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
