"""The reporting dashboard keeps each user's filters, sort and display choices across logins (#673)."""

import re

import pytest
from django.urls import reverse

import governanceplatform.tests.conftest as gp_conftest
from governanceplatform.globals import LIST_PREFERENCE_PAGES
from governanceplatform.helpers import set_preference
from governanceplatform.models import Functionality, User, UserPreference


@pytest.fixture
def populate_db(db):
    # on rewrap fixture to expose localy and don't get flake error
    return gp_conftest.populate_db.__wrapped__(db)


@pytest.fixture
def regulator(populate_db):
    """A regulator administrator whose regulator has the reporting module."""
    user = User.objects.get(email="regadmin@reg1.lu")
    user.regulators.first().functionalities.add(Functionality.objects.get(type="reporting"))
    return user


@pytest.mark.django_db
def test_sort_and_page_size_survive_logout(client, otp_client, regulator):
    otp_client(regulator).get(reverse("reporting"), {"per_page": "25", "sort_field": "name", "sort_direction": "asc"})
    client.logout()

    response = otp_client(regulator).get(reverse("reporting"))

    assert response.status_code == 200
    assert response.context["projects"].paginator.per_page == 25
    assert response.context["sort_field"] == "name"
    assert response.context["sort_direction"] == "asc"


@pytest.mark.django_db
def test_reset_sort_returns_to_the_default_order(otp_client, regulator):
    client = otp_client(regulator)
    client.get(reverse("reporting"), {"sort_field": "name"})

    redirect = client.get(reverse("reporting"), {"reset_sort": ""})
    response = client.get(reverse("reporting"))

    assert redirect.status_code == 302
    assert response.context["sort_field"] == "updated_at"
    assert not UserPreference.objects.filter(user=regulator, key="reporting.sort").exists()


@pytest.mark.django_db
def test_column_choice_reaches_the_template(otp_client, regulator):
    set_preference(regulator, "reporting", "columns", {"created_by": False})

    response = otp_client(regulator).get(reverse("reporting"))

    assert response.context["visible_columns"]["created_by"] is False
    assert response.context["visible_columns"]["name"] is True


@pytest.mark.django_db
def test_column_choice_offers_the_registry_columns(otp_client, regulator):
    html = otp_client(regulator).get(reverse("reporting")).content.decode()

    toggles = set(re.findall(r'data-column="([^"]+)"\s+id="column-', html))
    assert toggles == set(LIST_PREFERENCE_PAGES["reporting"]["columns"])
