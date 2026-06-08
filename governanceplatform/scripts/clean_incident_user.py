import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth.models import Group
from django.db import DatabaseError
from django.db.models.functions import Now

from governanceplatform.models import ScriptLogEntry, User
from governanceplatform.settings import DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT

logger = logging.getLogger(__name__)


# Script to run once day
# remove incident user which are not connected
# if now > last_login + DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
# if last_login is null we take the date_joined
@shared_task(name="clean_incident_user")
def run(logger=logger):
    logger.info("clean_incident_user.py")
    try:
        IncidentUserGrouId = Group.objects.get(name="IncidentUser").id
        not_logged_user_to_delete_qs = User.objects.filter(
            last_login__isnull=True,
            date_joined__lte=Now() - timedelta(days=DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT),
            groups__in=[IncidentUserGrouId],
            incident__isnull=True,
        )
        logged_user_to_delete_qs = User.objects.filter(
            last_login__lte=Now() - timedelta(days=DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT),
            last_login__isnull=False,
            groups__in=[IncidentUserGrouId],
            incident__isnull=True,
        )
    except DatabaseError as e:
        logger.error("Failed to fetch users to delete: %s", e, exc_info=True)
        raise

    try:
        deleted_number = not_logged_user_to_delete_qs.count() + logged_user_to_delete_qs.count()
        ScriptLogEntry.objects.create(
            object_id=None,
            object_repr="System:IncidentUser script deletion " + str(deleted_number) + " user(s) deleted",
            action_flag=3,
        )
    except Exception as e:
        logger.error("Failed to write application log: %s", e, exc_info=True)
        raise
    logger.info("Deleting %s incident user(s) who have never logged in", deleted_number)
    not_logged_user_to_delete_qs.delete()
    logged_user_to_delete_qs.delete()
