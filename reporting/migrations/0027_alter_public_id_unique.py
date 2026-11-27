import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "0026_populate_public_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Public ID"),
        ),
        migrations.AlterField(
            model_name="companyproject",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Public ID"),
        ),
        migrations.AlterField(
            model_name="observationrecommendationthrough",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Public ID"),
        ),
    ]
