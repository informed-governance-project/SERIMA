"""Per-user list preferences (#673): stored per page and aspect, so they survive logout."""

import json
import re
from functools import partial

import django_filters
import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticDevice

from governanceplatform.globals import DEFAULT_PER_PAGE, PER_PAGE_CHOICES
from governanceplatform.helpers import (
    ListPreferences,
    bind_applicable_filters,
    get_preferences,
    set_preference,
    update_list_params,
)
from governanceplatform.models import Company, CompanyUser, Sector, User, UserPreference
from incidents.filters import IncidentFilter
from incidents.globals import ALLOWED_SORT_FIELDS as INCIDENT_SORT_FIELDS
from reporting.filters import ProjectFilter


@pytest.fixture
def operator(populate_db):
    return _create_operator("prefs@com1.lu")


@pytest.fixture
def other_operator(populate_db):
    return _create_operator("prefs-other@com1.lu")


def _create_operator(email):
    user = User.objects.create(email=email, accepted_terms=True, accepted_terms_date=timezone.now())
    # A real save, not companies.add(): the post_save signal grants the operator group.
    CompanyUser.objects.create(user=user, company=Company.objects.all()[0], approved=True)
    user.refresh_from_db()
    return user


def _list_request(user, query="", session=None):
    """A request for /incidents/ in a given session; a fresh session stands for a new login."""
    request = RequestFactory().get(f"/incidents/{query}")
    request.user = user
    if session is None:
        SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    else:
        request.session = session
    return request


def _state(request, page, filterset_class):
    preferences = update_list_params(request, page, filterset_class)
    assert isinstance(preferences, ListPreferences)
    return preferences


def _incidents(user, query="", session=None):
    request = _list_request(user, query, session)
    return update_list_params(request, "incidents", IncidentFilter, INCIDENT_SORT_FIELDS), request


def _stored(user, key):
    return UserPreference.objects.filter(user=user, key=key).values_list("value", flat=True).first()


# Model


@pytest.mark.django_db
def test_a_user_has_one_row_per_key(operator):
    UserPreference.objects.create(user=operator, key="incidents.sort", value={})

    with pytest.raises(IntegrityError):
        UserPreference.objects.create(user=operator, key="incidents.sort", value={})


@pytest.mark.django_db
def test_preferences_are_deleted_with_the_user(operator):
    set_preference(operator, "incidents", "legend", True)

    operator.delete()

    assert not UserPreference.objects.exists()


# get_preferences


@pytest.mark.django_db
def test_defaults_apply_when_nothing_is_stored(operator):
    preferences = get_preferences(operator, "incidents")

    assert preferences["filters"] == {}
    assert preferences["sort"] == {}
    assert preferences["legend"] is False
    assert preferences["columns"]["status"] is True
    assert preferences["columns"]["reference"] is False


@pytest.mark.django_db
def test_stored_columns_override_defaults_and_unknown_columns_are_dropped(operator):
    set_preference(operator, "incidents", "columns", {"status": False, "reference": True, "removed_column": True})

    columns = get_preferences(operator, "incidents")["columns"]

    assert columns["status"] is False
    assert columns["reference"] is True
    assert columns["regulation"] is True
    assert "removed_column" not in columns


@pytest.mark.django_db
def test_loading_a_page_preferences_is_a_single_query(operator, django_assert_num_queries):
    for aspect, value in (("filters", {"per_page": "25"}), ("sort", {"sort_field": "status"}), ("legend", True)):
        set_preference(operator, "incidents", aspect, value)

    with django_assert_num_queries(1):
        get_preferences(operator, "incidents")


@pytest.mark.django_db
def test_pages_do_not_share_preferences(operator):
    set_preference(operator, "incidents", "legend", True)

    assert get_preferences(operator, "regulator_incidents")["legend"] is False


# update_list_params


@pytest.mark.django_db
def test_filters_and_sort_survive_a_new_session(operator):
    _incidents(operator, "?incident_status=CLOS&sort_field=status&sort_direction=asc")

    preferences, _ = _incidents(operator)

    assert preferences.filters == {"incident_status": "CLOS"}
    assert preferences.sort == {"sort_field": "status", "sort_direction": "asc"}


@pytest.mark.django_db
def test_search_and_page_last_only_for_the_session(operator):
    _, request = _incidents(operator, "?incident_status=CLOS")
    _incidents(operator, "?search=ransomware", session=request.session)
    preferences, _ = _incidents(operator, "?page=3", session=request.session)
    assert preferences.filters == {"incident_status": "CLOS", "search": "ransomware", "page": "3"}

    same_session, _ = _incidents(operator, session=request.session)
    new_session, _ = _incidents(operator)

    assert same_session.filters["search"] == "ransomware"
    assert new_session.filters == {"incident_status": "CLOS"}
    assert _stored(operator, "incidents.filters") == {"incident_status": "CLOS"}


@pytest.mark.django_db
def test_unknown_parameters_and_invalid_values_are_not_stored(operator):
    preferences, _ = _incidents(operator, "?per_page=5000&sort_field=password&sort_direction=sideways&csrfmiddlewaretoken=x")

    assert preferences.filters == {}
    assert preferences.sort == {"sort_field": "last_update", "sort_direction": "desc"}
    assert not UserPreference.objects.filter(user=operator).exists()


@pytest.mark.django_db
def test_allowed_page_size_is_stored(operator):
    preferences, _ = _incidents(operator, "?per_page=50")

    assert preferences.filters == {"per_page": 50}


@pytest.mark.django_db
def test_multi_value_filters_are_taken_from_the_filterset(operator):
    request = _list_request(operator, "?reference_year=2024&reference_year=2025&sectors=1")

    preferences = _state(request, "reporting", ProjectFilter)

    assert preferences.filters == {"reference_year": ["2024", "2025"], "sectors": ["1"]}


@pytest.mark.django_db
def test_clearing_a_filter_removes_it(operator):
    _incidents(operator, "?incident_status=CLOS&per_page=25")

    preferences, _ = _incidents(operator, "?incident_status=")

    assert preferences.filters == {"per_page": 25}


@pytest.mark.django_db
def test_reset_clears_filters_but_keeps_sort(operator):
    _, request = _incidents(operator, "?incident_status=CLOS&search=x&sort_field=status")

    response, _ = _incidents(operator, "?reset", session=request.session)

    assert isinstance(response, HttpResponseRedirect)
    assert response.url == "/incidents/"
    assert _stored(operator, "incidents.filters") is None
    assert _stored(operator, "incidents.sort") == {"sort_field": "status"}
    assert "incidents_list_params" not in request.session


@pytest.mark.django_db
def test_reset_sort_clears_sort_but_keeps_filters(operator):
    _incidents(operator, "?incident_status=CLOS&sort_field=status")

    response, _ = _incidents(operator, "?reset_sort")

    assert isinstance(response, HttpResponseRedirect)
    assert _stored(operator, "incidents.sort") is None
    assert _stored(operator, "incidents.filters") == {"incident_status": "CLOS"}


@pytest.mark.django_db
def test_an_empty_search_clears_only_the_search(operator):
    _, request = _incidents(operator, "?incident_status=CLOS&search=ransomware")

    response, _ = _incidents(operator, "?search=", session=request.session)
    preferences, _ = _incidents(operator, session=request.session)

    assert isinstance(response, HttpResponseRedirect)
    assert preferences.filters == {"incident_status": "CLOS"}


@pytest.mark.django_db
def test_an_unchanged_request_does_not_write(operator):
    _incidents(operator, "?incident_status=CLOS&sort_field=status")
    before = list(UserPreference.objects.filter(user=operator).values_list("key", "updated_at"))

    _incidents(operator, "?incident_status=CLOS")

    assert list(UserPreference.objects.filter(user=operator).values_list("key", "updated_at")) == before


@pytest.mark.django_db
def test_one_user_preferences_do_not_affect_another(operator, other_operator):
    _incidents(operator, "?incident_status=CLOS&sort_field=status")

    preferences, _ = _incidents(other_operator)

    assert preferences.filters == {}
    assert preferences.sort == {"sort_field": "last_update", "sort_direction": "desc"}


@pytest.mark.django_db
def test_the_page_default_sort_applies_until_the_user_sorts(operator):
    preferences, _ = _incidents(operator)

    assert preferences.sort == {"sort_field": "last_update", "sort_direction": "desc"}
    assert not UserPreference.objects.filter(user=operator, key="incidents.sort").exists()


@pytest.mark.django_db
def test_a_sort_direction_alone_keeps_the_default_field(operator):
    preferences, _ = _incidents(operator, "?sort_direction=asc")

    assert preferences.sort == {"sort_field": "last_update", "sort_direction": "asc"}


@pytest.mark.django_db
def test_page_size_defaults_to_the_shared_default(operator):
    default, _ = _incidents(operator)
    chosen, _ = _incidents(operator, "?per_page=50")

    assert default.per_page == DEFAULT_PER_PAGE
    assert chosen.per_page == 50


@pytest.mark.django_db
def test_a_page_without_sorting_has_no_default_sort(operator):
    preferences = _state(_list_request(operator), "report_recommendations", SectorFilter)

    assert preferences.sort == {}


@pytest.mark.django_db
def test_columns_and_legend_are_returned_with_the_list_state(operator):
    set_preference(operator, "incidents", "legend", True)

    preferences, _ = _incidents(operator)

    assert isinstance(preferences, ListPreferences)
    assert preferences.legend is True
    assert preferences.columns["reference"] is False


# bind_applicable_filters


class SectorFilter(django_filters.FilterSet):
    sectors = django_filters.ModelMultipleChoiceFilter(field_name="id", queryset=Sector.objects.all())

    class Meta:
        model = Sector
        fields = ["sectors"]


@pytest.mark.django_db
def test_a_rejected_filter_value_is_neither_applied_nor_reported(populate_db):
    unknown_sector_id = str(Sector.objects.order_by("-id").first().id + 1000)
    params = {"sectors": [unknown_sector_id], "per_page": 25, "search": "x"}

    filterset, applicable = bind_applicable_filters(partial(SectorFilter, queryset=Sector.objects.all()), params)

    assert applicable == {"per_page": 25, "search": "x"}
    assert not filterset.errors
    assert filterset.qs.count() == Sector.objects.count()


@pytest.mark.django_db
def test_valid_filters_are_bound_once(populate_db):
    sector_id = str(Sector.objects.first().id)
    bound = []

    def make_filterset(data):
        bound.append(data)
        return SectorFilter(data, queryset=Sector.objects.all())

    filterset, applicable = bind_applicable_filters(make_filterset, {"sectors": [sector_id]})

    assert applicable == {"sectors": [sector_id]}
    assert len(bound) == 1
    assert not filterset.errors


# Preferences endpoint


def _url(page, aspect):
    return reverse("save_list_preference", args=[page, aspect])


def _post(client, page, aspect, value):
    return client.post(_url(page, aspect), data=json.dumps({"value": value}), content_type="application/json")


@pytest.mark.django_db
def test_endpoint_saves_column_choice(otp_client, operator):
    response = _post(otp_client(operator), "incidents", "columns", {"reference": True, "status": False})

    assert response.status_code == 200
    columns = get_preferences(operator, "incidents")["columns"]
    assert columns["reference"] is True
    assert columns["status"] is False


@pytest.mark.django_db
def test_endpoint_saves_legend_state(otp_client, operator):
    response = _post(otp_client(operator), "so_declaration", "legend", True)

    assert response.status_code == 200
    assert get_preferences(operator, "so_declaration")["legend"] is True


@pytest.mark.django_db
def test_endpoint_writes_only_the_requesting_user_preferences(otp_client, operator, other_operator):
    _post(otp_client(operator), "incidents", "legend", True)

    assert get_preferences(other_operator, "incidents")["legend"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "aspect, value",
    [
        ("columns", {"password": True}),
        ("columns", {"status": "yes"}),
        ("columns", {}),
        ("columns", ["status"]),
        ("legend", "true"),
        ("legend", None),
    ],
)
def test_endpoint_rejects_invalid_values(otp_client, operator, aspect, value):
    response = _post(otp_client(operator), "incidents", aspect, value)

    assert response.status_code == 400
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b"\xff"])
def test_endpoint_rejects_a_malformed_body(otp_client, operator, body):
    response = otp_client(operator).post(_url("incidents", "legend"), data=body, content_type="application/json")

    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    "page, aspect",
    [
        ("incidents", "filters"),
        ("incidents", "sort"),
        ("unknown_page", "legend"),
        ("so_declaration", "columns"),
    ],
)
def test_endpoint_refuses_aspects_it_does_not_own(otp_client, operator, page, aspect):
    response = _post(otp_client(operator), page, aspect, True)

    assert response.status_code == 404
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_endpoint_accepts_only_post(otp_client, operator):
    response = otp_client(operator).get(_url("incidents", "legend"))

    assert response.status_code == 405


@pytest.mark.django_db
def test_endpoint_requires_login(client, populate_db):
    response = _post(client, "incidents", "legend", True)

    assert response.status_code == 302
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_endpoint_requires_a_csrf_token(operator):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(operator)
    session = csrf_client.session
    session["otp_device_id"] = StaticDevice.objects.create(user=operator, name="test-device").persistent_id
    session.save()

    response = _post(csrf_client, "incidents", "legend", True)

    assert response.status_code == 403
    assert not UserPreference.objects.exists()


# Pagination


@pytest.mark.django_db
def test_changing_page_keeps_a_multi_value_filter(operator):
    _incidents(operator, "?affected_sectors=1&affected_sectors=2")

    preferences, _ = _incidents(operator, "?page=2")

    assert preferences.filters["affected_sectors"] == ["1", "2"]
    assert _stored(operator, "incidents.filters") == {"affected_sectors": ["1", "2"]}


@pytest.mark.django_db
def test_pagination_links_carry_only_page_and_page_size():
    request = RequestFactory().get("/incidents/?affected_sectors=1&affected_sectors=2&search=a%26b")
    request.user = AnonymousUser()
    html = render_to_string(
        "parts/pagination.html",
        {"pagination_data": Paginator(range(30), 10).get_page(2), "per_page_choices": PER_PAGE_CHOICES},
        request=request,
    )

    assert set(re.findall(r'href="([^"]+)"', html)) == {
        "?page=1",
        "?page=2",
        "?page=3",
        *(f"?per_page={size}&page=1" for size in PER_PAGE_CHOICES),
    }


def _pagination(count, per_page=10):
    request = RequestFactory().get("/incidents/")
    request.user = AnonymousUser()
    context = {"pagination_data": Paginator(range(count), per_page).get_page(1), "per_page_choices": PER_PAGE_CHOICES}
    return render_to_string("parts/pagination.html", context, request=request)


def test_page_size_choices_are_ascending():
    assert list(PER_PAGE_CHOICES) == sorted(PER_PAGE_CHOICES)


@pytest.mark.django_db
def test_pagination_is_hidden_below_the_smallest_page_size():
    assert _pagination(min(PER_PAGE_CHOICES) - 1).strip() == ""


@pytest.mark.django_db
def test_pagination_shows_from_the_smallest_page_size():
    html = _pagination(min(PER_PAGE_CHOICES))

    assert "perPageDropdown" in html


@pytest.mark.django_db
def test_the_current_page_size_is_marked_active():
    html = _pagination(60, per_page=25)

    assert re.search(r'class="dropdown-item spinner-trigger\s+active\s*"\s+href="\?per_page=25&page=1"', html)


# Filter form submissions replace the stored filters


@pytest.mark.django_db
def test_unticking_every_value_of_a_multi_select_clears_it(operator):
    _, request = _incidents(operator, "?affected_sectors=1&affected_sectors=2&incident_status=CLOS&per_page=25")

    # The browser sends nothing for a multi-select left empty.
    preferences, _ = _incidents(operator, "?incident_status=CLOS", session=request.session)

    assert preferences.filters == {"incident_status": "CLOS", "per_page": 25}
    assert _stored(operator, "incidents.filters") == {"incident_status": "CLOS", "per_page": 25}


@pytest.mark.django_db
def test_a_search_keeps_the_stored_filters(operator):
    _, request = _incidents(operator, "?affected_sectors=1&affected_sectors=2")

    preferences, _ = _incidents(operator, "?search=ransomware", session=request.session)

    assert preferences.filters == {"affected_sectors": ["1", "2"], "search": "ransomware"}


@pytest.mark.django_db
def test_a_sort_or_page_size_change_keeps_the_stored_filters(operator):
    _, request = _incidents(operator, "?affected_sectors=1&affected_sectors=2")

    _incidents(operator, "?sort_field=status&sort_direction=asc", session=request.session)
    preferences, _ = _incidents(operator, "?per_page=50&page=1", session=request.session)

    assert preferences.filters["affected_sectors"] == ["1", "2"]


# The page number restarts when the result set changes


def _on_page_three(operator, query=""):
    _, request = _incidents(operator, query)
    _incidents(operator, "?page=3", session=request.session)
    return request.session


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "?incident_status=CLOS",
        "?sort_field=status&sort_direction=asc",
        "?search=ransomware",
        "?per_page=50&page=3",
        "?page=3&sort_field=status",
    ],
)
def test_changing_the_result_set_returns_to_the_first_page(operator, query):
    session = _on_page_three(operator)

    preferences, _ = _incidents(operator, query, session=session)

    assert "page" not in preferences.filters


@pytest.mark.django_db
def test_an_unchanged_request_stays_on_the_page(operator):
    session = _on_page_three(operator, "?incident_status=CLOS")

    preferences, _ = _incidents(operator, "?incident_status=CLOS", session=session)

    assert preferences.filters["page"] == "3"


@pytest.mark.django_db
@pytest.mark.parametrize("query", ["?reset_sort", "?search="])
def test_a_reset_returns_to_the_first_page(operator, query):
    session = _on_page_three(operator, "?sort_field=status&search=ransomware")

    _incidents(operator, query, session=session)

    assert "page" not in session["incidents_list_params"]
