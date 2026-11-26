import re

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from governanceplatform.models import Company, Sector
from reporting.models import (
    CompanyProject,
    CompanyReporting,
    Observation,
    ObservationRecommendation,
    ObservationRecommendationThrough,
    Project,
)
from reporting.tests.conftest import reporting_regulator

# Integer-keyed project, company-project and recommendation links and ids as the pages built them
# before #936. The lookahead keeps the all-zero placeholder UUID from counting as an integer.
SEQUENTIAL_ID_PATTERNS = [
    r"/reporting/(?:project|company_project|recommendations/update|access_log)/\d+(?![0-9a-fA-F-])",
    r'data-(?:project|company-project|recommendation)-id="\d+"',
    r"(?:\"|&quot;)(?:id|public_id)(?:\"|&quot;): \d+",
]


def company_project(project: Project, regulator) -> CompanyProject:
    return CompanyProject.objects.create(
        company=Company.objects.first(),
        project=project,
        sector=regulator.get_sectors().first(),
        year=2025,
        has_security_objectives=True,
        has_risk_assessment=True,
    )


def recommendation(sector: Sector) -> ObservationRecommendationThrough:
    company_reporting = CompanyReporting.objects.create(company=Company.objects.first(), sector=sector, year=2025)
    observation = Observation.objects.create(company_reporting=company_reporting)
    return ObservationRecommendationThrough.objects.create(
        observation=observation, observation_recommendation=ObservationRecommendation.objects.create(code="R1")
    )


def assert_no_sequential_id(content: str) -> None:
    for pattern in SEQUENTIAL_ID_PATTERNS:
        assert not re.search(pattern, content), pattern


@pytest.mark.django_db
def test_a_project_url_does_not_resolve_with_the_primary_key(otp_client, regulator, project):
    response = otp_client(regulator).get(f"/reporting/project/{project.pk}/dashboard")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_project_is_reached_by_its_public_id(otp_client, regulator, project):
    response = otp_client(regulator).get(reverse("dashboard_report_project", args=[project.public_id]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_project_list_never_shows_a_sequential_id(otp_client, regulator, project):
    Project.objects.filter(pk=project.pk).update(task_status="RUNNING")

    content = otp_client(regulator).get(reverse("reporting")).content.decode()

    assert str(project.public_id) in content
    assert_no_sequential_id(content)


@pytest.mark.django_db
def test_the_project_dashboard_never_shows_a_sequential_id(otp_client, regulator, project):
    row = company_project(project, regulator)

    content = otp_client(regulator).get(reverse("dashboard_report_project", args=[project.public_id])).content.decode()

    assert str(row.public_id) in content
    assert_no_sequential_id(content)


@pytest.mark.django_db
def test_a_company_project_is_updated_by_its_public_id(otp_client, regulator, project):
    row = company_project(project, regulator)

    url = reverse("update_company_project", args=[row.public_id])

    response = otp_client(regulator).post(url, {"field": "is_selected", "value": "true"})

    assert response.json()["company_project_id"] == str(row.public_id)
    row.refresh_from_db()
    assert row.is_selected


@pytest.mark.django_db
def test_the_recommendations_page_never_shows_a_sequential_id(otp_client, regulator):
    through = recommendation(regulator.get_sectors().first())
    company_reporting = through.observation.company_reporting
    url = reverse("report_recommendations", args=[company_reporting.company_id, company_reporting.sector_id, company_reporting.year])

    content = otp_client(regulator).get(url).content.decode()

    assert str(through.public_id) in content
    assert_no_sequential_id(content)


@pytest.mark.django_db
def test_a_recommendation_is_reordered_by_its_public_id(otp_client, regulator):
    through = recommendation(regulator.get_sectors().first())

    response = otp_client(regulator).post(reverse("update_report_recommendation", args=[through.public_id]), {"order": 4})

    assert response.json() == {"success": True}
    through.refresh_from_db()
    assert through.order == 4


@pytest.mark.django_db
def test_a_regulator_user_cannot_reorder_a_recommendation_outside_their_sectors(otp_client, populate_db):
    through = recommendation(Sector.objects.create(name="Unassigned"))
    regulator_user = reporting_regulator("reguser@reg1.lu")

    response = otp_client(regulator_user).post(reverse("update_report_recommendation", args=[through.public_id]), {"order": 4})

    assert response.status_code == 403
    through.refresh_from_db()
    assert through.order == 0


@pytest.mark.django_db
def test_another_regulator_cannot_read_the_generation_status(otp_client, other_regulator, project):
    response = otp_client(other_regulator).get(reverse("report_generation_status", args=[project.public_id]))

    assert response.status_code == 403


@pytest.mark.django_db
def test_another_regulator_cannot_cancel_the_generation(otp_client, other_regulator, project):
    Project.objects.filter(pk=project.pk).update(task_status="RUNNING")

    response = otp_client(other_regulator).post(reverse("cancel_report_generation", args=[project.public_id]))

    assert response.status_code == 403
    project.refresh_from_db()
    assert project.task_status == "RUNNING"


@pytest.mark.django_db(transaction=True)
def test_the_migration_keeps_project_ids_and_gives_each_row_its_own_public_id(regulator, project):
    company_project(project, regulator)
    company_project(Project.objects.create(**{**_project_fields(project), "name": "Second"}), regulator)
    recommendation(regulator.get_sectors().first())
    project_public_id = project.public_id

    before = ("reporting", "0024_project_api_id")
    after = ("reporting", "0027_alter_public_id_unique")
    executor = MigrationExecutor(connection)
    executor.migrate([before])
    try:
        executor = MigrationExecutor(connection)
        executor.migrate([after])
        apps = executor.loader.project_state([after]).apps

        assert apps.get_model("reporting", "Project").objects.get(pk=project.pk).public_id == project_public_id
        company_project_ids = list(apps.get_model("reporting", "CompanyProject").objects.values_list("public_id", flat=True))
        through_ids = list(apps.get_model("reporting", "ObservationRecommendationThrough").objects.values_list("public_id", flat=True))
        assert None not in company_project_ids + through_ids
        assert len(set(company_project_ids)) == 2
        assert len(through_ids) == 1
    finally:
        # Going back to `before` also unapplied every later migration; the teardown flush
        # needs the schema the current models describe.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


def _project_fields(project: Project) -> dict:
    return {
        field: getattr(project, field)
        for field in (
            "author",
            "standard",
            "reference_year",
            "years",
            "top_ranking",
            "threshold_for_high_risk",
            "selected_file_format",
            "selected_languages",
        )
    }
