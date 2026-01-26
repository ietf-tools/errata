# Copyright The IETF Trust 2025-2026, All Rights Reserved

from django.db import migrations


def add_type_data(apps, schema_editor):
    ErratumType = apps.get_model("errata", "ErratumType")
    types = [
        {"slug": "editorial", "name": "Editorial", "order": 2},
        {"slug": "technical", "name": "Technical", "order": 1},
    ]
    for type in types:
        ErratumType.objects.create(**type)


def remove_type_data(apps, schema_editor):
    ErratumType = apps.get_model("errata", "ErratumType")
    slugs = ["editorial", "technical"]
    ErratumType.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0002_populate_status"),
    ]

    operations = [
        migrations.RunPython(add_type_data, remove_type_data),
    ]
