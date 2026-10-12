from importlib import import_module

import pytest
from django.db import IntegrityError

from governanceplatform.helpers import user_in_group
from governanceplatform.models import Sector

# the renaming runs once and lives with the migration that applies it
plan_acronym_renaming = import_module("governanceplatform.migrations.0069_unique_sector_acronym").plan_acronym_renaming


def test_user_group(populate_db):
    """
    Test User model
    - Assure that all the roles are properly linked to company, observers, and regulators
    """
    users = populate_db["users"]
    for user in users:
        if not user_in_group(user, "OperatorAdmin") and not user_in_group(user, "OperatorUser"):
            assert len(user.get_companies()) == 0, f"User {user.email} should not have company(ies)"
        if not user_in_group(user, "ObserverUser") and not user_in_group(user, "ObserverAdmin"):
            assert len(user.get_observers()) == 0, f"User {user.email} should not have observer(s)"
        if not user_in_group(user, "RegulatorUser") and not user_in_group(user, "RegulatorAdmin"):
            assert len(user.get_regulators()) == 0, f"User {user.email} should not have regulator(s)"
        if user_in_group(user, "OperatorUser") or user_in_group(user, "OperatorAdmin"):
            assert len(user.get_companies()) > 0, f"User {user.email} should have company(ies)"
        if user_in_group(user, "RegulatorUser") or user_in_group(user, "RegulatorAdmin"):
            assert len(user.get_regulators()) > 0, f"User {user.email} should have regulator(s)"
        if user_in_group(user, "ObserverUser") or user_in_group(user, "ObserverAdmin"):
            assert len(user.get_observers()) > 0, f"User {user.email} should have observer(s)"


def test_user_functionnalities(populate_db):
    """
    Test User model
    - test User::get_module_permissions according to the dataset, where every eligible role is enabled
    """
    users = populate_db["users"]
    for user in users:
        if (
            user_in_group(user, "PlatformAdmin")
            or user_in_group(user, "IncidentUser")
            or user_in_group(user, "ObserverAdmin")
            or user_in_group(user, "ObserverUser")
        ):
            assert len(user.get_module_permissions()) == 0, f"User {user.email} should have no permission"
        # Operators have no entity switch, so their enabled role is enough
        if user_in_group(user, "OperatorUser") or user_in_group(user, "OperatorAdmin"):
            assert user.get_module_permissions() == ["securityobjectives"], f"User {user.email} should have SO"
        if user_in_group(user, "RegulatorUser") or user_in_group(user, "RegulatorAdmin"):
            # REG1 has access to other modules
            if user.regulators.first().name == "REG1":
                assert len(user.get_module_permissions()) > 0, f"User {user.email} should have permission(s)"
            # REG2 doesn't have access to other module
            if user.regulators.first().name == "REG2":
                assert len(user.get_module_permissions()) == 0, f"User {user.email} should have no permission"


def test_distinct_acronyms_are_not_renamed():
    assert plan_acronym_renaming([(1, "ENE"), (2, "TRA"), (3, "HEAL")]) == {}


def test_the_earliest_sector_of_a_duplicated_group_keeps_its_acronym():
    renaming = plan_acronym_renaming([(9, "ENE"), (4, "ENE")])

    assert 4 not in renaming
    assert renaming[9] == "ENE1"


def test_a_duplicated_acronym_at_max_length_has_its_last_letter_replaced():
    assert plan_acronym_renaming([(1, "HEAL"), (2, "HEAL")]) == {2: "HEA1"}


def test_the_digit_goes_up_until_the_acronym_is_free():
    renaming = plan_acronym_renaming([(1, "ENE"), (2, "ENE"), (3, "ENE"), (4, "ENE2")])

    assert renaming == {2: "ENE1", 3: "ENE3"}


@pytest.mark.django_db
def test_two_sectors_cannot_share_an_acronym():
    sector = Sector(acronym="ZZZ")
    sector.set_current_language("en")
    sector.name = "First"
    sector.save()

    duplicate = Sector(acronym="ZZZ")
    duplicate.set_current_language("en")
    duplicate.name = "Second"
    with pytest.raises(IntegrityError):
        duplicate.save()
