#!/usr/bin/env python3

from celery import shared_task
from django.utils import translation

from governanceplatform.tasks import store_async_pdf

# Celery autodiscovery imports only this module; importing the scripts here is what
# registers their scheduled tasks.
from incidents.scripts import (
    email_reminder,
    incident_cleaning,
    log_cleaning,
    workflow_update_status,
)

from .models import Incident, IncidentWorkflow
from .pdf_generation import get_pdf_report

__all__ = ["email_reminder", "incident_cleaning", "log_cleaning", "workflow_update_status"]


@shared_task(bind=True)
def generate_incident_pdf_task(self, incident_id: int, incident_workflow_id: int | None, language: str):
    incident = Incident.objects.get(pk=incident_id)
    incident_workflow = IncidentWorkflow.objects.get(pk=incident_workflow_id) if incident_workflow_id else None

    with translation.override(language):
        pdf_report = get_pdf_report(incident, incident_workflow)

    store_async_pdf(self.request.id, pdf_report)
