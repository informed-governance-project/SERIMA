import uuid

from django.db import migrations, models


def populate_api_ids(apps, schema_editor):
    project = apps.get_model("reporting", "Project")
    for obj in project.objects.using(schema_editor.connection.alias).all().iterator():
        obj.api_id = uuid.uuid4()
        obj.save(using=schema_editor.connection.alias, update_fields=["api_id"])


class Migration(migrations.Migration):
    dependencies = [("reporting", "0023_riskdata_unique_risk_uuid_service")]

    operations = [
        migrations.AddField(
            model_name="project", name="api_id", field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_api_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="project", name="api_id", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
