import datetime as dt
import json

import pytest
from django.urls import reverse
from django.utils import timezone

from governanceplatform.models import Sector
from incidents.forms import ImpactForm
from incidents.models import IncidentWorkflow, ReportTimeline, SectorRegulation, Workflow


@pytest.fixture
def sectorial_incident(populate_incident_db, create_incident):
    """An operator incident on the NIS workflow, whose two reports disclose impacts."""
    operator = next(u for u in populate_incident_db["users"] if u.email == "opadmin@com1.lu")
    sector_regulation = SectorRegulation.objects.get(id=2)
    sectors = Sector.objects.filter(acronym__in=["GAS", "ELEC"])
    incident = create_incident(
        user=operator,
        workflow=sector_regulation,
        sectors=sectors,
        incident_id="XXXX-SSS-SSS-0002-2005",
        incident_detection_date=timezone.now(),
    )
    impacts = {}
    for impact in populate_incident_db["incidents_impacts"]:
        impact.regulations.set([sector_regulation.regulation])
        impact.sectors.set(sectors)
        impacts[str(impact.label)] = impact
    return incident, impacts


def create_report(incident, workflow_id, impacts, minutes_ago):
    incident_workflow = IncidentWorkflow.objects.create(
        incident=incident,
        workflow=Workflow.objects.get(id=workflow_id),
        report_timeline=ReportTimeline.objects.create(),
        timestamp=timezone.now() - dt.timedelta(minutes=minutes_ago),
    )
    incident_workflow.impacts.set(impacts)
    return incident_workflow


def impacts_widget(incident, incident_workflow):
    return ImpactForm(incident=incident, incident_workflow=incident_workflow).fields["impacts"].widget


@pytest.mark.django_db
def test_impacts_changed_since_the_previous_report_are_flagged(sectorial_incident):
    incident, impacts = sectorial_incident
    create_report(incident, 3, [impacts["impact1"]], minutes_ago=10)
    final = create_report(incident, 4, [impacts["impact2"]], minutes_ago=0)

    assert "answer-modified" in impacts_widget(incident, final).attrs["class"]


@pytest.mark.django_db
def test_the_previous_version_lists_the_impacts_selected_in_the_previous_report(sectorial_incident):
    incident, impacts = sectorial_incident
    create_report(incident, 3, [impacts["impact1"]], minutes_ago=10)
    final = create_report(incident, 4, [impacts["impact2"]], minutes_ago=0)

    previous = json.loads(impacts_widget(incident, final).attrs["data-previous-choices"])

    checked = {option["label"] for sector in previous["children"] for option in sector["options"] if option["checked"]}
    assert checked == {"impact1"}


@pytest.mark.django_db
def test_unchanged_impacts_are_not_flagged(sectorial_incident):
    incident, impacts = sectorial_incident
    create_report(incident, 3, [impacts["impact1"]], minutes_ago=10)
    final = create_report(incident, 4, [impacts["impact1"]], minutes_ago=0)

    assert "answer-modified" not in impacts_widget(incident, final).attrs.get("class", "")


@pytest.mark.django_db
def test_impacts_of_the_first_report_are_not_flagged(sectorial_incident):
    incident, impacts = sectorial_incident
    preliminary = create_report(incident, 3, [impacts["impact1"]], minutes_ago=0)

    assert "answer-modified" not in impacts_widget(incident, preliminary).attrs.get("class", "")


@pytest.mark.django_db
def test_an_earlier_report_without_impacts_step_is_not_compared(sectorial_incident):
    incident, impacts = sectorial_incident
    preliminary = create_report(incident, 3, [], minutes_ago=10)
    Workflow.objects.filter(pk=preliminary.workflow_id).update(is_impact_needed=False)
    final = create_report(incident, 4, [impacts["impact1"]], minutes_ago=0)

    assert "answer-modified" not in impacts_widget(incident, final).attrs.get("class", "")


@pytest.mark.django_db
def test_the_markers_are_rendered_once_on_the_impacts_container(sectorial_incident):
    incident, impacts = sectorial_incident
    create_report(incident, 3, [impacts["impact1"]], minutes_ago=10)
    final = create_report(incident, 4, [impacts["impact2"]], minutes_ago=0)

    html = str(ImpactForm(incident=incident, incident_workflow=final)["impacts"])

    assert html.count("data-previous-choices") == 1
    assert html.count("answer-modified") == 1


@pytest.mark.django_db
def test_regulator_review_shows_the_impacts_of_the_reviewed_report_as_modified(otp_client, sectorial_incident, populate_incident_db):
    incident, impacts = sectorial_incident
    create_report(incident, 3, [impacts["impact1"]], minutes_ago=10)
    final = create_report(incident, 4, [impacts["impact2"]], minutes_ago=0)
    regulator = next(u for u in populate_incident_db["users"] if u.email == "regadmin@reg2.lu")
    client = otp_client(regulator)
    url = f"{reverse('edit_workflow')}?incident_workflow_id={final.public_id}"

    response = client.get(url)
    impacts_step = str(response.context["wizard"]["steps"].count - 2)
    response = client.post(url, {"workflow_wizard_view-current_step": "0", "wizard_goto_step": impacts_step})

    widget = response.context["wizard"]["form"].fields["impacts"].widget
    assert widget.initial_data == [impacts["impact2"].id]
    assert impacts_step in response.context["modified_steps"]
