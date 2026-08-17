import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth.models import Group
from django.db import DatabaseError
from django.db.models.functions import Now

from governanceplatform.models import ScriptLogEntry, User
from governanceplatform.settings import PASSWORD_RESET_TIMEOUT

logger = logging.getLogger(__name__)


# Script to run every hour
# remove users who are inactive, never logged, and recently joined
@shared_task(name="unactive_account_cleaning")
def run(logger=logger):
    logger.info("running unactive_account_cleaning.py")
    try:
        IncidentUserGrouId = Group.objects.get(name="IncidentUser").id
        user_to_delete_qs = User.objects.filter(
            last_login__isnull=True,
            email_verified=False,
            date_joined__lte=Now() - timedelta(seconds=PASSWORD_RESET_TIMEOUT),
            groups__in=[IncidentUserGrouId],
        )
    except DatabaseError as e:
        logger.error("Failed to fetch users to delete: %s", e, exc_info=True)
        raise

    try:
        deleted_number = user_to_delete_qs.count()
        ScriptLogEntry.objects.create(
            object_id=None,
            object_repr=f"System:Inactive user script deletion {deleted_number} user(s) deleted",
            action_flag=3,
        )
    except Exception as e:
        logger.error("Failed to write application log: %s", e, exc_info=True)
        raise
    logger.info("Deleting %s user(s)", deleted_number)
    user_to_delete_qs.delete()
