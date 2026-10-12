#!/usr/bin/env python3

# Celery autodiscovery imports only this module; importing the scripts here is what
# registers their scheduled tasks.
from incidents.scripts import (
    email_reminder,
    incident_cleaning,
    log_cleaning,
    workflow_update_status,
)

__all__ = ["email_reminder", "incident_cleaning", "log_cleaning", "workflow_update_status"]
