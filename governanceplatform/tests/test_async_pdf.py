from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.http import Http404
from django.test import RequestFactory

from governanceplatform.async_pdf import ASYNC_PDF_SESSION_KEY, get_pdf_file_path, get_pdf_task
from governanceplatform.tasks import cleanup_async_pdf_file, store_async_pdf


def request_with_pending_pdfs(pending_pdfs):
    request = RequestFactory().get("/")
    request.session = {ASYNC_PDF_SESSION_KEY: pending_pdfs}
    return request


def test_store_writes_the_pdf_and_schedules_its_cleanup(settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    task_id = str(uuid4())

    with patch("governanceplatform.tasks.cleanup_async_pdf_file.apply_async") as apply_async:
        store_async_pdf(task_id, b"%PDF-1.7")

    assert Path(get_pdf_file_path(task_id)).read_bytes() == b"%PDF-1.7"
    apply_async.assert_called_once_with(kwargs={"task_id": task_id}, countdown=3600)


def test_cleanup_removes_an_abandoned_file(settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    task_id = str(uuid4())
    file_path = Path(get_pdf_file_path(task_id))
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"%PDF")

    cleanup_async_pdf_file(task_id)

    assert not file_path.exists()


def test_cleanup_tolerates_an_already_downloaded_file(settings, tmp_path):
    settings.PRIVATE_FILES_ROOT = str(tmp_path)

    cleanup_async_pdf_file(str(uuid4()))


def test_a_task_is_found_under_its_own_kind():
    task_id = str(uuid4())
    request = request_with_pending_pdfs({task_id: {"kind": "incident", "filename": "a.pdf"}})

    assert get_pdf_task(request, "incident", task_id)["filename"] == "a.pdf"


def test_a_task_is_refused_under_another_kind():
    """One module's download view must not be handed another module's task."""
    task_id = str(uuid4())
    request = request_with_pending_pdfs({task_id: {"kind": "incident", "filename": "a.pdf"}})

    with pytest.raises(Http404):
        get_pdf_task(request, "security_objective", task_id)


def test_an_unknown_task_is_refused():
    with pytest.raises(Http404):
        get_pdf_task(request_with_pending_pdfs({}), "incident", str(uuid4()))
