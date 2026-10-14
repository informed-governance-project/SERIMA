"""
Deadline evaluation for incident reports.

is_deadline_exceeded drives the status badge on every row of the incident list, so each
trigger event has to resolve to OUT or UNDE rather than raising.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from incidents.helpers import is_deadline_exceeded
from incidents.models import IncidentWorkflow, SectorRegulationWorkflow


@pytest.fixture
def incident_with_reports(populate_incident_db):
    """The operator incident plus its two ordered reports."""
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")
    reports = list(incident.sector_regulation.workflows.order_by("sectorregulationworkflow__position"))
    return incident, reports


def _configure(incident, report, trigger, delay_in_hours=1):
    SectorRegulationWorkflow.objects.filter(
        sector_regulation=incident.sector_regulation,
        workflow=report,
    ).update(trigger_event_before_deadline=trigger, delay_in_hours_before_deadline=delay_in_hours)


@pytest.mark.django_db()
def test_returns_the_review_status_of_a_submitted_report(incident_with_reports):
    """Once a report exists its own review status wins over any deadline calculation."""
    incident, reports = incident_with_reports
    submitted = IncidentWorkflow.objects.create(incident=incident, workflow=reports[0])

    assert is_deadline_exceeded(reports[0], incident) == submitted.review_status


@pytest.mark.django_db()
def test_notification_date_deadline_is_exceeded(incident_with_reports):
    incident, reports = incident_with_reports
    _configure(incident, reports[0], "NOTIF_DATE", delay_in_hours=1)
    incident.incident_notification_date = timezone.now() - timedelta(hours=5)
    incident.save()

    assert is_deadline_exceeded(reports[0], incident) == "OUT"


@pytest.mark.django_db()
def test_notification_date_deadline_still_running(incident_with_reports):
    incident, reports = incident_with_reports
    _configure(incident, reports[0], "NOTIF_DATE", delay_in_hours=48)
    incident.incident_notification_date = timezone.now() - timedelta(hours=1)
    incident.save()

    assert is_deadline_exceeded(reports[0], incident) == "UNDE"


@pytest.mark.django_db()
def test_detection_date_deadline_is_exceeded(incident_with_reports):
    incident, reports = incident_with_reports
    _configure(incident, reports[0], "DETECT_DATE", delay_in_hours=1)
    sector_regulation = incident.sector_regulation
    sector_regulation.is_detection_date_needed = True
    sector_regulation.save()
    incident.incident_detection_date = timezone.now() - timedelta(hours=5)
    incident.save()

    assert is_deadline_exceeded(reports[0], incident) == "OUT"


@pytest.mark.django_db()
def test_detection_date_deadline_undetermined_without_a_detection_date(incident_with_reports):
    """No detection date anywhere means no deadline can be computed, not a crash."""
    incident, reports = incident_with_reports
    _configure(incident, reports[0], "DETECT_DATE", delay_in_hours=1)
    sector_regulation = incident.sector_regulation
    sector_regulation.is_detection_date_needed = True
    sector_regulation.save()
    incident.incident_detection_date = None
    incident.save()

    assert is_deadline_exceeded(reports[0], incident) == "UNDE"


@pytest.mark.django_db()
def test_previous_workflow_deadline_is_exceeded(incident_with_reports):
    """The second report's clock starts when the first one was submitted."""
    incident, reports = incident_with_reports
    _configure(incident, reports[1], "PREV_WORK", delay_in_hours=1)
    submitted = IncidentWorkflow.objects.create(incident=incident, workflow=reports[0])
    IncidentWorkflow.objects.filter(pk=submitted.pk).update(timestamp=timezone.now() - timedelta(hours=5))

    assert is_deadline_exceeded(reports[1], incident) == "OUT"


@pytest.mark.django_db()
def test_previous_workflow_undetermined_when_nothing_submitted_yet(incident_with_reports):
    incident, reports = incident_with_reports
    _configure(incident, reports[1], "PREV_WORK", delay_in_hours=1)

    assert is_deadline_exceeded(reports[1], incident) == "UNDE"


@pytest.mark.django_db()
def test_unknown_trigger_is_undetermined(incident_with_reports):
    incident, reports = incident_with_reports
    _configure(incident, reports[0], "NONE")

    assert is_deadline_exceeded(reports[0], incident) == "UNDE"
