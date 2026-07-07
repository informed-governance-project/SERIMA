#!/usr/bin/env python3

import os

import django

# django init
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "governanceplatform.settings")
django.setup()

from incidents.scripts import (  # noqa: E402 F401
    connector_delivery,
    email_reminder,
    incident_cleaning,
    log_cleaning,
    workflow_update_status,
)
