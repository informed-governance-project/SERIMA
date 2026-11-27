from django.db import migrations, models


# A unique field with a callable default must be added in three steps: a single AddField would
# evaluate uuid4 once and give every existing row the same value.
class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0074_email_content_markdown_to_html"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="public_id",
            field=models.UUIDField(editable=False, null=True, verbose_name="Public ID"),
        ),
        migrations.AddField(
            model_name="incidentworkflow",
            name="public_id",
            field=models.UUIDField(editable=False, null=True, verbose_name="Public ID"),
        ),
    ]
