import logging
from datetime import timedelta

from celery import shared_task
from django.db import DatabaseError
from django.db.models.functions import Now

from governanceplatform.models import ScriptLogEntry
from governanceplatform.settings import INCIDENT_RETENTION_TIME_IN_DAY
from incidents.models import Incident

logger = logging.getLogger(__name__)


# Script to run once day
# remove incidents after a period configured in config.py
@shared_task(name="incident_cleaning")
def run(logger=logger):
    logger.info("running incident_cleaning.py")
    # for all closed incident
    try:
        incident_to_delete_qs = Incident.objects.filter(
            incident_notification_date__lte=Now() - timedelta(days=INCIDENT_RETENTION_TIME_IN_DAY)
        )
    except DatabaseError as e:
        logger.error("Failed to fetch incident to delete: %s", e, exc_info=True)
        raise

    try:
        ScriptLogEntry.objects.create(
            object_id=None,
            object_repr="System:Incident script deletion " + str(incident_to_delete_qs.count()) + " incident(s) deleted",
            action_flag=3,
        )
    except Exception as e:
        logger.error("Failed to write application log: %s", e, exc_info=True)
        raise
    incident_to_delete_qs.delete()
