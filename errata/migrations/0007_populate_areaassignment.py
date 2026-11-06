# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations
from django.utils import timezone


def forward(apps, schema_editor):
    RfcMetadata = apps.get_model("errata", "RfcMetadata")
    AreaAssignment = apps.get_model("errata", "AreaAssignment")
    HistoricalAreaAssignment = apps.get_model("errata", "HistoricalAreaAssignment")
    assignments = AreaAssignment.objects.bulk_create(
        AreaAssignment(rfc_metadata_id=rfc_number, area=area)
        for rfc_number, area in RfcMetadata.objects.exclude(area_assignment="")
        .order_by("rfc_number")
        .values_list("rfc_number", "area_assignment")
    )
    # Start each assignment's history, so it doesn't appear from nowhere.
    now = timezone.now()
    HistoricalAreaAssignment.objects.bulk_create(
        HistoricalAreaAssignment(
            id=assignment.id,
            rfc_metadata_id=assignment.rfc_metadata_id,
            area=assignment.area,
            history_date=now,
            history_type="+",
            history_change_reason="Copied from RfcMetadata.area_assignment",
        )
        for assignment in assignments
    )


def reverse(apps, schema_editor):
    RfcMetadata = apps.get_model("errata", "RfcMetadata")
    AreaAssignment = apps.get_model("errata", "AreaAssignment")
    # Put the assignments back on RfcMetadata, which 0008 removes them from.
    for rfc_number, area in AreaAssignment.objects.values_list(
        "rfc_metadata_id", "area"
    ):
        RfcMetadata.objects.filter(rfc_number=rfc_number).update(area_assignment=area)
    apps.get_model("errata", "HistoricalAreaAssignment").objects.all().delete()
    AreaAssignment.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0006_areaassignment"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
