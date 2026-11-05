# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations

# errata_auth.utils.SUCCESSOR_AREAS as of this migration. RfcMetadata.save
# uses the live mapping from then on.
CLOSED_AREA_SUCCESSORS = {"app": "art", "rai": "art", "tsv": "wit"}


def forward(apps, schema_editor):
    RfcMetadata = apps.get_model("errata", "RfcMetadata")
    AreaAssignment = apps.get_model("errata", "AreaAssignment")
    assigned_areas = dict(AreaAssignment.objects.values_list("rfc_metadata_id", "area"))
    rows = list(RfcMetadata.objects.all())
    for metadata in rows:
        area = assigned_areas.get(metadata.rfc_number) or metadata.area_acronym
        metadata.resolved_area = CLOSED_AREA_SUCCESSORS.get(area, area)
        metadata.resolved_group_acronym = metadata.group_acronym
        metadata.resolved_group_list_email = metadata.group_list_email
    RfcMetadata.objects.bulk_update(
        rows,
        ["resolved_area", "resolved_group_acronym", "resolved_group_list_email"],
        batch_size=1000,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0009_rfcmetadata_resolved_routing"),
    ]

    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
