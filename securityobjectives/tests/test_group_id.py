import pytest
from django.db import IntegrityError, transaction

from governanceplatform.globals import CROCKFORD_ALPHABET, REFERENCE_TOKEN_LENGTH
from securityobjectives.filters import StandardAnswerFilter
from securityobjectives.globals import REFERENCE_PREFIX
from securityobjectives.models import StandardAnswer, StandardAnswerGroup


@pytest.mark.django_db
def test_a_new_group_gets_a_crockford_id():
    group = StandardAnswerGroup.objects.create()

    assert group.group_id.startswith(REFERENCE_PREFIX)
    token = group.group_id.removeprefix(REFERENCE_PREFIX)
    assert len(token) == REFERENCE_TOKEN_LENGTH
    assert set(token) <= set(CROCKFORD_ALPHABET)


@pytest.mark.django_db
def test_two_groups_do_not_share_an_id():
    first = StandardAnswerGroup.objects.create()
    second = StandardAnswerGroup.objects.create()

    assert first.group_id != second.group_id


@pytest.mark.django_db
def test_a_group_without_a_company_gets_its_own_id():
    """The number used to come from the company's existing groups, so a declaration
    created without one was always numbered 0001 and the second could not be saved."""
    first = StandardAnswerGroup.objects.create(company=None)
    second = StandardAnswerGroup.objects.create(company=None)

    assert first.group_id != second.group_id


@pytest.mark.django_db
def test_the_database_rejects_a_duplicate_group_id():
    group = StandardAnswerGroup.objects.create()

    with pytest.raises(IntegrityError), transaction.atomic():
        StandardAnswerGroup.objects.create(group_id=group.group_id)


@pytest.mark.django_db
def test_a_group_id_does_not_depend_on_the_language_of_the_session():
    """The framework segment was taken from a translated label, so the same standard
    produced a different id depending on the language the declaration was created in."""
    from django.utils.translation import override

    with override("fr"):
        french = StandardAnswerGroup.objects.create()
    with override("en"):
        english = StandardAnswerGroup.objects.create()

    assert set(french.group_id.removeprefix(REFERENCE_PREFIX)) <= set(CROCKFORD_ALPHABET)
    assert set(english.group_id.removeprefix(REFERENCE_PREFIX)) <= set(CROCKFORD_ALPHABET)


def search_declarations(value: str) -> list[StandardAnswer]:
    return list(StandardAnswerFilter(data={"search": value}, queryset=StandardAnswer.objects.all(), is_regulator=True).qs)


@pytest.fixture
def declaration(populate_so_db):
    answer = StandardAnswer.objects.first()
    answer.group.group_id = "SO_K7V2XQ10"
    answer.group.save()
    return answer


@pytest.mark.django_db
def test_a_declaration_is_found_by_its_group_id_whatever_its_case(declaration):
    assert declaration in search_declarations("so_k7v2xq10")


@pytest.mark.django_db
@pytest.mark.parametrize("typed", ["SO_K7V2XQ1O", "SO_K7V2XQI0", "SO_K7V2XQL0", "SO_K7U2XQ10", "S0_K7V2XQ10"])
def test_a_group_id_typed_with_a_lookalike_character_is_not_found(declaration, typed):
    """The search is strict (#948): a letter typed for a digit, or a zero for the O of
    the prefix, is not read as the character it resembles."""
    assert declaration not in search_declarations(typed)
