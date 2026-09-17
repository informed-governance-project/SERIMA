from django.db import migrations


def backfill_missing_report_timelines(apps, schema_editor):
    """
    Migration 0047 assigned every ReportTimeline it created to the incident's latest report
    instead of the report being iterated, so all the other reports were left without a timeline.
    Give each of them a copy of the latest report's timeline.
    """
    Incident = apps.get_model("incidents", "Incident")
    ReportTimeline = apps.get_model("incidents", "ReportTimeline")
    IncidentWorkflow = apps.get_model("incidents", "IncidentWorkflow")

    incident_ids = IncidentWorkflow.objects.filter(report_timeline__isnull=True).values_list("incident_id", flat=True).distinct()

    for incident in Incident.objects.filter(id__in=incident_ids):
        reports = IncidentWorkflow.objects.filter(incident=incident).order_by("-timestamp")
        latest_report = reports.first()
        source_timeline = latest_report.report_timeline

        if source_timeline is None:
            source_timeline = ReportTimeline.objects.create(
                report_timeline_timezone=incident.incident_timezone,
                incident_detection_date=incident.incident_detection_date,
            )
            latest_report.report_timeline = source_timeline
            latest_report.save(update_fields=["report_timeline"])

        for report in reports.filter(report_timeline__isnull=True):
            report.report_timeline = ReportTimeline.objects.create(
                report_timeline_timezone=source_timeline.report_timeline_timezone,
                incident_detection_date=source_timeline.incident_detection_date,
                incident_starting_date=source_timeline.incident_starting_date,
                incident_resolution_date=source_timeline.incident_resolution_date,
            )
            report.save(update_fields=["report_timeline"])


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0065_alter_emailtranslation_content"),
    ]

    operations = [
        # Not reversible: the timelines created here are indistinguishable from the ones 0047 created correctly
        migrations.RunPython(backfill_missing_report_timelines, migrations.RunPython.noop),
    ]
