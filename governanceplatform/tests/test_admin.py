import pytest

from governanceplatform.helpers import user_in_group
from governanceplatform.models import (
    ApplicationConfig,
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
        email = f"new_user{index}@serima.exemple.lu"
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


def assert_add_user_rejects_email(client, email):
    user_count = User.objects.count()

    response = client.post(
        "/admin/governanceplatform/user/add/",
        {"email": email, "first_name": "test", "last_name": "test"},
    )

    assert response.status_code == 200
    assert "email" in response.context["adminform"].form.errors
    assert User.objects.count() == user_count


@pytest.mark.django_db
def test_add_user_via_admin_rejects_existing_email_in_other_case(otp_client, populate_db):
    users = populate_db["users"]
    creator = platform_admin(users)
    existing = next(user for user in users if user != creator)

    assert_add_user_rejects_email(otp_client(creator), existing.email.upper())


@pytest.mark.django_db
def test_operator_admin_add_user_rejects_existing_email_in_other_case(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = otp_client(context["operator_admin"])
    session = client.session
    session["company_in_use"] = context["company"].id
    session.save()

    assert_add_user_rejects_email(client, context["member"].email.upper())


def platform_admin(users):
    return next(user for user in users if user_in_group(user, "PlatformAdmin"))


@pytest.mark.django_db
def test_reset_accepted_terms_on_post(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    response = client.post("/admin/governanceplatform/user/reset-accepted-terms/")

    assert response.status_code == 302
    assert not User.objects.filter(accepted_terms=True).exists()


@pytest.mark.django_db
def test_reset_accepted_terms_refuses_get(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    response = client.get("/admin/governanceplatform/user/reset-accepted-terms/")

    assert response.status_code == 404
    assert User.objects.filter(accepted_terms=True).exists()


@pytest.mark.django_db
def test_reset_cookie_acceptation_on_post(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))
    version = ApplicationConfig.objects.get(key="cookiebanner").value

    response = client.post("/admin/governanceplatform/user/reset-cookie-acceptation/")

    assert response.status_code == 302
    assert ApplicationConfig.objects.get(key="cookiebanner").value != version


@pytest.mark.django_db
def test_reset_cookie_acceptation_refuses_get(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))
    version = ApplicationConfig.objects.get(key="cookiebanner").value

    response = client.get("/admin/governanceplatform/user/reset-cookie-acceptation/")

    assert response.status_code == 404
    assert ApplicationConfig.objects.get(key="cookiebanner").value == version


@pytest.mark.django_db
def test_reset_buttons_ask_for_confirmation(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get("/admin/governanceplatform/user/").content.decode()

    for url in ("reset-accepted-terms/", "reset-cookie-acceptation/"):
        assert f'formaction="{url}"' in body
    assert body.count("data-confirm-message=") >= 2
    assert 'id="account-action-confirm"' in body
