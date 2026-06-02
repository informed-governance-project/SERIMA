import pytest

from governanceplatform.helpers import user_in_group
from governanceplatform.models import (
    User,
)


@pytest.mark.django_db(transaction=True)
def test_add_user_via_admin(otp_client, populate_db):
    """
    Test that when a user creates another via the admin interface,
    the new user's role is correct depending on the creator.
    """
    users = populate_db["users"]
    url = "/admin/governanceplatform/user/add/"

    # role mapping creator --> creation
    role_mapping = {
        "PlatformAdmin": "PlatformAdmin",
        "RegulatorAdmin": "RegulatorUser",
        "RegulatorUser": "OperatorUser",
        "OperatorAdmin": "OperatorUser",
        "ObserverAdmin": "ObserverUser",
    }

    for index, creator in enumerate(users, start=1):
        # new user data
        email = f"new_user{index}@nisinp.lu"
        data = {
            "email": email,
            "first_name": "test",
            "last_name": "test",
        }

        client = otp_client(creator)

        # check if the user is in a group who can create a user
        creator_group = next((group for group in role_mapping if user_in_group(creator, group)), None)
        if not creator_group:
            continue

        expected_group = role_mapping[creator_group]

        response = client.post(url, data, follow=True)
        assert response.status_code == 200
        created_user = User.objects.get(email=email)
        assert user_in_group(created_user, expected_group), f"{creator_group} → {expected_group} expected, but got something else"
