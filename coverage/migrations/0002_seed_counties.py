import json
from pathlib import Path

from django.db import migrations

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "counties_seed.json"


def seed_counties(apps, schema_editor):
    County = apps.get_model("coverage", "County")
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    County.objects.bulk_create(
        [County(fips=row["fips"], name=row["name"], state=row["state"]) for row in rows],
        batch_size=500,
    )


def unseed_counties(apps, schema_editor):
    County = apps.get_model("coverage", "County")
    County.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coverage", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_counties, unseed_counties),
    ]
