from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from governanceplatform.models import ScriptLogEntry, User
from governanceplatform.scripts import clean_incident_user, unactive_account_cleaning
from incidents.models import Incident


# Tests the cleanup rules for temporary incident users.
@pytest.mark.django_db
class TestCleanIncidentUser:
    # Deletes expired users with or without a previous login and records the total.
    def test_run_deletes_old_incident_users_and_records_the_number_deleted(self, create_incident_user):
        now = timezone.now()
        retention = clean_incident_user.DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
        never_logged_in = create_incident_user(
            email="never-logged-in@example.com",
            date_joined=now - timedelta(days=retention + 1),
        )
        previously_logged_in = create_incident_user(
            email="previously-logged-in@example.com",
            date_joined=now - timedelta(days=retention + 10),
            last_login=now - timedelta(days=retention + 1),
        )

        clean_incident_user.run()

        assert not User.objects.filter(pk=never_logged_in.pk).exists()
        assert not User.objects.filter(pk=previously_logged_in.pk).exists()
        log_entry = ScriptLogEntry.objects.get()
        assert log_entry.action_flag == 3
        assert log_entry.object_id is None
        assert log_entry.object_repr == "System:IncidentUser script deletion 2 user(s) deleted"

    # Keeps a never-logged-in user whose account is still within the retention period.
    def test_run_keeps_never_logged_in_user_created_within_retention_period(self, create_incident_user):
        retention = clean_incident_user.DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
        user = create_incident_user(
            email="recent-user@example.com",
            date_joined=timezone.now() - timedelta(days=retention - 1),
        )

        clean_incident_user.run()

        assert User.objects.filter(pk=user.pk).exists()

    # Uses the last login rather than the creation date for previously active users.
    def test_run_uses_last_login_for_users_who_have_logged_in(self, create_incident_user):
        now = timezone.now()
        retention = clean_incident_user.DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
        user = create_incident_user(
            email="recent-login@example.com",
            date_joined=now - timedelta(days=retention + 10),
            last_login=now - timedelta(days=retention - 1),
        )

        clean_incident_user.run()

        assert User.objects.filter(pk=user.pk).exists()

    # Keeps expired users who do not belong to the temporary incident-user group.
    def test_run_keeps_old_user_outside_incident_user_group(self, create_incident_user):
        other_group = Group.objects.create(name="OperatorUser")
        retention = clean_incident_user.DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
        user = create_incident_user(
            email="operator@example.com",
            date_joined=timezone.now() - timedelta(days=retention + 1),
            group=other_group,
        )

        clean_incident_user.run()

        assert User.objects.filter(pk=user.pk).exists()

    # Keeps an expired temporary user when an incident still references the account.
    def test_run_keeps_old_user_linked_to_an_incident(self, create_incident_user):
        retention = clean_incident_user.DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
        user = create_incident_user(
            email="incident-owner@example.com",
            date_joined=timezone.now() - timedelta(days=retention + 1),
        )
        Incident.objects.create(incident_id="TEST-INCIDENT", contact_user=user)

        clean_incident_user.run()

        assert User.objects.filter(pk=user.pk).exists()

    # Records a zero-deletion entry when no temporary user is eligible for cleanup.
    def test_run_records_zero_when_no_user_is_eligible(self, create_incident_user):
        retention = clean_incident_user.DAY_BEFORE_DELETING_INC_USER_WITHOUT_INCIDENT
        create_incident_user(
            email="recent@example.com",
            date_joined=timezone.now() - timedelta(days=retention - 1),
        )

        clean_incident_user.run()

        log_entry = ScriptLogEntry.objects.get()
        assert log_entry.object_repr == "System:IncidentUser script deletion 0 user(s) deleted"


# Tests the cleanup rules for inactive and unverified incident-reporting users.
@pytest.mark.django_db
class TestUnactiveAccountCleaning:
    # Deletes a never-logged-in, unverified incident user after the activation timeout.
    def test_run_deletes_user_who_meets_cleanup_conditions(self, create_incident_user):
        timeout = unactive_account_cleaning.PASSWORD_RESET_TIMEOUT
        user = create_incident_user(
            email="expired-unverified@example.com",
            date_joined=timezone.now() - timedelta(seconds=timeout + 1),
        )

        unactive_account_cleaning.run()

        assert not User.objects.filter(pk=user.pk).exists()

    # Keeps an unverified incident user while the activation timeout has not expired.
    def test_run_keeps_user_who_does_not_meet_cleanup_conditions(self, create_incident_user):
        timeout = unactive_account_cleaning.PASSWORD_RESET_TIMEOUT
        user = create_incident_user(
            email="recent-unverified@example.com",
            date_joined=timezone.now() - timedelta(seconds=timeout - 1),
        )

        unactive_account_cleaning.run()

        assert User.objects.filter(pk=user.pk).exists()
