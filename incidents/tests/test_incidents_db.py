import datetime as dt

import pytest
from django.utils import timezone
from django.utils.translation import activate

from incidents.models import (
    Email,
    Impact,
    IncidentWorkflow,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    SectorRegulation,
    SectorRegulationWorkflow,
    Workflow,
)


@pytest.mark.django_db
def test_incidents_elements_in_db(populate_incident_db):
    """
    Check if objects are present in DB
    """
    activate("en")
    assert Email.objects.count() == 4
    assert Question.objects.count() == 10
    assert QuestionCategory.objects.count() == 4
    assert PredefinedAnswer.objects.count() == 8
    assert Workflow.objects.count() == 4
    assert QuestionCategoryOptions.objects.count() == 4
    assert QuestionOptions.objects.count() == 10
    assert SectorRegulation.objects.count() == 2
    assert SectorRegulationWorkflow.objects.count() == 4
    assert Impact.objects.count() == 3


@pytest.fixture
def incident_with_reversed_positions(populate_incident_db):
    """
    An incident on sector regulation 1, whose workflows are repositioned so that their
    position order is the reverse of their primary-key order (#950).
    """
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")
    first_created, second_created = incident.sector_regulation.workflows.order_by("pk")
    SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation, workflow=first_created).update(position=20)
    SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation, workflow=second_created).update(position=10)
    IncidentWorkflow.objects.create(incident=incident, workflow=first_created)
    IncidentWorkflow.objects.create(incident=incident, workflow=second_created)
    return incident, [second_created, first_created]


@pytest.mark.django_db
def test_latest_incident_workflows_follow_workflow_position(incident_with_reversed_positions):
    incident, workflows_by_position = incident_with_reversed_positions

    reports = incident.get_latest_incident_workflows()

    assert [report.workflow for report in reports] == workflows_by_position


@pytest.mark.django_db
def test_latest_incident_workflows_keep_only_latest_report_per_workflow(incident_with_reversed_positions):
    incident, workflows_by_position = incident_with_reversed_positions
    resubmitted = IncidentWorkflow.objects.create(
        incident=incident,
        workflow=workflows_by_position[0],
        timestamp=timezone.now() + dt.timedelta(hours=1),
    )

    reports = list(incident.get_latest_incident_workflows())

    assert [report.workflow for report in reports] == workflows_by_position
    assert reports[0] == resubmitted


@pytest.mark.django_db
def test_latest_incident_workflows_kept_when_sector_regulation_removed(incident_with_reversed_positions):
    incident, workflows_by_position = incident_with_reversed_positions
    incident.sector_regulation = None
    incident.save()

    reports = incident.get_latest_incident_workflows()

    assert {report.workflow for report in reports} == set(workflows_by_position)


@pytest.fixture
def report_due_two_hours_after_notification(populate_incident_db):
    """The first report of an incident notified now, due two hours after the notification date."""
    incident = populate_incident_db["incidents"][0]
    report = SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation).order_by("position").first()
    report.trigger_event_before_deadline = "NOTIF_DATE"
    report.delay_in_hours_before_deadline = 2
    report.save()
    notified_at = timezone.now()
    incident.incident_notification_date = notified_at
    incident.save()
    return incident, report.workflow, notified_at


def submit(incident, workflow, at):
    return IncidentWorkflow.objects.create(incident=incident, workflow=workflow, timestamp=at)


@pytest.mark.django_db
def test_report_updated_after_deadline_stays_under_review_when_first_submitted_on_time(report_due_two_hours_after_notification):
    incident, workflow, notified_at = report_due_two_hours_after_notification
    submit(incident, workflow, notified_at + dt.timedelta(hours=1))

    update = submit(incident, workflow, notified_at + dt.timedelta(hours=5))

    assert update.review_status == "DELIV"


@pytest.mark.django_db
def test_report_updated_stays_late_when_first_submitted_late(report_due_two_hours_after_notification):
    incident, workflow, notified_at = report_due_two_hours_after_notification
    submit(incident, workflow, notified_at + dt.timedelta(hours=3))

    update = submit(incident, workflow, notified_at + dt.timedelta(hours=5))

    assert update.review_status == "LATE"


@pytest.mark.django_db
def test_report_revised_after_deadline_stays_under_review_when_first_submitted_on_time(report_due_two_hours_after_notification):
    incident, workflow, notified_at = report_due_two_hours_after_notification
    first = submit(incident, workflow, notified_at + dt.timedelta(hours=1))
    first.review_status = "FAIL"
    first.save()

    revision = submit(incident, workflow, notified_at + dt.timedelta(hours=5))

    assert revision.review_status == "DELIV"


@pytest.mark.django_db
def test_report_first_submitted_after_deadline_is_late(report_due_two_hours_after_notification):
    incident, workflow, notified_at = report_due_two_hours_after_notification

    first = submit(incident, workflow, notified_at + dt.timedelta(hours=3))

    assert first.review_status == "LATE"


@pytest.mark.django_db
def test_late_report_stays_late_after_previous_report_is_resubmitted(populate_incident_db):
    """A report due after the previous one keeps the deadline that applied when it was first submitted."""
    incident = populate_incident_db["incidents"][0]
    previous_report, report = SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation).order_by("position")
    report.trigger_event_before_deadline = "PREV_WORK"
    report.delay_in_hours_before_deadline = 2
    report.save()
    start = timezone.now()
    submit(incident, previous_report.workflow, start)
    submit(incident, report.workflow, start + dt.timedelta(hours=3))
    submit(incident, previous_report.workflow, start + dt.timedelta(hours=4))

    update = submit(incident, report.workflow, start + dt.timedelta(hours=5))

    assert update.review_status == "LATE"
