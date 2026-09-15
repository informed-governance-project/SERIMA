import pytest
from django.db import IntegrityError, transaction

from governanceplatform.globals import CROCKFORD_ALPHABET, REFERENCE_TOKEN_LENGTH
from securityobjectives.models import StandardAnswerGroup


@pytest.mark.django_db
def test_a_new_group_gets_a_crockford_id():
    group = StandardAnswerGroup.objects.create()

    assert len(group.group_id) == REFERENCE_TOKEN_LENGTH
    assert set(group.group_id) <= set(CROCKFORD_ALPHABET)


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

    assert set(french.group_id) <= set(CROCKFORD_ALPHABET)
    assert set(english.group_id) <= set(CROCKFORD_ALPHABET)
