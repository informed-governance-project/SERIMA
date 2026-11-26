import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("securityobjectives", "0050_populate_public_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="standardanswergroup",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Public ID"),
        ),
        migrations.AlterField(
            model_name="standardanswer",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Public ID"),
        ),
    ]
