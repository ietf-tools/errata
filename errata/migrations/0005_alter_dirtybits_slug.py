# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("errata", "0004_populate_dirty_bits"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dirtybits",
            name="slug",
            field=models.CharField(
                choices=[("errata_json", "Errata JSON")], max_length=40, unique=True
            ),
        ),
    ]
