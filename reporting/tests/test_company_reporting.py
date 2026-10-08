"""The two per-company reporting lookups that used to be Company methods.

Both take (company, year, sector) positionally and every caller passes them that way, so
a swapped year and sector would return a plausible empty result rather than raising.
"""

import pytest

from governanceplatform.models import Company, Sector
from reporting.helpers import get_report_recommandations, risk_analysis_exists
from reporting.models import (
    AssetData,
    CompanyReporting,
    Observation,
    ObservationRecommendation,
    ObservationRecommendationThrough,
    ServiceStat,
)

YEAR = 2025


@pytest.fixture
def company(db):
    return Company.objects.create(identifier="TC1", name="Test Company")


@pytest.fixture
def sector(db):
    sector = Sector.objects.create(acronym="ELEC")
    sector.set_current_language("en")
    sector.name = "Electricity"
    sector.save()
    return sector


@pytest.fixture
def reporting_row(company, sector):
    return CompanyReporting.objects.create(company=company, year=YEAR, sector=sector)


def _service_stat(reporting_row):
    """ServiceStat.service points at reporting's own AssetData, not Service."""
    asset = AssetData.objects.create()
    asset.set_current_language("en")
    asset.name = "Grid"
    asset.save()
    return ServiceStat.objects.create(service=asset, company_reporting=reporting_row)


@pytest.mark.django_db()
def test_risk_analysis_needs_both_a_year_and_a_sector(company, sector):
    assert risk_analysis_exists(company) is False
    assert risk_analysis_exists(company, YEAR, None) is False
    assert risk_analysis_exists(company, None, sector) is False


@pytest.mark.django_db()
def test_risk_analysis_requires_service_statistics(reporting_row, company, sector):
    """A reporting row on its own is not a risk analysis; it needs a ServiceStat."""
    assert risk_analysis_exists(company, YEAR, sector) is False

    _service_stat(reporting_row)

    assert risk_analysis_exists(company, YEAR, sector) is True


@pytest.mark.django_db()
def test_risk_analysis_ignores_another_year(reporting_row, company, sector):
    _service_stat(reporting_row)

    assert risk_analysis_exists(company, YEAR + 1, sector) is False


@pytest.mark.django_db()
def test_recommendations_are_returned_in_order(reporting_row, company, sector):
    observation = Observation.objects.create(company_reporting=reporting_row)
    for order in (2, 0, 1):
        recommendation = ObservationRecommendation.objects.create(code=f"R{order}")
        recommendation.set_current_language("en")
        recommendation.save()
        ObservationRecommendationThrough.objects.create(
            observation=observation,
            observation_recommendation=recommendation,
            order=order,
        )

    result = get_report_recommandations(company, YEAR, sector)

    assert [row.order for row in result] == [0, 1, 2]


@pytest.mark.django_db()
def test_empty_results_are_always_recommendation_querysets(company, sector, reporting_row):
    """Every branch returns the same model, so a caller may filter the result.

    The empty branches used to hand back a CompanyReporting queryset instead.
    """
    no_arguments = get_report_recommandations(company)
    no_observation = get_report_recommandations(company, YEAR, sector)
    no_reporting_row = get_report_recommandations(company, YEAR + 1, sector)

    for result in (no_arguments, no_observation, no_reporting_row):
        assert result.model is ObservationRecommendationThrough
        assert list(result) == []
