from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0072_migrate_rttickets"),
    ]

    operations = [
        migrations.DeleteModel(
            name="RTTicket",
        ),
    ]
