from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

import governanceplatform.tests.conftest as gp_conftest
from governanceplatform.models import Functionality
from reporting.models import CompanyReporting


@pytest.fixture
def populate_db(db):
    # on rewrap fixture to expose localy and don't get flake error
    return gp_conftest.populate_db.__wrapped__(db)


@pytest.fixture
def regulator_client(otp_client, populate_db):
    """A regulator administrator whose regulator has the reporting module."""
    user = next(u for u in populate_db["users"] if u.email == "regadmin@reg1.lu")
    user.regulators.first().functionalities.add(Functionality.objects.get(type="reporting"))
    return otp_client(user)


def stalled_import():
    result = MagicMock()
    result.ready.return_value = False
    result.completed_count.return_value = 0
    result.__len__.return_value = 1
    return patch("reporting.views.GroupResult.restore", return_value=result)


@pytest.mark.django_db
def test_import_is_refused_when_no_worker_reads_the_interactive_queue(regulator_client, populate_db, settings, tmp_path):
    """The import rewrites the reporting data before queuing, so it must not start without a worker."""
    settings.PRIVATE_FILES_ROOT = str(tmp_path)
    sector = next(s for s in populate_db["sectors"] if s.parent)

    with (
        patch("reporting.views.celery_health_check", return_value=False) as health_check,
        patch("reporting.views.group") as group,
    ):
        response = regulator_client.post(
            "/reporting/import_risk_analysis",
            {
                "company": populate_db["companies"][0].id,
                "sectors": [sector.id],
                "year": timezone.now().year,
                "import_file": SimpleUploadedFile("risk_analysis.json", b"{}", content_type="application/json"),
            },
        )

    assert response.status_code == 400
    assert "messages" in response.json()
    health_check.assert_called_once_with("interactive")
    group.assert_not_called()
    assert not CompanyReporting.objects.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.django_db
def test_status_fails_a_stalled_import_when_no_worker_reads_the_interactive_queue(regulator_client):
    with stalled_import(), patch("reporting.views.celery_health_check", return_value=False):
        response = regulator_client.get("/reporting/import_risk_analysis_status/group-id")

    assert response.json()["state"] == "FAILURE"
    assert "messages" in response.json()


@pytest.mark.django_db
def test_status_leaves_a_running_import_alone_when_a_worker_reads_the_queue(regulator_client):
    with stalled_import(), patch("reporting.views.celery_health_check", return_value=True):
        response = regulator_client.get("/reporting/import_risk_analysis_status/group-id")

    assert response.json()["state"] == "PROGRESS"
