from unittest.mock import patch

import pytest

import celery_worker
from governanceplatform.helpers import celery_health_check

# Every task, with the queue it must land on. A new task fails test_every_task_has_a_queue
# until it is added here, so that its queue is a decision rather than a default.
EXPECTED_QUEUES = {
    # A user is waiting on a spinner.
    "incidents.tasks.generate_incident_pdf_task": "interactive",
    "securityobjectives.tasks.generate_declaration_pdf_task": "interactive",
    "securityobjectives.tasks.generate_so_export_task": "interactive",
    "reporting.tasks.import_risk_analysis_task": "interactive",
    # Report generation, holding Kaleido and LibreOffice.
    "reporting.tasks.generate_data": "reports",
    "reporting.tasks.generate_docx_task": "reports",
    "reporting.tasks.generate_pdf_task": "reports",
    "reporting.tasks.save_file_task": "reports",
    "reporting.tasks.zip_files_task": "reports",
    "reporting.tasks.on_chord_error": "reports",
    "reporting.tasks.cleanup_files": "reports",
    # Scheduled jobs and cleanups.
    "clean_incident_user": "celery",
    "email_reminder": "celery",
    "incident_cleaning": "celery",
    "log_cleaning": "celery",
    "so_declarations_cleaning": "celery",
    "unactive_account_cleaning": "celery",
    "workflow_update_status": "celery",
    "governanceplatform.tasks.cleanup_async_pdf_file": "celery",
    "reporting.tasks.cleanup_ra_tmp_file_task": "celery",
    "reporting.tasks.delete_project_task": "celery",
    "securityobjectives.tasks.cleanup_old_export_files": "celery",
    "securityobjectives.tasks.cleanup_so_export_file": "celery",
    "securityobjectives.tasks.cleanup_unconfirmed_import_file": "celery",
    "import_export_extensions.tasks.export_data_task": "celery",
    "import_export_extensions.tasks.import_data_task": "celery",
    "import_export_extensions.tasks.parse_data_task": "celery",
}


@pytest.fixture(scope="module")
def worker_app():
    """The worker's app, with its tasks registered as a running worker has them."""
    app = celery_worker.app
    app.loader.import_default_modules()
    return app


def test_every_task_has_a_queue(worker_app):
    registered = {name for name in worker_app.tasks if not name.startswith("celery.")}

    assert registered == set(EXPECTED_QUEUES)


@pytest.mark.parametrize(("task_name", "queue"), EXPECTED_QUEUES.items())
def test_task_is_routed_to_its_queue(worker_app, task_name, queue):
    assert worker_app.amqp.router.route({}, task_name)["queue"].name == queue


def test_a_worker_without_queue_option_consumes_every_queue(worker_app):
    """Installations that never pass -Q must keep running every task after the upgrade."""
    assert set(worker_app.amqp.queues) == {"interactive", "reports", "celery"}


def active_queues(*names):
    return {"worker@host": [{"name": name} for name in names]}


def test_health_check_passes_when_a_worker_reads_the_queue():
    with (
        patch("governanceplatform.helpers.current_app.control.inspect") as inspect,
        patch("governanceplatform.helpers.is_redis_available", return_value=True),
    ):
        inspect.return_value.active_queues.return_value = active_queues("interactive", "celery")

        assert celery_health_check("interactive") is True


def test_health_check_fails_when_only_other_queues_are_read():
    """A reports worker answering must not hide that no interactive worker is running."""
    with (
        patch("governanceplatform.helpers.current_app.control.inspect") as inspect,
        patch("governanceplatform.helpers.is_redis_available", return_value=True),
    ):
        inspect.return_value.active_queues.return_value = active_queues("reports")

        assert celery_health_check("interactive") is False


def test_health_check_fails_when_no_worker_answers():
    with (
        patch("governanceplatform.helpers.current_app.control.inspect") as inspect,
        patch("governanceplatform.helpers.is_redis_available", return_value=True),
    ):
        inspect.return_value.active_queues.return_value = None

        assert celery_health_check("interactive") is False


def test_health_check_fails_when_the_broker_is_unreachable():
    with patch("governanceplatform.helpers.current_app.control.inspect", side_effect=ConnectionError("broker down")):
        assert celery_health_check("interactive") is False
