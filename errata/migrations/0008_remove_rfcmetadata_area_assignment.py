# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0007_populate_areaassignment"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="rfcmetadata",
            name="area_assignment",
        ),
    ]
