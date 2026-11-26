import re
from uuid import uuid4

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from incidents.models import Incident, IncidentWorkflow, ReportTimeline, SectorRegulationWorkflow, Workflow


def get_incident(populate_incident_db, reference: str) -> Incident:
    return next(i for i in populate_incident_db["incidents"] if i.incident_id == reference)


def get_user(populate_incident_db, email: str):
    return next(u for u in populate_incident_db["users"] if u.email == email)


def operator_client(otp_client, populate_incident_db, incident: Incident):
    client = otp_client(get_user(populate_incident_db, "opadmin@com1.lu"))
    session = client.session
    session["company_in_use"] = incident.company_id
    session.save()
    return client


def first_report(incident: Incident) -> Workflow:
    return SectorRegulationWorkflow.objects.filter(sector_regulation=incident.sector_regulation).order_by("position").first().workflow


@pytest.mark.django_db
def test_a_report_is_started_by_the_incident_public_id(otp_client, populate_incident_db):
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    client = operator_client(otp_client, populate_incident_db, incident)

    response = client.get(reverse("create_workflow"), {"incident_id": incident.public_id, "workflow_id": first_report(incident).pk})

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_report_start_does_not_accept_the_incident_primary_key(otp_client, populate_incident_db):
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    client = operator_client(otp_client, populate_incident_db, incident)

    response = client.get(reverse("create_workflow"), {"incident_id": incident.pk, "workflow_id": first_report(incident).pk})

    assert response.status_code == 302
    assert response.url == reverse("incidents")


@pytest.mark.django_db
def test_a_report_is_edited_by_the_incident_public_id(otp_client, populate_incident_db):
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    report = first_report(incident)
    IncidentWorkflow.objects.create(incident=incident, workflow=report, report_timeline=ReportTimeline.objects.create())
    client = operator_client(otp_client, populate_incident_db, incident)

    response = client.get(reverse("edit_workflow"), {"incident_id": incident.public_id, "workflow_id": report.pk})

    assert response.status_code == 200


@pytest.mark.django_db
def test_an_incident_is_deleted_by_its_public_id(otp_client, populate_incident_db):
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    client = operator_client(otp_client, populate_incident_db, incident)

    response = client.post(reverse("delete_incident", args=[incident.public_id]))

    assert response.status_code == 302
    assert not Incident.objects.filter(pk=incident.pk).exists()


@pytest.mark.django_db
def test_an_incident_delete_with_the_primary_key_deletes_nothing(otp_client, populate_incident_db):
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    client = operator_client(otp_client, populate_incident_db, incident)

    response = client.post(f"/incidents/delete/{incident.pk}")

    assert response.status_code == 404
    assert Incident.objects.filter(pk=incident.pk).exists()


@pytest.mark.django_db
def test_an_incident_url_does_not_resolve_with_the_primary_key(otp_client, populate_incident_db):
    operator = get_user(populate_incident_db, "opadmin@com1.lu")
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")

    response = otp_client(operator).get(f"/incidents/access_log/{incident.pk}")

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_incident_is_reached_by_its_public_id(otp_client, populate_incident_db):
    operator = get_user(populate_incident_db, "opadmin@com1.lu")
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")

    response = otp_client(operator).get(reverse("access_log", args=[incident.public_id]))

    assert response.status_code == 200
    assert response.context["incident"] == incident


@pytest.mark.django_db
def test_an_unknown_public_id_is_not_found(otp_client, populate_incident_db):
    operator = get_user(populate_incident_db, "opadmin@com1.lu")

    response = otp_client(operator).get(reverse("access_log", args=[uuid4()]))

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["", "1", "not-a-uuid"])
def test_a_report_review_with_a_malformed_id_sends_back_to_the_list(otp_client, populate_incident_db, value):
    operator = get_user(populate_incident_db, "opadmin@com1.lu")

    response = otp_client(operator).get(reverse("review_workflow"), {"incident_workflow_id": value})

    assert response.status_code == 302
    assert response.url == reverse("incidents")


@pytest.mark.django_db
def test_a_report_review_does_not_accept_the_primary_key(otp_client, populate_incident_db):
    operator = get_user(populate_incident_db, "opadmin@com1.lu")
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    incident_workflow = IncidentWorkflow.objects.create(
        incident=incident, workflow=populate_incident_db["incidents_reports"][0], report_timeline=ReportTimeline.objects.create()
    )

    response = otp_client(operator).get(reverse("review_workflow"), {"incident_workflow_id": incident_workflow.pk})

    assert response.status_code == 302
    assert response.url == reverse("incidents")


@pytest.mark.django_db
def test_a_report_review_opens_by_public_id(otp_client, populate_incident_db):
    operator = get_user(populate_incident_db, "opadmin@com1.lu")
    incident = get_incident(populate_incident_db, "XXXX-SSS-SSS-0001-2005")
    incident_workflow = IncidentWorkflow.objects.create(
        incident=incident, workflow=populate_incident_db["incidents_reports"][0], report_timeline=ReportTimeline.objects.create()
    )

    response = otp_client(operator).get(reverse("review_workflow"), {"incident_workflow_id": incident_workflow.public_id})

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_status_change_answers_with_the_public_id(otp_client, populate_incident_db):
    regulator_admin = get_user(populate_incident_db, "regadmin@reg1.lu")
    incident = get_incident(populate_incident_db, "RRR-SSS-SSS-0001-2005")

    response = otp_client(regulator_admin).post(reverse("regulator_incident_edit", args=[incident.public_id]), {"incident_status": "GOING"})

    assert response.status_code == 200
    assert response.json()["id"] == str(incident.public_id)


# Integer-keyed incident links and element ids as the pages built them before #936. The lookahead
# keeps the all-zero placeholder UUID the templates reverse from counting as an integer.
SEQUENTIAL_ID_PATTERNS = [
    r"/incidents/(?:incident|access_log|download-pdf|download-incident-report-pdf|delete)/\d+(?![0-9a-fA-F-])",
    r"[?&](?:incident_id|incident_workflow_id)=\d+(?![0-9a-fA-F-])",
    r"(?:incident|impact)_status_\d+(?![0-9a-fA-F-])",
    r"is_significative_impact_\d+(?![0-9a-fA-F-])",
    r'data-incident-id="\d+"',
    r"(?:\"|&quot;)id(?:\"|&quot;): \d+",
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("email", "url_name", "session"),
    [
        ("opadmin@com1.lu", "incidents", {}),
        ("regadmin@reg1.lu", "incidents", {}),
        ("regadmin@reg1.lu", "regulator_incidents", {"is_regulator_incidents": True}),
        ("obsadm@cert1.lu", "incidents", {}),
    ],
)
def test_the_incident_lists_never_show_a_sequential_id(otp_client, populate_incident_db, email, url_name, session):
    for incident in populate_incident_db["incidents"]:
        IncidentWorkflow.objects.create(
            incident=incident, workflow=populate_incident_db["incidents_reports"][0], report_timeline=ReportTimeline.objects.create()
        )
    client = otp_client(get_user(populate_incident_db, email))
    if session:
        client_session = client.session
        client_session.update(session)
        client_session.save()

    response = client.get(reverse(url_name))

    assert response.status_code == 200
    content = response.content.decode()
    assert any(str(incident.public_id) in content for incident in populate_incident_db["incidents"])
    for pattern in SEQUENTIAL_ID_PATTERNS:
        assert not re.search(pattern, content), pattern


@pytest.mark.django_db(transaction=True)
def test_the_migration_gives_each_existing_row_its_own_public_id():
    before = ("incidents", "0074_email_content_markdown_to_html")
    after = ("incidents", "0077_alter_public_id_unique")

    executor = MigrationExecutor(connection)
    executor.migrate([before])
    apps = executor.loader.project_state([before]).apps
    historical_incident = apps.get_model("incidents", "Incident")
    historical_incident_workflow = apps.get_model("incidents", "IncidentWorkflow")
    historical_report_timeline = apps.get_model("incidents", "ReportTimeline")
    incidents = [historical_incident.objects.create(incident_id=f"LEGACY_{n}") for n in range(3)]
    for incident in incidents:
        historical_incident_workflow.objects.create(incident=incident, report_timeline=historical_report_timeline.objects.create())

    try:
        executor = MigrationExecutor(connection)
        executor.migrate([after])
        apps = executor.loader.project_state([after]).apps

        incident_ids = list(apps.get_model("incidents", "Incident").objects.values_list("public_id", flat=True))
        workflow_ids = list(apps.get_model("incidents", "IncidentWorkflow").objects.values_list("public_id", flat=True))
        assert None not in incident_ids + workflow_ids
        assert len(set(incident_ids)) == len(incidents)
        assert len(set(workflow_ids)) == len(incidents)
    finally:
        # Going back to `before` also unapplied every later migration; the teardown flush
        # needs the schema the current models describe.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
