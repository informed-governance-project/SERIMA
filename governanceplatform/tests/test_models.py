from governanceplatform.helpers import user_in_group


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
    - test User::get_module_permissions according to the dataset
    """
    users = populate_db["users"]
    for user in users:
        if (
            user_in_group(user, "OperatorUser")
            or user_in_group(user, "OperatorAdmin")
            or user_in_group(user, "PlatformAdmin")
            or user_in_group(user, "IncidentUser")
            or user_in_group(user, "ObserverAdmin")
            or user_in_group(user, "ObserverUser")
        ):
            assert len(user.get_module_permissions()) == 0, f"User {user.email} should have no permission"
        if user_in_group(user, "RegulatorUser") or user_in_group(user, "RegulatorAdmin"):
            # REG1 has access to other modules
            if user.regulators.first().name == "REG1":
                assert len(user.get_module_permissions()) > 0, f"User {user.email} should have permission(s)"
            # REG2 doesn't have access to other module
            if user.regulators.first().name == "REG2":
                assert len(user.get_module_permissions()) == 0, f"User {user.email} should have no permission"
