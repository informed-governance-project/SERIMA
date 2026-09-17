import pytest
from django.urls import get_resolver, reverse

from conftest import list_admin_add_urls, list_urls, test_get_with_otp
from governanceplatform.helpers import user_in_group

# Restricted URL
restricted_names = [
    "admin:index",
    "edit_account",
    "incidents",
    "logout",
    "set_language",
    "contact",
]

# Public URL
non_restricted_urls = [
    "privacy",
    "cookies",
    "sitemap",
    "accessibility",
    "registration",
    "login",
]


@pytest.mark.django_db
def test_restricted_urls_without_credential(client):
    """
    Verify that a user who is not logged in is redirected to restricted views.
    """
    for name in restricted_names:
        url = reverse(name)
        response = client.get(url)
        assert response.status_code == 302


@pytest.mark.django_db
def test_accessible_urls_without_credential(client):
    """
    Verify that a user who is not logged in can access public pages.
    """
    for name in non_restricted_urls:
        url = reverse(name)
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_plain_login_url_redirects_to_two_factor(client):
    """
    Verify that the password-only login view shipped by django.contrib.auth.urls
    is not served, keeping the next parameter.
    """
    response = client.get("/account/login/?next=/incidents/")

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next=/incidents/"


@pytest.mark.django_db
def test_plain_login_url_does_not_authenticate(client, populate_db):
    """
    Verify that credentials posted to the password-only login view do not open a
    session, which would bypass the second factor.
    """
    user = populate_db["users"][0]

    response = client.post("/account/login/", {"username": user.email, "password": "secret"})

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_user_access_admin_without_2FA(client, populate_db):
    """
    Verify the admin access is unaccessible without 2FA
    """
    users = populate_db["users"]

    for user in users:
        client.force_login(user)

        url = reverse("admin:index")
        response = client.get(url)
        assert response.status_code in (
            302,
            403,
        ), f"User {user.email} should not access to the admin without 2FA"


@pytest.mark.django_db
def test_user_access_admin_with_2FA(otp_client, populate_db):
    """
    Verify that a user in the IncidentUser group or OperatorUser group cannot access the admin
    """
    users = populate_db["users"]
    url = reverse("admin:index")
    authorized_users = [
        user
        for user in users
        if user_in_group(user, "RegulatorAdmin")
        or user_in_group(user, "RegulatorUser")
        or user_in_group(user, "OperatorAdmin")
        or user_in_group(user, "ObserverAdmin")
        or user_in_group(user, "PlatformAdmin")
    ]
    test_get_with_otp(otp_client, users, authorized_users, [], url)


@pytest.mark.django_db
def test_roles_addition_rights(otp_client, populate_db):
    """
    Test the rights of each groups on the model of governanceplatform
    """
    users = populate_db["users"]
    platform_admin_rights = [
        "regulator",
        "observer",
        "regulation",
        "functionality",
        "entitycategory",
    ]
    for url_path in list_admin_add_urls("governanceplatform"):
        url = "/" + url_path
        if any(model in url_path for model in platform_admin_rights):
            authorized_users = [user for user in users if user_in_group(user, "PlatformAdmin")]
            test_get_with_otp(otp_client, users, authorized_users, [], url)
        elif url_path == "sector":
            authorized_users = [user for user in users if user_in_group(user, "RegulatorAdmin")]
            test_get_with_otp(otp_client, users, authorized_users, [], url)
        elif url_path == "company":
            authorized_users = [user for user in users if user_in_group(user, "RegulatorUser") or user_in_group(user, "RegulatorAdmin")]
            test_get_with_otp(otp_client, users, authorized_users, [], url)
        elif url_path == "user":
            authorized_users = [
                user
                for user in users
                if user_in_group(user, "ObserverAdmin")
                or user_in_group(user, "OperatorAdmin")
                or user_in_group(user, "RegulatorUser")
                or user_in_group(user, "RegulatorAdmin")
                or user_in_group(user, "PlatformAdmin")
            ]
            test_get_with_otp(otp_client, users, authorized_users, [], url)


@pytest.mark.django_db
def test_superuser_restricted_access(otp_client, populate_db):
    """
    Verify that a superuser cannot access the platform
    """
    users = populate_db["users"]
    for user in users:
        user.is_superuser = True
        user.save()
        client = otp_client(user)
        all_urls = list_urls(get_resolver().url_patterns)
        simple_urls = [url for url in all_urls if "<" not in url and "+" not in url]
        for url in simple_urls:
            response = client.get(url)
            assert response.status_code == 404
        user.is_superuser = False
        user.save()
