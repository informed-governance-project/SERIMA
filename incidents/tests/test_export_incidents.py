import csv
import datetime
import io

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import activate

from governanceplatform.models import RegulatorUser
from incidents.models import IncidentWorkflow, ReportTimeline, SectorRegulation, Workflow

REGULATION_ID = 2
SECTOR_REGULATION_ID = 1
REPORT_ID = 1


@pytest.fixture
def exporting_client(otp_client, populate_incident_db):
    """A regulator administrator allowed to export, with the second factor satisfied."""
    user = next(u for u in populate_incident_db["users"] if u.email == "regadmin@reg1.lu")
    RegulatorUser.objects.filter(user=user).update(
        is_regulator_administrator=True,
        can_export_incidents=True,
    )
    return otp_client(user)


def submit_report(incident, submitted_at, review_status="PASS"):
    """Submit the report the export is asked for."""
    return IncidentWorkflow.objects.create(
        incident=incident,
        workflow=Workflow.objects.get(pk=REPORT_ID),
        timestamp=submitted_at,
        review_status=review_status,
        report_timeline=ReportTimeline.objects.create(incident_detection_date=submitted_at),
    )


def notified_on(incident, notified_at):
    incident.incident_notification_date = notified_at
    incident.sector_regulation = SectorRegulation.objects.get(pk=SECTOR_REGULATION_ID)
    incident.save()
    return incident


def export(client, from_date, to_date, **options):
    payload = {
        "regulation": REGULATION_ID,
        "sectorregulation": SECTOR_REGULATION_ID,
        "workflow": REPORT_ID,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "file_format": "csv",
    }
    payload.update(options)
    return client.post(reverse("export_incidents"), payload)


def references(response):
    rows = csv.DictReader(io.StringIO(response.content.decode()))
    return {row["Reference"] for row in rows}


@pytest.mark.django_db
def test_the_chosen_report_is_exported(exporting_client, populate_incident_db):
    activate("en")
    today = timezone.now().date()
    incident = notified_on(populate_incident_db["incidents"][0], timezone.now())
    submit_report(incident, timezone.now())

    response = export(exporting_client, today - datetime.timedelta(days=1), today)

    assert response.status_code == 200
    assert references(response) == {incident.incident_id}


@pytest.mark.django_db
def test_a_report_awaiting_revision_is_exported_when_no_status_is_asked_for(exporting_client, populate_incident_db):
    """Current behaviour, kept: the option has to be asked for."""
    activate("en")
    today = timezone.now().date()
    incident = notified_on(populate_incident_db["incidents"][0], timezone.now())
    submit_report(incident, timezone.now(), review_status="FAIL")

    response = export(exporting_client, today - datetime.timedelta(days=1), today)

    assert references(response) == {incident.incident_id}


@pytest.mark.django_db
def test_review_status_restricts_the_export(exporting_client, populate_incident_db):
    """A periodic filing wants finished reports, not those sent back for revision."""
    activate("en")
    today = timezone.now().date()
    passed, revised = populate_incident_db["incidents"][:2]
    submit_report(notified_on(passed, timezone.now()), timezone.now(), review_status="PASS")
    submit_report(notified_on(revised, timezone.now()), timezone.now(), review_status="FAIL")

    response = export(exporting_client, today - datetime.timedelta(days=1), today, review_status="PASS")

    assert references(response) == {passed.incident_id}


@pytest.mark.django_db
def test_dates_apply_to_the_incident_notification_by_default(exporting_client, populate_incident_db):
    """An incident notified before the window stays out of it, however late its report is."""
    activate("en")
    today = timezone.now().date()
    incident = notified_on(populate_incident_db["incidents"][0], timezone.now() - datetime.timedelta(days=100))
    submit_report(incident, timezone.now())

    response = export(exporting_client, today - datetime.timedelta(days=30), today)

    assert response.status_code == 400


@pytest.mark.django_db
def test_dates_can_apply_to_the_report_instead(exporting_client, populate_incident_db):
    """The report filed late lands in the period it was filed in, and only there."""
    activate("en")
    today = timezone.now().date()
    late = notified_on(populate_incident_db["incidents"][0], timezone.now() - datetime.timedelta(days=100))
    submit_report(late, timezone.now())
    old = notified_on(populate_incident_db["incidents"][1], timezone.now() - datetime.timedelta(days=100))
    submit_report(old, timezone.now() - datetime.timedelta(days=100))

    response = export(exporting_client, today - datetime.timedelta(days=30), today, date_basis="report")

    assert response.status_code == 200
    assert references(response) == {late.incident_id}
