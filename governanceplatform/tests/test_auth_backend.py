import pytest
from django.contrib.auth import authenticate
from django.db import connection
from django.test.utils import CaptureQueriesContext

from governanceplatform.helpers import is_user_operator
from governanceplatform.models import User


@pytest.fixture
def backend_user(db):
    return User.objects.create_user(
        email="backend@example.com",
        password="password",
    )


@pytest.mark.django_db
def test_authenticate_ignores_email_case(backend_user):
    """
    Verify that the email is matched case-insensitively.
    """
    assert authenticate(request=None, username="BackEnd@Example.COM", password="password") == backend_user


@pytest.mark.django_db
def test_authenticate_rejects_wrong_password(backend_user):
    """
    Verify that a known email with a wrong password is refused.
    """
    assert authenticate(request=None, username=backend_user.email, password="wrong") is None


@pytest.mark.django_db
def test_authenticate_rejects_unknown_email(db):
    """
    Verify that an email without an account is refused.
    """
    assert authenticate(request=None, username="nobody@example.com", password="password") is None


@pytest.mark.django_db
def test_authenticate_rejects_deactivated_user(backend_user):
    """
    Verify that a deactivated account is refused even with the right password.
    """
    backend_user.is_active = False
    backend_user.save()

    assert authenticate(request=None, username=backend_user.email, password="password") is None


@pytest.mark.django_db
def test_group_membership_is_read_once_per_request(otp_client, populate_db):
    """
    Verify that the group checks made by the middleware, the context processors
    and the templates share a single query.
    """
    user = next(u for u in populate_db["users"] if is_user_operator(u))
    client = otp_client(user)
    client.get("/privacy/")

    with CaptureQueriesContext(connection) as context:
        client.get("/privacy/")

    group_queries = [query for query in context.captured_queries if "auth_group" in query["sql"]]
    assert len(group_queries) == 1
