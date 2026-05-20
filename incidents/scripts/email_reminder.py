import logging
import math

from celery import shared_task
from django.db import DatabaseError
from django.utils import timezone

from incidents.email import send_email
from incidents.models import (
    Incident,
    IncidentWorkflow,
    SectorRegulationWorkflow,
    SectorRegulationWorkflowEmail,
)

logger = logging.getLogger(__name__)


# Script to run every hour
@shared_task(name="email_reminder")
def run(logger=logger):
    logger.info("running email_reminder.py")
    # for all unclosed incident
    actual_time = timezone.now()
    try:
        ongoing_incidents = Incident.objects.filter(incident_status="GOING")
    except DatabaseError as e:
        logger.error("Failed to fetch ongoing incidents: %s", e, exc_info=True)
        raise

    for incident in ongoing_incidents:
        try:
            # detection date, the email is sent xx hours if the report is not filled see #451
            for report in incident.get_all_workflows():
                if (
                    not IncidentWorkflow.objects.filter(
                        incident=incident,
                        workflow=report,
                    ).exists()
                    and incident.incident_detection_date is not None
                ):
                    emails = SectorRegulationWorkflowEmail.objects.filter(
                        sector_regulation_workflow__sector_regulation=incident.sector_regulation,
                        sector_regulation_workflow__workflow=report,
                        trigger_event="DETEC_DATE",
                    )
                    for email in emails:
                        dt = actual_time - incident.incident_detection_date
                        if math.floor(dt.total_seconds() / 60 / 60) == email.delay_in_hours:
                            send_email(email.email, incident)
            # Workflow with deadline from prev workflow
            for incident_workflow in incident.get_latest_incident_workflows(timestamp_order="timestamp"):
                # chek if there is a next workflow
                next_workflow = incident_workflow.get_next_workflow()
                if next_workflow is not False:
                    next_incident_workflow = (
                        IncidentWorkflow.objects.all()
                        .filter(
                            incident=incident,
                            workflow=next_workflow,
                        )
                        .order_by("-timestamp")
                        .first()
                    )
                    # there is one next workflow but not filled
                    if next_incident_workflow is None:
                        next_sector_regulation_workflow = (
                            SectorRegulationWorkflow.objects.all()
                            .filter(
                                sector_regulation=incident.sector_regulation,
                                workflow=next_workflow,
                            )
                            .first()
                        )
                        emails = SectorRegulationWorkflowEmail.objects.all().filter(
                            sector_regulation_workflow=next_sector_regulation_workflow,
                            trigger_event="PREV_WORK",
                        )
                        for email in emails:
                            dt = actual_time - incident_workflow.timestamp
                            if math.floor(dt.total_seconds() / 60 / 60) == email.delay_in_hours:
                                send_email(email.email, incident)
                # From notification date
                sector_regulation_workflow = (
                    SectorRegulationWorkflow.objects.all()
                    .filter(
                        sector_regulation=incident.sector_regulation,
                        workflow=incident_workflow.workflow,
                    )
                    .first()
                )

                emails = SectorRegulationWorkflowEmail.objects.all().filter(
                    sector_regulation_workflow=sector_regulation_workflow,
                    trigger_event="NOTIF_DATE",
                )
                for email in emails:
                    dt = actual_time - incident_workflow.timestamp
                    if math.floor(dt.total_seconds() / 60 / 60) == email.delay_in_hours:
                        send_email(email.email, incident)
        except Exception as e:
            logger.error("Error processing incident ID %s: %s", incident.id, e, exc_info=True)
