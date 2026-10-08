"""security_objective_exists: has this company filed an accepted declaration?

reporting/signals.py and securityobjectives/views.py both stamp CompanyProject rows from
this, so a wrong year or sector argument would silently mark companies as having
declared nothing.
"""

import pytest

from governanceplatform.models import Sector
from securityobjectives.globals import SO_COLUMN_GRID_TOTAL
from securityobjectives.helpers import security_objective_exists, set_declaration_column_widths


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


def _config(hidden=()):
    """A column config with the named columns hidden."""
    from securityobjectives.globals import SO_DECLARATION_COLUMNS

    return {key: {"label": str(column["label"]), "visible": key not in hidden} for key, column in SO_DECLARATION_COLUMNS.items()}


@pytest.mark.parametrize(
    ("hidden", "expected"),
    [
        ((), {"maturity_level": 1, "security_measure": 3, "evidence": 3, "is_implemented": 1, "justification": 2, "review_comment": 2}),
        (("review_comment",), {"maturity_level": 1, "security_measure": 4, "evidence": 4, "is_implemented": 1, "justification": 2}),
        (("maturity_level",), {"security_measure": 4, "evidence": 3, "is_implemented": 1, "justification": 2, "review_comment": 2}),
        (("evidence",), {"maturity_level": 1, "security_measure": 4, "is_implemented": 1, "justification": 3, "review_comment": 3}),
        (("maturity_level", "evidence"), {"security_measure": 5, "is_implemented": 1, "justification": 3, "review_comment": 3}),
        (("maturity_level", "evidence", "review_comment"), {"security_measure": 6, "is_implemented": 2, "justification": 4}),
    ],
)
def test_visible_columns_are_widened_in_proportion_to_their_original_width(hidden, expected):
    config = set_declaration_column_widths(_config(hidden))

    assert {key: column["width"] for key, column in config.items() if column["visible"]} == expected


def test_a_wider_column_gains_more_than_a_narrower_one():
    """Proportional means the share of the freed width follows the original width."""
    base = _config()
    set_declaration_column_widths(base)
    widened = set_declaration_column_widths(_config(("review_comment",)))

    measure_gain = widened["security_measure"]["width"] - base["security_measure"]["width"]
    implemented_gain = widened["is_implemented"]["width"] - base["is_implemented"]["width"]

    assert measure_gain > implemented_gain


def test_no_column_is_ever_narrower_than_when_the_whole_table_is_shown():
    """Scaling only ever grows a column, so none can round away to nothing."""
    from securityobjectives.globals import SO_DECLARATION_COLUMNS

    for hidden in [(), ("review_comment",), ("maturity_level",), ("evidence",), ("maturity_level", "evidence")]:
        config = set_declaration_column_widths(_config(hidden))
        for key, column in config.items():
            if column["visible"]:
                assert column["width"] >= SO_DECLARATION_COLUMNS[key]["width"]


def test_a_fully_shown_table_keeps_the_widths_it_always_had():
    """The default layout must be untouched by the width calculation."""
    config = set_declaration_column_widths(_config())

    assert {key: column["width"] for key, column in config.items()} == {
        "maturity_level": 1,
        "security_measure": 3,
        "evidence": 3,
        "is_implemented": 1,
        "justification": 2,
        "review_comment": 2,
    }


@pytest.mark.parametrize(
    "hidden",
    [
        (),
        ("review_comment",),
        ("maturity_level",),
        ("evidence",),
        ("maturity_level", "evidence"),
        ("maturity_level", "review_comment"),
        ("evidence", "review_comment"),
        ("maturity_level", "evidence", "review_comment"),
    ],
)
def test_visible_columns_always_span_the_full_grid(hidden):
    """A row that does not total 12 either overhangs the table or under-fills it."""
    config = set_declaration_column_widths(_config(hidden))

    spanned = sum(column["width"] for column in config.values() if column["visible"])

    assert spanned == SO_COLUMN_GRID_TOTAL
