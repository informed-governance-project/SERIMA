import logging
import math

from celery import shared_task
from django.db import DatabaseError
from django.utils import timezone

from incidents.email import send_email
from incidents.models import Incident, IncidentWorkflow, SectorRegulationWorkflow

logger = logging.getLogger(__name__)


# Script to run every hour
# Send an email when the delay is overdue
# The status change is managed in frontend
@shared_task(name="workflow_update_status")
def run(logger=logger):
    logger.info("running workflow_update_status.py")
    # for all unclosed incident
    actual_time = timezone.now()
    try:
        ongoing_incidents = Incident.objects.filter(incident_status="GOING")
    except DatabaseError as e:
        logger.error("Failed to fetch ongoing incidents: %s", e, exc_info=True)
        raise

    for incident in ongoing_incidents:
        try:
            filled_workflow_ids = IncidentWorkflow.objects.filter(incident=incident).values_list("workflow", flat=True)

            if not incident.sector_regulation:
                continue

            unfilled_report_ids = incident.sector_regulation.workflows.exclude(id__in=filled_workflow_ids).values_list("id", flat=True)

            srw = SectorRegulationWorkflow.objects.filter(
                workflow__in=unfilled_report_ids,
                sector_regulation=incident.sector_regulation,
            )

            for report in srw:
                try:
                    delay_in_hours = report.delay_in_hours_before_deadline
                    dt = report.how_late_is_the_report(incident, actual_time)

                    if dt and math.floor(dt.total_seconds() / 60 / 60) == delay_in_hours:
                        if incident.sector_regulation.report_status_changed_email:
                            send_email(
                                incident.sector_regulation.report_status_changed_email,
                                incident,
                            )
                except Exception as e:
                    logger.error(
                        "Error processing report ID %s for incident ID %s: %s",
                        report.id,
                        incident.id,
                        e,
                        exc_info=True,
                    )

        except Exception as e:
            logger.error("Error processing incident ID %s: %s", incident.id, e, exc_info=True)
