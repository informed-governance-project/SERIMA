from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.contrib.admin.models import LogEntry
from django.utils import timezone

from governanceplatform.models import ScriptLogEntry
from incidents.models import Incident, IncidentWorkflow, SectorRegulationWorkflow, SectorRegulationWorkflowEmail
from incidents.scripts import email_reminder, incident_cleaning, log_cleaning, workflow_update_status


@pytest.mark.django_db
class TestIncidentCleaning:
    def test_run_deletes_expired_incidents_and_records_total(self):
        """Delete incidents beyond the retention period and record the number deleted."""
        now = timezone.now()
        expired_incident = Incident.objects.create(
            incident_id="EXPIRED-INCIDENT",
            incident_notification_date=now - timedelta(days=incident_cleaning.INCIDENT_RETENTION_TIME_IN_DAY + 1),
        )
        recent_incident = Incident.objects.create(
            incident_id="RECENT-INCIDENT",
            incident_notification_date=now - timedelta(days=incident_cleaning.INCIDENT_RETENTION_TIME_IN_DAY - 1),
        )

        incident_cleaning.run()

        assert not Incident.objects.filter(pk=expired_incident.pk).exists()
        assert Incident.objects.filter(pk=recent_incident.pk).exists()
        log_entry = ScriptLogEntry.objects.get()
        assert log_entry.action_flag == 3
        assert log_entry.object_id is None
        assert log_entry.object_repr == "System:Incident script deletion 1 incident(s) deleted"


@pytest.mark.django_db
class TestLogCleaning:
    def test_run_deletes_expired_logs_and_records_total(self, django_user_model):
        """Delete admin logs beyond the retention period and record the number deleted."""
        user = django_user_model.objects.create_user(email="script-test@example.com", password="password")
        expired_log = LogEntry.objects.create(user=user, object_repr="Expired log", action_flag=1)
        recent_log = LogEntry.objects.create(user=user, object_repr="Recent log", action_flag=1)
        now = timezone.now()
        LogEntry.objects.filter(pk=expired_log.pk).update(action_time=now - timedelta(days=log_cleaning.LOG_RETENTION_TIME_IN_DAY + 1))
        LogEntry.objects.filter(pk=recent_log.pk).update(action_time=now - timedelta(days=log_cleaning.LOG_RETENTION_TIME_IN_DAY - 1))

        log_cleaning.run()

        assert not LogEntry.objects.filter(pk=expired_log.pk).exists()
        assert LogEntry.objects.filter(pk=recent_log.pk).exists()
        log_entry = ScriptLogEntry.objects.get()
        assert log_entry.action_flag == 3
        assert log_entry.object_id is None
        assert log_entry.object_repr == "System:Log script deletion 1 log(s) deleted"

    def test_run_records_zero_when_no_log_has_expired(self):
        """Record a zero-deletion entry when no admin log has expired."""
        log_cleaning.run()

        assert ScriptLogEntry.objects.get().object_repr == "System:Log script deletion 0 log(s) deleted"


@pytest.mark.django_db
class TestWorkflowUpdateStatus:
    def test_run_sends_email_at_deadline(self, populate_incident_db, monkeypatch):
        """Send the configured status email when an unfilled report reaches its deadline hour."""
        incident = populate_incident_db["incidents"][0]
        Incident.objects.exclude(pk=incident.pk).update(incident_status="CLOSE")
        status_email = populate_incident_db["incidents_email"][0]
        incident.sector_regulation.report_status_changed_email = status_email
        incident.sector_regulation.save()
        report = SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation).order_by("position").first()
        report.trigger_event_before_deadline = "NOTIF_DATE"
        report.delay_in_hours_before_deadline = 2
        report.save()
        now = timezone.now()
        Incident.objects.filter(pk=incident.pk).update(incident_notification_date=now - timedelta(hours=2))
        incident.refresh_from_db()
        send_email = MagicMock()
        monkeypatch.setattr(workflow_update_status.timezone, "now", lambda: now)
        monkeypatch.setattr(workflow_update_status, "send_email", send_email)

        workflow_update_status.run()

        send_email.assert_called_once_with(status_email, incident, workflow=report.workflow)

    def test_run_ignores_closed_incidents(self, populate_incident_db, monkeypatch):
        """Ignore closed incidents even when one of their reports has reached its deadline."""
        Incident.objects.update(incident_status="CLOSE")
        send_email = MagicMock()
        monkeypatch.setattr(workflow_update_status, "send_email", send_email)

        workflow_update_status.run()

        send_email.assert_not_called()


@pytest.mark.django_db
class TestEmailReminder:
    def test_run_sends_detection_date_reminder(self, populate_incident_db, monkeypatch):
        """Send a reminder based on the incident detection date for an unfilled report."""
        incident = populate_incident_db["incidents"][0]
        Incident.objects.exclude(pk=incident.pk).update(incident_status="CLOSE")
        report = SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation).order_by("position").first()
        reminder_email = populate_incident_db["incidents_email"][0]
        SectorRegulationWorkflowEmail.objects.create(
            sector_regulation_workflow=report,
            email=reminder_email,
            trigger_event="DETEC_DATE",
            delay_in_hours=2,
        )
        now = timezone.now()
        Incident.objects.filter(pk=incident.pk).update(incident_detection_date=now - timedelta(hours=2))
        incident.refresh_from_db()
        send_email = MagicMock()
        monkeypatch.setattr(email_reminder.timezone, "now", lambda: now)
        monkeypatch.setattr(email_reminder, "send_email", send_email)

        email_reminder.run()

        send_email.assert_called_once_with(reminder_email, incident, workflow=report.workflow)

    def test_run_sends_previous_workflow_reminder(self, populate_incident_db, monkeypatch):
        """Send a reminder when the delay after the previous workflow has elapsed."""
        incident = populate_incident_db["incidents"][0]
        Incident.objects.exclude(pk=incident.pk).update(incident_status="CLOSE")
        reports = list(
            SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation)
            .select_related("workflow")
            .order_by("position")
        )
        reminder_email = populate_incident_db["incidents_email"][0]
        SectorRegulationWorkflowEmail.objects.create(
            sector_regulation_workflow=reports[1],
            email=reminder_email,
            trigger_event="PREV_WORK",
            delay_in_hours=2,
        )
        now = timezone.now()
        incident_workflow = IncidentWorkflow.objects.create(incident=incident, workflow=reports[0].workflow)
        IncidentWorkflow.objects.filter(pk=incident_workflow.pk).update(timestamp=now - timedelta(hours=2))
        send_email = MagicMock()
        monkeypatch.setattr(email_reminder.timezone, "now", lambda: now)
        monkeypatch.setattr(email_reminder, "send_email", send_email)

        email_reminder.run()

        send_email.assert_called_once_with(
            reminder_email, incident, workflow=incident_workflow.workflow, incident_workflow=incident_workflow
        )

    def test_run_sends_notification_date_reminder(self, populate_incident_db, monkeypatch):
        """Send a reminder based on the submitted workflow notification date."""
        incident = populate_incident_db["incidents"][0]
        Incident.objects.exclude(pk=incident.pk).update(incident_status="CLOSE")
        report = SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation).order_by("position").first()
        reminder_email = populate_incident_db["incidents_email"][0]
        SectorRegulationWorkflowEmail.objects.create(
            sector_regulation_workflow=report,
            email=reminder_email,
            trigger_event="NOTIF_DATE",
            delay_in_hours=2,
        )
        now = timezone.now()
        incident_workflow = IncidentWorkflow.objects.create(incident=incident, workflow=report.workflow)
        IncidentWorkflow.objects.filter(pk=incident_workflow.pk).update(timestamp=now - timedelta(hours=2))
        send_email = MagicMock()
        monkeypatch.setattr(email_reminder.timezone, "now", lambda: now)
        monkeypatch.setattr(email_reminder, "send_email", send_email)

        email_reminder.run()

        send_email.assert_called_once_with(
            reminder_email, incident, workflow=incident_workflow.workflow, incident_workflow=incident_workflow
        )
