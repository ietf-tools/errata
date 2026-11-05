# Copyright The IETF Trust 2026, All Rights Reserved

import django.db.models.deletion
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0010_populate_resolved_routing"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupReplacement",
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
                ("group", models.CharField(max_length=40, unique=True)),
                ("replacement_group", models.CharField(max_length=40)),
                ("replacement_list_email", models.EmailField(max_length=64)),
                (
                    "replacement_area",
                    models.CharField(
                        blank=True,
                        help_text="Leave blank to keep the area of each RFC.",
                        max_length=40,
                    ),
                ),
            ],
            options={
                "ordering": ["group"],
            },
        ),
        migrations.CreateModel(
            name="HistoricalGroupReplacement",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("group", models.CharField(db_index=True, max_length=40)),
                ("replacement_group", models.CharField(max_length=40)),
                ("replacement_list_email", models.EmailField(max_length=64)),
                (
                    "replacement_area",
                    models.CharField(
                        blank=True,
                        help_text="Leave blank to keep the area of each RFC.",
                        max_length=40,
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
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical group replacement",
                "verbose_name_plural": "historical group replacements",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
