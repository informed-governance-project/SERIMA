from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from kombu.exceptions import OperationalError

from governanceplatform.async_pdf import ASYNC_PDF_SESSION_KEY, get_pdf_file_path
from securityobjectives.models import LogStandardAnswer, StandardAnswer
from securityobjectives.tasks import generate_declaration_pdf_task


def get_user(populate_so_db, email):
    return next(u for u in populate_so_db["users"] if u.email == email)


def login(otp_client, populate_so_db, email):
    """Log in, with the declaration's company active for an operator."""
    client = otp_client(get_user(populate_so_db, email))
    session = client.session
    session["company_in_use"] = populate_so_db["sas"][0].submitter_company_id
    session.save()
    return client


def pdf_url(populate_so_db):
    return f"/securityobjectives/download/{populate_so_db['sas'][0].id}"


def queue_pdf(client, url):
    """Ask for a PDF the way the browser does, and return the queued task's id and arguments."""
    task_id = str(uuid4())
    with patch("securityobjectives.views.generate_declaration_pdf_task.delay") as delay:
        delay.return_value.id = task_id
        response = client.post(url)
    assert response.status_code == 200
    assert response.json() == {
        "task_id": task_id,
        "status_url": f"/securityobjectives/pdf/{task_id}/status",
        "download_url": f"/securityobjectives/pdf/{task_id}/download",
    }
    return task_id, delay.call_args.args


def run_task(task_id, args):
    with patch("governanceplatform.tasks.cleanup_async_pdf_file.apply_async"):
        return generate_declaration_pdf_task.apply(args=args, task_id=task_id)


@pytest.mark.django_db
def test_get_no_longer_produces_a_pdf(otp_client, populate_so_db):
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")

    assert client.get(pdf_url(populate_so_db)).status_code == 405


@pytest.mark.django_db
def test_the_task_renders_for_the_requesting_user(otp_client, populate_so_db):
    """The review-comment column depends on who asks, so the task must know the user."""
    user = get_user(populate_so_db, "regadmin@reg1.lu")
    client = login(otp_client, populate_so_db, user.email)

    _, args = queue_pdf(client, pdf_url(populate_so_db))

    assert args[:2] == (populate_so_db["sas"][0].id, user.id)


@pytest.mark.django_db
def test_an_unknown_declaration_is_not_queued(otp_client, populate_so_db):
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")

    with patch("securityobjectives.views.generate_declaration_pdf_task.delay") as delay:
        response = client.post("/securityobjectives/download/999999")

    assert response.status_code == 404
    delay.assert_not_called()


@pytest.mark.django_db
def test_a_draft_declaration_is_not_queued_for_a_regulator(otp_client, populate_so_db):
    StandardAnswer.objects.filter(pk=populate_so_db["sas"][0].id).update(status="UNDE")
    client = login(otp_client, populate_so_db, "regadmin@reg1.lu")

    with patch("securityobjectives.views.generate_declaration_pdf_task.delay") as delay:
        response = client.post(pdf_url(populate_so_db))

    assert response.status_code == 403
    assert "messages" in response.json()
    delay.assert_not_called()


@pytest.mark.django_db
def test_a_dead_broker_reports_an_error(otp_client, populate_so_db):
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")

    with patch("securityobjectives.views.generate_declaration_pdf_task.delay", side_effect=OperationalError("broker down")):
        response = client.post(pdf_url(populate_so_db))

    assert response.status_code == 400
    assert ASYNC_PDF_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_status_reports_a_finished_pdf(otp_client, populate_so_db):
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")
    task_id, _ = queue_pdf(client, pdf_url(populate_so_db))
    result = MagicMock()
    result.successful.return_value = True

    with patch("governanceplatform.views.AsyncResult", return_value=result):
        response = client.get(f"/securityobjectives/pdf/{task_id}/status")

    assert response.json() == {"status": "SUCCESS"}


@pytest.mark.django_db
def test_task_writes_the_declaration_pdf(otp_client, populate_so_db, settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")
    task_id, args = queue_pdf(client, pdf_url(populate_so_db))

    result = run_task(task_id, args)

    assert result.successful(), result.traceback
    assert Path(get_pdf_file_path(task_id)).read_bytes().startswith(b"%PDF")


@pytest.mark.django_db
def test_download_serves_the_pdf_once_and_logs_it(otp_client, populate_so_db, settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    user = get_user(populate_so_db, "opadmin@com1.lu")
    client = login(otp_client, populate_so_db, user.email)
    task_id, args = queue_pdf(client, pdf_url(populate_so_db))
    run_task(task_id, args)

    response = client.get(f"/securityobjectives/pdf/{task_id}/download")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "Security_objective_declaration_" in response["Content-Disposition"]
    assert b"".join(response.streaming_content).startswith(b"%PDF")
    assert not Path(get_pdf_file_path(task_id)).exists()
    assert LogStandardAnswer.objects.filter(user=user, action="DOWNLOAD").count() == 1
    assert client.get(f"/securityobjectives/pdf/{task_id}/download").status_code == 404


@pytest.mark.django_db
def test_download_is_refused_to_another_user(otp_client, populate_so_db, settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")
    task_id, args = queue_pdf(client, pdf_url(populate_so_db))
    run_task(task_id, args)

    client = login(otp_client, populate_so_db, "regadmin@reg1.lu")

    assert client.get(f"/securityobjectives/pdf/{task_id}/download").status_code == 404
    assert Path(get_pdf_file_path(task_id)).exists()


@pytest.mark.django_db
def test_download_is_refused_when_access_was_revoked(otp_client, populate_so_db, settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    user = get_user(populate_so_db, "regadmin@reg1.lu")
    client = login(otp_client, populate_so_db, user.email)
    task_id, args = queue_pdf(client, pdf_url(populate_so_db))
    run_task(task_id, args)

    StandardAnswer.objects.filter(pk=populate_so_db["sas"][0].id).update(status="UNDE")
    response = client.get(f"/securityobjectives/pdf/{task_id}/download")

    assert response.status_code == 302
    assert not Path(get_pdf_file_path(task_id)).exists()
    assert not LogStandardAnswer.objects.filter(user=user, action="DOWNLOAD").exists()


@pytest.mark.django_db
def test_an_incident_task_cannot_be_downloaded_as_a_declaration(otp_client, populate_so_db, settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    client = login(otp_client, populate_so_db, "opadmin@com1.lu")
    task_id = str(uuid4())
    session = client.session
    session[ASYNC_PDF_SESSION_KEY] = {task_id: {"kind": "incident", "incident_id": 1, "filename": "x.pdf"}}
    session.save()

    assert client.get(f"/securityobjectives/pdf/{task_id}/download").status_code == 404
