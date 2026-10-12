#!/usr/bin/env python3

import os
from pathlib import Path

from celery import shared_task
from django.utils import translation

# Celery autodiscovery imports only this module; importing the scripts here is what
# registers their scheduled tasks.
from incidents.scripts import (
    email_reminder,
    incident_cleaning,
    log_cleaning,
    workflow_update_status,
)

from .models import Incident, IncidentWorkflow
from .pdf_generation import get_pdf_file_path, get_pdf_report

__all__ = ["email_reminder", "incident_cleaning", "log_cleaning", "workflow_update_status"]


@shared_task(bind=True)
def generate_incident_pdf_task(self, incident_id: int, incident_workflow_id: int | None, language: str):
    incident = Incident.objects.get(pk=incident_id)
    incident_workflow = IncidentWorkflow.objects.get(pk=incident_workflow_id) if incident_workflow_id else None

    with translation.override(language):
        pdf_report = get_pdf_report(incident, incident_workflow)

    file_path = get_pdf_file_path(self.request.id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as pdf_file:
        pdf_file.write(pdf_report)

    # The download removes the file; this only catches the ones nobody came back for.
    cleanup_incident_pdf_file.apply_async(kwargs={"task_id": self.request.id}, countdown=3600)


@shared_task
def cleanup_incident_pdf_file(task_id: str):
    Path(get_pdf_file_path(task_id)).unlink(missing_ok=True)
