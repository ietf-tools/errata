# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0008_remove_rfcmetadata_area_assignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="rfcmetadata",
            name="resolved_area",
            field=models.CharField(blank=True, editable=False, max_length=40),
        ),
        migrations.AddField(
            model_name="rfcmetadata",
            name="resolved_group_acronym",
            field=models.CharField(blank=True, editable=False, max_length=40),
        ),
        migrations.AddField(
            model_name="rfcmetadata",
            name="resolved_group_list_email",
            field=models.EmailField(blank=True, editable=False, max_length=64),
        ),
    ]
