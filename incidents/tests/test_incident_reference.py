from importlib import import_module

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from governanceplatform.globals import CROCKFORD_ALPHABET, REFERENCE_TOKEN_LENGTH
from governanceplatform.helpers import build_crockford_token, normalize_crockford, normalize_reference
from incidents.filters import reference_matches
from incidents.globals import REFERENCE_PREFIX
from incidents.models import Incident

# the renumbering runs once and lives with the migration that applies it
renumbering_migration = import_module("incidents.migrations.0068_renumber_duplicate_references")
parse_legacy_reference = renumbering_migration.parse_legacy_reference
plan_reference_renumbering = renumbering_migration.plan_reference_renumbering


@pytest.mark.django_db
def test_a_new_incident_gets_a_crockford_reference():
    incident = Incident.objects.create()

    assert incident.incident_id.startswith(REFERENCE_PREFIX)
    token = incident.incident_id.removeprefix(REFERENCE_PREFIX)
    assert len(token) == REFERENCE_TOKEN_LENGTH
    assert set(token) <= set(CROCKFORD_ALPHABET)


def test_a_reference_never_contains_a_character_read_as_another():
    tokens = "".join(build_crockford_token() for _ in range(200))

    assert not set(tokens) & set("ILOU")


@pytest.mark.django_db
def test_two_incidents_do_not_share_a_reference():
    first = Incident.objects.create()
    second = Incident.objects.create()

    assert first.incident_id != second.incident_id


@pytest.mark.django_db
def test_an_incident_without_a_company_gets_its_own_reference():
    """References used to be numbered from a count of the company's incidents, which
    fell back to 0001 for every incident notified for an unregistered entity."""
    first = Incident.objects.create(company=None, company_name="Unverified entity")
    second = Incident.objects.create(company=None, company_name="Unverified entity")

    assert first.incident_id != second.incident_id


@pytest.mark.django_db
def test_deleting_an_incident_does_not_free_its_reference():
    """The count the reference was built from dropped back when an incident was
    deleted, so the next one was handed a number already in use."""
    first = Incident.objects.create()
    reference = first.incident_id
    second = Incident.objects.create()
    second.delete()

    third = Incident.objects.create()

    assert third.incident_id not in (reference, second.incident_id)


@pytest.mark.django_db
def test_the_database_rejects_a_duplicate_reference():
    incident = Incident.objects.create()

    with pytest.raises(IntegrityError), transaction.atomic():
        Incident.objects.create(incident_id=incident.incident_id)


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("OP1_Enr_Elc_0007_2026", ("OP1_Enr_Elc", 7, 2026)),
        ("REGULATOR_Wat_DWa_0006_2026", ("REGULATOR_Wat_DWa", 6, 2026)),
        # an operator acronym can carry an underscore of its own
        ("test_compa_Enr_Gas_0001_2026", ("test_compa_Enr_Gas", 1, 2026)),
        # an incident notified without a sector leaves those segments empty
        ("ILR__0002_2026", ("ILR_", 2, 2026)),
    ],
)
def test_a_legacy_reference_is_split_into_its_parts(reference, expected):
    assert parse_legacy_reference(reference) == expected


@pytest.mark.parametrize(
    "reference",
    [
        "OP1_Enr_Elc_0007_2026",
        "REGULATOR_Wat_DWa_0006_2026",
        "test_compa_Enr_Gas_0001_2026",
        "ILR__0002_2026",
    ],
)
def test_a_renumbered_duplicate_keeps_the_shape_of_its_siblings(reference):
    renumbering = plan_reference_renumbering([(1, reference), (2, reference)])

    prefix, number, year = parse_legacy_reference(reference)
    assert renumbering[2] == f"{prefix}_{number + 1:04}_{year}"


@pytest.mark.parametrize(
    "reference",
    ["", "K7M2XQ4P", "FOO-ENE-ELE-0012-2026", "FOO_ENE_ELE_ABCD_2026", "FOO_ENE_ELE_0012_26"],
)
def test_a_reference_that_is_not_in_the_legacy_format_is_not_parsed(reference):
    assert parse_legacy_reference(reference) is None


def test_a_transcribed_reference_is_read_back_as_crockford_intends():
    assert normalize_crockford("k7m2xq4o") == "K7M2XQ40"
    assert normalize_crockford("IL") == "11"


@pytest.mark.django_db
def test_a_reference_is_found_when_a_zero_was_transcribed_as_a_letter():
    incident = Incident.objects.create(incident_id="K7M2XQ40")

    found = Incident.objects.filter(reference_matches("k7m2xq4o"))

    assert list(found) == [incident]


@pytest.mark.django_db
def test_a_legacy_reference_is_still_found_by_its_company_acronym():
    """Normalising the search input must not turn the O of a company acronym into a
    zero, or the legacy references stop being searchable."""
    incident = Incident.objects.create(incident_id="FOO_ENE_ELE_0012_2026")

    found = Incident.objects.filter(reference_matches("FOO"))

    assert list(found) == [incident]


def test_renumbering_leaves_a_reference_that_is_used_once_alone():
    references = [(1, "FOO_ENE_ELE_0001_2026"), (2, "FOO_ENE_ELE_0002_2026")]

    assert plan_reference_renumbering(references) == {}


def test_the_earliest_incident_of_a_duplicated_group_keeps_its_reference():
    references = [(7, "FOO_ENE_ELE_0003_2026"), (12, "FOO_ENE_ELE_0003_2026")]

    renumbering = plan_reference_renumbering(references)

    assert 7 not in renumbering
    assert renumbering[12] == "FOO_ENE_ELE_0004_2026"


def test_a_renumbered_incident_continues_its_own_series():
    references = [
        (1, "FOO_ENE_ELE_0003_2026"),
        (2, "FOO_ENE_ELE_0003_2026"),
        (3, "FOO_ENE_ELE_0009_2026"),
        (4, "BAR_ENE_ELE_0001_2026"),
    ]

    renumbering = plan_reference_renumbering(references)

    assert renumbering == {2: "FOO_ENE_ELE_0010_2026"}


def test_renumbering_keeps_the_year_the_reference_was_issued_under():
    """A reference restamped with the approval year no longer matches its notification
    date; correcting that would change the reference more than freeing it does."""
    references = [(1, "FOO_ENE_ELE_0003_2025"), (2, "FOO_ENE_ELE_0003_2025")]

    assert plan_reference_renumbering(references)[2].endswith("_2025")


def test_every_duplicate_of_a_group_is_given_its_own_reference():
    references = [
        (1, "FOO_ENE_ELE_0001_2026"),
        (2, "FOO_ENE_ELE_0001_2026"),
        (3, "FOO_ENE_ELE_0001_2026"),
    ]

    renumbering = plan_reference_renumbering(references)

    assert sorted(renumbering) == [2, 3]
    assert len(set(renumbering.values())) == 2


def test_a_hand_edited_duplicate_is_given_an_opaque_token():
    references = [(1, "FOO-ENE-ELE-0003-2026"), (2, "FOO-ENE-ELE-0003-2026")]

    renumbering = plan_reference_renumbering(references)

    assert renumbering[2].startswith(REFERENCE_PREFIX)
    token = renumbering[2].removeprefix(REFERENCE_PREFIX)
    assert len(token) == REFERENCE_TOKEN_LENGTH
    assert set(token) <= set(CROCKFORD_ALPHABET)


def test_renumbering_never_reuses_a_reference_already_held_by_another_incident():
    references = [
        (1, "FOO_ENE_ELE_0003_2026"),
        (2, "FOO_ENE_ELE_0003_2026"),
        (3, "FOO_ENE_ELE_0004_2026"),
    ]

    renumbering = plan_reference_renumbering(references)

    assert renumbering[2] != "FOO_ENE_ELE_0004_2026"
    assert renumbering[2] == "FOO_ENE_ELE_0005_2026"


@pytest.mark.django_db(transaction=True)
def test_the_migration_frees_the_duplicates_already_in_the_database():
    """The renumbering runs once, against real rows, and nothing rehearses it first."""
    before = ("incidents", "0067_delete_orphan_report_timelines")
    after = ("incidents", "0069_alter_incident_incident_id")

    executor = MigrationExecutor(connection)
    executor.migrate([before])
    historical_incident = executor.loader.project_state([before]).apps.get_model("incidents", "Incident")
    kept = historical_incident.objects.create(incident_id="FOO_ENE_ELE_0003_2026")
    renumbered = historical_incident.objects.create(incident_id="FOO_ENE_ELE_0003_2026")

    MigrationExecutor(connection).migrate([after])

    assert historical_incident.objects.get(pk=kept.pk).incident_id == "FOO_ENE_ELE_0003_2026"
    assert historical_incident.objects.get(pk=renumbered.pk).incident_id == "FOO_ENE_ELE_0004_2026"


@pytest.mark.django_db
def test_a_prefixed_reference_is_found_after_a_transcription_slip():
    """Normalising the whole value would read the I of the prefix as a 1, and the
    reference the operator quoted would stop matching."""
    incident = Incident.objects.create(incident_id="NI_K7M2XQ40")

    found = Incident.objects.filter(reference_matches("NI_K7M2XQ4O"))

    assert list(found) == [incident]


def test_the_prefix_survives_normalisation():
    assert normalize_reference("ni_k7m2xq4o", REFERENCE_PREFIX) == "NI_K7M2XQ40"
