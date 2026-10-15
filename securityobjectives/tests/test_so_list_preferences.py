"""The security objectives dashboard keeps each user's filters, sort and display choices across logins (#673)."""

import re

import pytest
from django.urls import reverse

from governanceplatform.globals import LIST_PREFERENCE_PAGES
from governanceplatform.helpers import set_preference
from governanceplatform.models import User


def _user(email):
    return User.objects.get(email=email)


@pytest.mark.django_db
def test_sort_and_page_size_survive_logout(client, otp_client, populate_so_db):
    regulator = _user("regadmin@reg1.lu")
    otp_client(regulator).get(reverse("securityobjectives"), {"per_page": "50", "sort_field": "year", "sort_direction": "asc"})
    client.logout()

    response = otp_client(regulator).get(reverse("securityobjectives"))

    assert response.status_code == 200
    assert response.context["standard_answers"].paginator.per_page == 50
    assert response.context["sort_field"] == "year"
    assert response.context["sort_direction"] == "asc"


@pytest.mark.django_db
def test_operator_and_regulator_preferences_are_independent(otp_client, populate_so_db):
    otp_client(_user("regadmin@reg1.lu")).get(reverse("securityobjectives"), {"sort_field": "year"})

    response = otp_client(_user("opadmin@com1.lu")).get(reverse("securityobjectives"))

    assert response.context["sort_field"] == "last_update"


@pytest.mark.django_db
def test_column_choice_and_legend_reach_the_template(otp_client, populate_so_db):
    regulator = _user("regadmin@reg1.lu")
    set_preference(regulator, "securityobjectives", "columns", {"progress": False})
    set_preference(regulator, "securityobjectives", "legend", True)

    response = otp_client(regulator).get(reverse("securityobjectives"))

    assert response.context["visible_columns"]["progress"] is False
    assert response.context["visible_columns"]["status"] is True
    assert response.context["show_legend"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("email", ["regadmin@reg1.lu", "opadmin@com1.lu"])
def test_column_choice_offers_the_registry_columns(otp_client, populate_so_db, email):
    html = otp_client(_user(email)).get(reverse("securityobjectives")).content.decode()

    toggles = set(re.findall(r'data-column="([^"]+)"\s+id="column-', html))
    assert toggles == set(LIST_PREFERENCE_PAGES["securityobjectives"]["columns"])


@pytest.mark.django_db
def test_hidden_columns_and_legend_are_rendered_by_the_server(otp_client, populate_so_db):
    regulator = _user("regadmin@reg1.lu")
    set_preference(regulator, "securityobjectives", "columns", {"year": False})
    set_preference(regulator, "securityobjectives", "legend", True)

    html = otp_client(regulator).get(reverse("securityobjectives")).content.decode()

    assert re.search(r'class="[^"]*\bd-none\b[^"]*"\s+data-column="year"', html)
    assert re.search(r'id="collapseLegend"\s+class="collapse\s+show\s*"', html)
