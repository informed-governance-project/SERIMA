"""security_objective_exists: has this company filed an accepted declaration?

reporting/signals.py and securityobjectives/views.py both stamp CompanyProject rows from
this, so a wrong year or sector argument would silently mark companies as having
declared nothing.
"""

import pytest

from governanceplatform.models import Sector
from securityobjectives.helpers import security_objective_exists


@pytest.fixture
def submitted_answer(populate_so_db):
    """The fixture's standard answer, promoted to the accepted status."""
    answer = populate_so_db["sas"][0]
    answer.status = "PASSM"
    answer.save()
    return answer


@pytest.mark.django_db()
def test_finds_an_accepted_answer_for_the_year_and_sector(submitted_answer):
    company = submitted_answer.submitter_company
    sector = submitted_answer.sectors.first()

    assert security_objective_exists(company, submitted_answer.year_of_submission, sector) is True


@pytest.mark.django_db()
def test_ignores_an_answer_that_was_never_accepted(populate_so_db):
    """The fixture answer is DELIV, not PASSM, so it must not count."""
    answer = populate_so_db["sas"][0]

    assert security_objective_exists(answer.submitter_company, answer.year_of_submission, answer.sectors.first()) is False


@pytest.mark.django_db()
def test_ignores_another_year(submitted_answer):
    company = submitted_answer.submitter_company
    sector = submitted_answer.sectors.first()

    assert security_objective_exists(company, submitted_answer.year_of_submission + 1, sector) is False


@pytest.mark.django_db()
def test_ignores_a_sector_the_answer_does_not_cover(submitted_answer):
    """The fixture answer covers every seeded sector, so this needs a fresh one."""
    company = submitted_answer.submitter_company
    uncovered = Sector.objects.create(acronym="NEW")
    uncovered.set_current_language("en")
    uncovered.name = "Uncovered"
    uncovered.save()

    assert security_objective_exists(company, submitted_answer.year_of_submission, uncovered) is False


@pytest.mark.django_db()
def test_requires_both_a_year_and_a_sector(submitted_answer):
    company = submitted_answer.submitter_company
    sector = submitted_answer.sectors.first()

    assert security_objective_exists(company) is False
    assert security_objective_exists(company, submitted_answer.year_of_submission, None) is False
    assert security_objective_exists(company, None, sector) is False
