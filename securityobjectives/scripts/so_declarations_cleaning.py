import logging
from datetime import timedelta

from celery import shared_task
from django.db import DatabaseError
from django.db.models.functions import Now

from governanceplatform.models import ScriptLogEntry
from governanceplatform.settings import SECURITY_OBJECTIVE_RETENTION_TIME_IN_DAY
from securityobjectives.models import StandardAnswer

logger = logging.getLogger(__name__)


# Script to run once day
# remove security objectives declarations after a period configured in config.py
@shared_task(name="so_declarations_cleaning")
def run(logger=logger):
    logger.info("running so_declarations_cleaning.py")
    try:
        declarations_delete_qs = StandardAnswer.objects.filter(
            creation_date__lte=Now() - timedelta(days=SECURITY_OBJECTIVE_RETENTION_TIME_IN_DAY)
        )
    except DatabaseError as e:
        logger.error(
            "Failed to fetch security objective declarations to delete: %s",
            e,
            exc_info=True,
        )
        raise

    try:
        ScriptLogEntry.objects.create(
            object_id=None,
            object_repr="System:Security Objectives script deletion " + str(declarations_delete_qs.count()) + " declarations(s) deleted",
            action_flag=3,
        )
    except Exception as e:
        logger.error("Failed to write application log: %s", e, exc_info=True)
        raise
    declarations_delete_qs.delete()
