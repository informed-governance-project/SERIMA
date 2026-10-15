"""The incident lists keep each user's filters, sort and display choices across logins (#673)."""

import re

import pytest
from django.urls import reverse

from governanceplatform.globals import INCIDENT_LIST_COLUMNS
from governanceplatform.helpers import set_preference
from governanceplatform.models import User, UserPreference


def _user(email):
    return User.objects.get(email=email)


def _login_again(client, otp_client, user):
    client.logout()
    return otp_client(user)


@pytest.mark.django_db
def test_filters_and_sort_survive_logout(client, otp_client, populate_db):
    operator = _user("opadmin@com1.lu")
    otp_client(operator).get(reverse("incidents"), {"incident_status": "CLOSE", "sort_field": "status", "sort_direction": "asc"})

    response = _login_again(client, otp_client, operator).get(reverse("incidents"))

    assert response.status_code == 200
    assert response.context["filter"].data["incident_status"] == "CLOSE"
    assert response.context["sort_field"] == "status"
    assert response.context["sort_direction"] == "asc"
    assert response.context["is_filtered"] is True


@pytest.mark.django_db
def test_search_does_not_survive_logout(client, otp_client, populate_db):
    operator = _user("opadmin@com1.lu")
    otp_client(operator).get(reverse("incidents"), {"search": "ransomware"})

    response = _login_again(client, otp_client, operator).get(reverse("incidents"))

    assert "search" not in response.context["filter"].data
    assert response.context["is_filtered"] is False


@pytest.mark.django_db
def test_reset_clears_the_stored_filters(otp_client, populate_db):
    operator = _user("opadmin@com1.lu")
    client = otp_client(operator)
    client.get(reverse("incidents"), {"incident_status": "CLOSE"})

    response = client.get(reverse("incidents"), {"reset": ""})

    assert response.status_code == 302
    assert response.url == reverse("incidents")
    assert not UserPreference.objects.filter(user=operator, key="incidents.filters").exists()


@pytest.mark.django_db
def test_a_stored_filter_rejected_here_is_ignored_but_kept(otp_client, populate_db):
    operator = _user("opadmin@com1.lu")
    set_preference(operator, "incidents", "filters", {"incident_status": "REMOVED_STATUS", "per_page": 25})

    response = otp_client(operator).get(reverse("incidents"))

    assert response.status_code == 200
    assert not response.context["filter"].errors
    assert response.context["is_filtered"] is False
    assert UserPreference.objects.get(user=operator, key="incidents.filters").value == {"incident_status": "REMOVED_STATUS", "per_page": 25}


@pytest.mark.django_db
def test_regulator_lists_keep_separate_preferences(otp_client, populate_db):
    regulator = _user("regadmin@reg1.lu")
    client = otp_client(regulator)
    client.get(reverse("incidents"), {"sort_field": "status", "sort_direction": "asc"})

    response = client.get(reverse("regulator_incidents"))

    assert response.status_code == 200
    assert response.context["sort_field"] == "last_update"


@pytest.mark.django_db
def test_reset_returns_to_the_regulator_incidents_page(otp_client, populate_db):
    client = otp_client(_user("regadmin@reg1.lu"))

    response = client.get(reverse("regulator_incidents"), {"reset_sort": ""})

    assert response.status_code == 302
    assert response.url == reverse("regulator_incidents")


@pytest.mark.django_db
def test_column_choice_and_legend_reach_the_template(otp_client, populate_db):
    operator = _user("opadmin@com1.lu")
    set_preference(operator, "incidents", "columns", {"reference": True})
    set_preference(operator, "incidents", "legend", True)

    response = otp_client(operator).get(reverse("incidents"))

    assert response.context["visible_columns"]["reference"] is True
    assert response.context["visible_columns"]["detection_date"] is False
    assert response.context["show_legend"] is True


def _column_toggles(response):
    return set(re.findall(r'data-column="([^"]+)"\s+id="column-', response.content.decode()))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email, url_name, missing_columns",
    [
        ("opadmin@com1.lu", "incidents", {"company_identifier", "company_name"}),
        ("regadmin@reg1.lu", "incidents", {"regulator"}),
        ("regadmin@reg1.lu", "regulator_incidents", {"company_identifier", "company_name"}),
    ],
)
def test_column_choice_offers_the_registry_columns_shown_to_the_role(otp_client, populate_db, email, url_name, missing_columns):
    response = otp_client(_user(email)).get(reverse(url_name))

    assert _column_toggles(response) == set(INCIDENT_LIST_COLUMNS) - missing_columns


@pytest.mark.django_db
def test_hidden_columns_are_hidden_by_the_server(otp_client, populate_incident_db):
    operator = _user("opadmin@com1.lu")
    set_preference(operator, "incidents", "columns", {"status": False})

    html = otp_client(operator).get(reverse("incidents")).content.decode()

    assert re.search(r'class="[^"]*\bd-none\b[^"]*"\s+data-column="status"', html)
    assert re.search(r'class="[^"]*\bd-none\b[^"]*"\s+data-column="reference"', html)
    assert not re.search(r'class="[^"]*\bd-none\b[^"]*"\s+data-column="regulation"', html)


@pytest.mark.django_db
def test_legend_state_is_rendered_by_the_server(otp_client, populate_db):
    operator = _user("opadmin@com1.lu")
    set_preference(operator, "incidents", "legend", True)

    html = otp_client(operator).get(reverse("incidents")).content.decode()

    assert re.search(r'id="collapseLegend"\s+class="collapse\s+show\s*"', html)
    assert reverse("save_list_preference", args=["incidents", "legend"]) in html


@pytest.mark.django_db
def test_the_table_carries_the_default_sort_for_the_header_arrows(otp_client, populate_incident_db):
    html = otp_client(_user("opadmin@com1.lu")).get(reverse("incidents")).content.decode()

    assert re.search(r'id="incidents-table"\s+data-default-sort-field="last_update"', html)


@pytest.mark.django_db
def test_unticking_every_sector_turns_the_filter_off(otp_client, populate_db):
    """The filter pop-up as a browser submits it: empty fields and no sector at all."""
    client = otp_client(_user("opadmin@com1.lu"))
    # Only sub-sectors and sectors without sub-sectors are offered.
    sector_ids = [str(sector.id) for sector in populate_db["sectors"] if sector.parent][:2]
    defaults = {"incident_id": "", "incident_status": "", "is_significative_impact": ""}

    filtered = client.get(reverse("incidents"), {**defaults, "affected_sectors": sector_ids})
    cleared = client.get(reverse("incidents"), defaults)

    assert filtered.context["is_filtered"] is True
    assert cleared.context["is_filtered"] is False


@pytest.mark.django_db
def test_the_impact_filter_offers_the_blank_choice_first(otp_client, populate_db):
    html = otp_client(_user("opadmin@com1.lu")).get(reverse("incidents")).content.decode()

    options = re.search(r'<select name="is_significative_impact"[^>]*>(.*?)</select>', html, re.S).group(1)
    assert re.findall(r'<option value="([^"]*)"', options) == ["", "true", "false"]
    assert re.search(r'<option value="" selected>---------</option>', options)


@pytest.mark.django_db
@pytest.mark.parametrize("impact, is_filtered", [("true", True), ("false", True), ("", False)])
def test_the_impact_filter_is_active_only_on_yes_or_no(otp_client, populate_db, impact, is_filtered):
    operator = _user("opadmin@com1.lu")

    response = otp_client(operator).get(reverse("incidents"), {"is_significative_impact": impact})

    assert response.context["is_filtered"] is is_filtered
    stored = UserPreference.objects.filter(user=operator, key="incidents.filters").values_list("value", flat=True).first() or {}
    assert ("is_significative_impact" in stored) is is_filtered
