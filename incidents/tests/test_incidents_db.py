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
