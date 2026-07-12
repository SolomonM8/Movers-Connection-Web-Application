from django.db import migrations
from django.db.models import F


def backfill_accepted(apps, schema_editor):
    Connection = apps.get_model("accounts", "Connection")
    Connection.objects.update(status="accepted", responded_at=F("created_at"))


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_connection_requested_by_connection_responded_at_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_accepted, noop_reverse),
    ]
