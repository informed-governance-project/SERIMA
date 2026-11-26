import uuid

from django.db import migrations

BATCH_SIZE = 1000


def populate_public_ids(apps, schema_editor):
    for model_name in ("Incident", "IncidentWorkflow"):
        model = apps.get_model("incidents", model_name)
        batch = []
        for obj in model.objects.filter(public_id__isnull=True).only("pk").iterator(chunk_size=BATCH_SIZE):
            obj.public_id = uuid.uuid4()
            batch.append(obj)
            if len(batch) == BATCH_SIZE:
                model.objects.bulk_update(batch, ["public_id"])
                batch = []
        model.objects.bulk_update(batch, ["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0075_incident_public_id"),
    ]

    operations = [
        # Reversing 0075 drops the column, so there is nothing to undo here.
        migrations.RunPython(populate_public_ids, migrations.RunPython.noop),
    ]
