from django.db import migrations, models


# A unique field with a callable default must be added in three steps: a single AddField would
# evaluate uuid4 once and give every existing row the same value. The project keeps the values it
# already had as api_id, so the references API clients hold stay valid.
class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "0024_project_api_id"),
    ]

    operations = [
        migrations.RenameField(
            model_name="project",
            old_name="api_id",
            new_name="public_id",
        ),
        migrations.AddField(
            model_name="companyproject",
            name="public_id",
            field=models.UUIDField(editable=False, null=True, verbose_name="Public ID"),
        ),
        migrations.AddField(
            model_name="observationrecommendationthrough",
            name="public_id",
            field=models.UUIDField(editable=False, null=True, verbose_name="Public ID"),
        ),
    ]
