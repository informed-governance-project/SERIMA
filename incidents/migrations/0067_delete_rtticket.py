from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0066_migrate_rttickets"),
    ]

    operations = [
        migrations.DeleteModel(
            name="RTTicket",
        ),
    ]
