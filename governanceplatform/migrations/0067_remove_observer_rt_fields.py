from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("governanceplatform", "0066_migrate_rt_to_connectors"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="observer",
            name="_rt_token",
        ),
        migrations.RemoveField(
            model_name="observer",
            name="rt_queue",
        ),
        migrations.RemoveField(
            model_name="observer",
            name="rt_url",
        ),
    ]
