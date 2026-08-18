"""
Regression tests for incidents left without a SectorRegulation.

Incident.sector_regulation uses on_delete=SET_NULL, so deleting a SectorRegulation
leaves incidents behind with sector_regulation = NULL. The list views hide them, but
the single-incident action views load them with a bare Incident.objects.get(pk=...),
so every helper they reach has to degrade instead of raising AttributeError.
"""

import pytest

from governanceplatform.helpers import can_edit_incident_report
from incidents.helpers import is_deadline_exceeded
from incidents.models import IncidentWorkflow, SectorRegulationWorkflow, Workflow


@pytest.fixture
def orphaned_incident(populate_incident_db):
    """An incident whose SectorRegulation has been removed."""
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")
    incident.sector_regulation = None
    incident.save()
    return incident


@pytest.mark.django_db()
def test_get_previous_workflow_returns_false_when_sector_regulation_removed(orphaned_incident):
    """
    Incident.get_previous_workflow must honour its False contract rather than
    dereferencing the .first() lookup, which matches nothing without a regulation.
    """
    workflow = Workflow.objects.first()

    assert orphaned_incident.get_previous_workflow(workflow) is False


@pytest.mark.django_db()
def test_is_deadline_exceeded_is_undetermined_when_sector_regulation_removed(orphaned_incident):
    """No regulation means no SectorRegulationWorkflow, so no deadline can be computed."""
    workflow = Workflow.objects.first()

    assert is_deadline_exceeded(workflow, orphaned_incident) == "UNDE"


@pytest.mark.django_db()
def test_can_edit_incident_report_denies_when_sector_regulation_removed(orphaned_incident, populate_incident_db):
    """
    A regulator admin reaching an orphaned incident must be denied, not met with a 500.
    The regulator branches compare against sector_regulation.regulator, which is absent.
    """
    regulator_admin = next(u for u in populate_incident_db["users"] if u.email == "regadmin@reg1.lu")

    assert can_edit_incident_report(regulator_admin, orphaned_incident, None) is False


@pytest.mark.django_db()
def test_is_deadline_exceeded_handles_report_without_timeline(populate_incident_db):
    """
    IncidentWorkflow.report_timeline is also SET_NULL. When the detection date has to be
    read off the previous report, a missing timeline must not raise.
    """
    incident = next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")

    sector_regulation = incident.sector_regulation
    sector_regulation.is_detection_date_needed = False
    sector_regulation.save()

    reports = list(sector_regulation.workflows.order_by("sectorregulationworkflow__position"))
    filled_report, pending_report = reports[0], reports[1]

    SectorRegulationWorkflow.objects.filter(
        sector_regulation=sector_regulation,
        workflow=pending_report,
    ).update(trigger_event_before_deadline="DETECT_DATE")

    # report_timeline is left NULL, as it is for a report whose timeline was deleted.
    IncidentWorkflow.objects.create(incident=incident, workflow=filled_report)

    assert is_deadline_exceeded(pending_report, incident) == "UNDE"
