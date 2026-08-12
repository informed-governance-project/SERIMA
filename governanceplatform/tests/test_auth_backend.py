import pytest
from django.contrib.auth import authenticate

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
