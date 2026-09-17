from django.db import migrations


def delete_orphan_report_timelines(apps, schema_editor):
    """
    Clear the timelines left behind by migration 0047 and by every report deleted before
    the post_delete cleanup existed. Nothing points at them, so they are unreachable.
    """
    ReportTimeline = apps.get_model("incidents", "ReportTimeline")

    ReportTimeline.objects.filter(incident_workflow__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0066_backfill_missing_report_timelines"),
    ]

    operations = [
        # Not reversible: the deleted timelines are unreachable and cannot be reconstructed
        migrations.RunPython(delete_orphan_report_timelines, migrations.RunPython.noop),
    ]
