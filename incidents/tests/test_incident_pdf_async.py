from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from kombu.exceptions import OperationalError

from governanceplatform.models import CompanyUser
from incidents.globals import INCIDENT_PDF_SESSION_KEY
from incidents.models import IncidentWorkflow, LogReportRead
from incidents.pdf_generation import get_pdf_file_path
from incidents.tasks import cleanup_incident_pdf_file, generate_incident_pdf_task


def get_user(populate_incident_db, email):
    return next(u for u in populate_incident_db["users"] if u.email == email)


def get_operator_incident(populate_incident_db):
    return next(i for i in populate_incident_db["incidents"] if i.incident_id == "XXXX-SSS-SSS-0001-2005")


def create_incident_workflow(populate_incident_db):
    incident = get_operator_incident(populate_incident_db)
    return IncidentWorkflow.objects.create(incident=incident, workflow=populate_incident_db["incidents_reports"][0])


def queue_pdf(client, url):
    """Ask for a PDF the way the browser does, and return the queued task's id and arguments."""
    task_id = str(uuid4())
    with patch("incidents.views.generate_incident_pdf_task.delay") as delay:
        delay.return_value.id = task_id
        response = client.post(url)
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id}
    return task_id, delay.call_args.args


def run_task(task_id, args):
    with patch("incidents.tasks.cleanup_incident_pdf_file.apply_async"):
        return generate_incident_pdf_task.apply(args=args, task_id=task_id)


def mock_result(successful=False, ready=False):
    result = MagicMock()
    result.successful.return_value = successful
    result.ready.return_value = ready
    return patch("incidents.views.generate_incident_pdf_task.AsyncResult", return_value=result)


@pytest.mark.django_db
def test_get_no_longer_produces_a_pdf(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)

    assert client.get(f"/incidents/download-pdf/{incident.id}").status_code == 405


@pytest.mark.django_db
def test_an_unknown_incident_is_not_queued(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))

    with patch("incidents.views.generate_incident_pdf_task.delay") as delay:
        response = client.post("/incidents/download-pdf/999999")

    assert response.status_code == 404
    delay.assert_not_called()


@pytest.mark.django_db
def test_a_dead_broker_reports_an_error(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)

    with patch("incidents.views.generate_incident_pdf_task.delay", side_effect=OperationalError("broker down")):
        response = client.post(f"/incidents/download-pdf/{incident.id}")

    assert response.status_code == 400
    assert "messages" in response.json()
    assert INCIDENT_PDF_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_report_pdf_is_queued_with_its_workflow(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident_workflow = create_incident_workflow(populate_incident_db)

    _, args = queue_pdf(client, f"/incidents/download-incident-report-pdf/{incident_workflow.id}")

    assert args[:2] == (incident_workflow.incident.id, incident_workflow.id)


@pytest.mark.django_db
def test_an_unknown_report_is_not_queued(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))

    with patch("incidents.views.generate_incident_pdf_task.delay") as delay:
        response = client.post("/incidents/download-incident-report-pdf/999999")

    assert response.status_code == 404
    delay.assert_not_called()


@pytest.mark.django_db
def test_a_report_outside_the_user_scope_is_not_queued(otp_client, populate_incident_db):
    # reguser@reg1.lu has no sector in common with the asectorial incident.
    client = otp_client(get_user(populate_incident_db, "reguser@reg1.lu"))
    incident_workflow = create_incident_workflow(populate_incident_db)

    with patch("incidents.views.generate_incident_pdf_task.delay") as delay:
        response = client.post(f"/incidents/download-incident-report-pdf/{incident_workflow.id}")

    assert response.status_code == 403
    delay.assert_not_called()


@pytest.mark.django_db
def test_status_of_a_task_from_another_session_is_not_found(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))

    with mock_result(successful=True):
        response = client.get(f"/incidents/pdf/{uuid4()}/status")

    assert response.status_code == 404


@pytest.mark.django_db
def test_status_reports_a_finished_pdf(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)
    task_id, _ = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")

    with mock_result(successful=True, ready=True):
        response = client.get(f"/incidents/pdf/{task_id}/status")

    assert response.json() == {"status": "SUCCESS"}


@pytest.mark.django_db
def test_status_leaves_a_running_task_alone_when_the_stack_is_healthy(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)
    task_id, _ = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")

    with mock_result(), patch("incidents.views.celery_health_check", return_value=True):
        response = client.get(f"/incidents/pdf/{task_id}/status")

    assert response.json() == {"status": "PENDING"}


@pytest.mark.django_db
def test_status_fails_a_running_task_when_the_stack_is_down(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)
    task_id, _ = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")

    with mock_result(), patch("incidents.views.celery_health_check", return_value=False):
        response = client.get(f"/incidents/pdf/{task_id}/status")

    assert response.json()["status"] == "FAILURE"
    assert task_id not in client.session[INCIDENT_PDF_SESSION_KEY]


@pytest.mark.django_db
def test_status_reports_a_failed_task(otp_client, populate_incident_db):
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)
    task_id, _ = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")

    with mock_result(ready=True):
        response = client.get(f"/incidents/pdf/{task_id}/status")

    assert response.json()["status"] == "FAILURE"
    assert "messages" in response.json()


@pytest.mark.django_db
def test_task_writes_the_incident_pdf(otp_client, populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident = get_operator_incident(populate_incident_db)
    task_id, args = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")

    result = run_task(task_id, args)

    assert result.successful()
    assert Path(get_pdf_file_path(task_id)).read_bytes().startswith(b"%PDF")


@pytest.mark.django_db
def test_task_writes_the_report_pdf(otp_client, populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    incident_workflow = create_incident_workflow(populate_incident_db)
    task_id, args = queue_pdf(client, f"/incidents/download-incident-report-pdf/{incident_workflow.id}")

    result = run_task(task_id, args)

    assert result.successful()
    assert Path(get_pdf_file_path(task_id)).read_bytes().startswith(b"%PDF")


@pytest.mark.django_db
def test_task_schedules_the_cleanup_of_its_file(populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    incident = get_operator_incident(populate_incident_db)
    task_id = str(uuid4())

    with patch("incidents.tasks.cleanup_incident_pdf_file.apply_async") as apply_async:
        generate_incident_pdf_task.apply(args=(incident.id, None, "en"), task_id=task_id)

    apply_async.assert_called_once_with(kwargs={"task_id": task_id}, countdown=3600)


@pytest.mark.django_db
def test_a_failed_task_writes_no_file(populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    incident = get_operator_incident(populate_incident_db)
    task_id = str(uuid4())

    with patch("incidents.tasks.get_pdf_report", side_effect=OSError("font missing")):
        result = run_task(task_id, (incident.id, None, "en"))

    assert result.failed()
    assert not Path(get_pdf_file_path(task_id)).exists()


@pytest.mark.django_db
def test_download_serves_the_pdf_once_and_logs_it(otp_client, populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    user = get_user(populate_incident_db, "regadmin@reg1.lu")
    client = otp_client(user)
    incident = get_operator_incident(populate_incident_db)
    task_id, args = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")
    run_task(task_id, args)

    response = client.get(f"/incidents/pdf/{task_id}/download")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert f"Incident_{incident.incident_id}_" in response["Content-Disposition"]
    assert b"".join(response.streaming_content).startswith(b"%PDF")
    assert not Path(get_pdf_file_path(task_id)).exists()
    assert LogReportRead.objects.filter(user=user, incident=incident, action="DOWNLOAD").count() == 1
    assert client.get(f"/incidents/pdf/{task_id}/download").status_code == 404


@pytest.mark.django_db
def test_download_is_refused_to_another_user(otp_client, populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    incident = get_operator_incident(populate_incident_db)
    client = otp_client(get_user(populate_incident_db, "regadmin@reg1.lu"))
    task_id, args = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")
    run_task(task_id, args)

    client = otp_client(get_user(populate_incident_db, "opadmin@com1.lu"))

    assert client.get(f"/incidents/pdf/{task_id}/download").status_code == 404
    assert Path(get_pdf_file_path(task_id)).exists()


@pytest.mark.django_db
def test_download_is_refused_when_access_was_revoked(otp_client, populate_incident_db, settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    user = get_user(populate_incident_db, "opadmin@com1.lu")
    client = otp_client(user)
    incident = get_operator_incident(populate_incident_db)
    task_id, args = queue_pdf(client, f"/incidents/download-pdf/{incident.id}")
    run_task(task_id, args)

    CompanyUser.objects.filter(user=user).update(approved=False)
    response = client.get(f"/incidents/pdf/{task_id}/download")

    assert response.status_code == 302
    assert not Path(get_pdf_file_path(task_id)).exists()
    assert not LogReportRead.objects.filter(user=user, action="DOWNLOAD").exists()


def test_cleanup_tolerates_an_already_downloaded_file(settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)

    cleanup_incident_pdf_file(str(uuid4()))


def test_cleanup_removes_an_abandoned_file(settings, tmp_path):
    settings.PATH_FOR_REPORTING_PDF = str(tmp_path)
    task_id = str(uuid4())
    file_path = Path(get_pdf_file_path(task_id))
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"%PDF")

    cleanup_incident_pdf_file(task_id)

    assert not file_path.exists()
