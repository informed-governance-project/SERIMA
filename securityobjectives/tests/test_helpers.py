"""security_objective_exists: has this company filed an accepted declaration?

reporting/signals.py and securityobjectives/views.py both stamp CompanyProject rows from
this, so a wrong year or sector argument would silently mark companies as having
declared nothing.
"""

from types import SimpleNamespace

import pytest

from governanceplatform.models import Sector
from securityobjectives.globals import SO_COLUMN_GRID_TOTAL
from securityobjectives.helpers import (
    get_domain_symbol,
    get_objective_symbol,
    is_objective_open,
    security_objective_exists,
    set_declaration_column_widths,
)
from securityobjectives.models import StandardAnswer


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
    sector = submitted_answer.get_sectors().first()

    assert security_objective_exists(company, submitted_answer.year_of_submission, sector) is True


@pytest.mark.django_db()
def test_ignores_an_answer_that_was_never_accepted(populate_so_db):
    """The fixture answer is DELIV, not PASSM, so it must not count."""
    answer = populate_so_db["sas"][0]

    assert security_objective_exists(answer.submitter_company, answer.year_of_submission, answer.get_sectors().first()) is False


@pytest.mark.django_db()
def test_ignores_another_year(submitted_answer):
    company = submitted_answer.submitter_company
    sector = submitted_answer.get_sectors().first()

    assert security_objective_exists(company, submitted_answer.year_of_submission + 1, sector) is False


@pytest.mark.django_db()
def test_ignores_a_sector_the_answer_does_not_cover(submitted_answer):
    """The fixture company is in every seeded sector, so this needs a fresh one."""
    company = submitted_answer.submitter_company
    uncovered = Sector.objects.create(acronym="NEW")
    uncovered.set_current_language("en")
    uncovered.name = "Uncovered"
    uncovered.save()

    assert security_objective_exists(company, submitted_answer.year_of_submission, uncovered) is False


@pytest.mark.django_db()
def test_requires_both_a_year_and_a_sector(submitted_answer):
    company = submitted_answer.submitter_company
    sector = submitted_answer.get_sectors().first()

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


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        (["passed", "failed", "partially"], "failed"),
        (["passed", "passed"], "passed"),
        (["outline-uninitiated", "outline-uninitiated"], "outline-uninitiated"),
        (["passed", "outline-uninitiated"], "partially"),
        (["partially", "outline-uninitiated"], "partially"),
    ],
)
def test_operator_domain_symbol_follows_the_first_matching_rule(symbols, expected):
    assert get_domain_symbol(symbols, is_regulator=False) == expected


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        (["passed", "partially"], "partially"),
        (["passed", "failed"], "failed"),
        (["passed", "passed"], "passed"),
    ],
)
def test_regulator_domain_symbol_follows_the_first_matching_rule(symbols, expected):
    assert get_domain_symbol(symbols, is_regulator=True) == expected


def test_regulator_domain_stays_not_reviewed_until_its_review_is_complete():
    """A revision already required in the domain must not hide the objectives left to review."""
    assert get_domain_symbol(["failed", "partially"], is_regulator=True) == "partially"


@pytest.mark.parametrize(
    ("symbol", "is_regulator", "expected"),
    [
        ("passed", False, False),
        ("partially", False, True),
        ("outline-uninitiated", False, True),
        ("failed", False, True),
        ("partially", True, True),
        ("passed", True, False),
        ("failed", True, False),
    ],
)
def test_objective_is_open_until_filled_or_reviewed(symbol, is_regulator, expected):
    assert is_objective_open(symbol, is_regulator) is expected


def _objective(review_status=None, completed=False, partially=False):
    """The attributes the declaration view sets on each objective before it is drawn."""
    objective = SimpleNamespace(completion_state={"is_completed": completed, "is_partially": partially})
    if review_status:
        objective.status = SimpleNamespace(status=review_status)
    return objective


@pytest.mark.parametrize(
    ("objective", "expected"),
    [
        (_objective(completed=True), "passed"),
        (_objective(partially=True), "partially"),
        (_objective(), "outline-uninitiated"),
        (_objective("NOT_REVIEWED", completed=True), "passed"),
    ],
)
def test_operator_bullet_follows_the_filling_of_a_draft(objective, expected):
    assert get_objective_symbol(objective, StandardAnswer(status="UNDE"), is_regulator=False) == expected


@pytest.mark.parametrize(("review_status", "expected"), [("PASS", "passed"), ("FAIL", "failed")])
def test_operator_bullet_keeps_the_verdict_on_a_new_version(review_status, expected):
    """An objective the regulator already judged shows that verdict, not its filling."""
    assert get_objective_symbol(_objective(review_status, completed=True), StandardAnswer(status="UNDE"), is_regulator=False) == expected


def test_operator_bullet_follows_the_filling_while_the_review_is_in_progress():
    """The verdict reaches the operator only once the review is sent."""
    assert get_objective_symbol(_objective("FAIL", completed=True), StandardAnswer(status="DELIV"), is_regulator=False) == "passed"


@pytest.mark.parametrize(("review_status", "expected"), [("PASS", "passed"), ("FAIL", "failed"), ("NOT_REVIEWED", "partially")])
def test_regulator_bullet_shows_the_review(review_status, expected):
    assert get_objective_symbol(_objective(review_status, completed=True), StandardAnswer(status="DELIV"), is_regulator=True) == expected


@pytest.mark.parametrize(("stored_status", "review_status", "expected"), [("PASSM", "PASS", "passed"), ("FAILM", "FAIL", "failed")])
def test_operator_bullet_shows_the_verdict_once_the_review_is_sent(stored_status, review_status, expected):
    objective = _objective(review_status, completed=False)

    assert get_objective_symbol(objective, StandardAnswer(status=stored_status), is_regulator=False) == expected
