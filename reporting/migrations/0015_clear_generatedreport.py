from django.db import migrations


def clear_generatedreport(apps, schema_editor):
    GeneratedReport = apps.get_model("reporting", "GeneratedReport")
    GeneratedReport.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "reporting",
            "0014_remove_generatedreport_user_generatedreport_project_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(clear_generatedreport),
    ]
