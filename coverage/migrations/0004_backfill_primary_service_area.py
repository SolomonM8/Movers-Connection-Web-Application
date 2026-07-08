from django.db import migrations


def backfill_primary(apps, schema_editor):
    LaborerProfile = apps.get_model("accounts", "LaborerProfile")
    ServiceArea = apps.get_model("coverage", "ServiceArea")

    for profile in LaborerProfile.objects.all():
        first_area = ServiceArea.objects.filter(laborer_profile=profile).order_by("id").first()
        if first_area and not ServiceArea.objects.filter(
            laborer_profile=profile, is_primary=True
        ).exists():
            first_area.is_primary = True
            first_area.save(update_fields=["is_primary"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coverage", "0003_servicearea_is_primary"),
    ]

    operations = [
        migrations.RunPython(backfill_primary, noop),
    ]
