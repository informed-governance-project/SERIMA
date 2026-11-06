#!/usr/bin/env python3

# Celery autodiscovery imports only this module; importing the scripts here is what
# registers their scheduled tasks.
from incidents.scripts import (
    connector_delivery,
    email_reminder,
    incident_cleaning,
    log_cleaning,
    workflow_update_status,
)

__all__ = ["connector_delivery", "email_reminder", "incident_cleaning", "log_cleaning", "workflow_update_status"]
