# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    DirtyBits = apps.get_model("errata", "DirtyBits")
    DirtyBits.objects.create(slug="errata_json", dirty_time=None, processed_time=None)


def reverse(apps, schema_editor):
    DirtyBits = apps.get_model("errata", "DirtyBits")
    DirtyBits.objects.filter(slug="errata_json").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0003_populate_type"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
