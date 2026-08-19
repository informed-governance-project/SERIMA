"""How a user linked to several companies is made to pick one.

SessionExpiryMiddleware calls the select_company view directly rather than redirecting,
so the picker is rendered at whatever URL was requested and select_company has no route
of its own. These tests pin the behaviour that a routed, redirect-based version would
have to preserve. No seeded user has more than one company, so none of this is otherwise
exercised.
"""

import pytest
from django.utils import timezone

from governanceplatform.models import Company, CompanyUser, User

PICKER = "registration/select_company.html"


def _templates(response):
    return [t.name for t in response.templates if t.name]


@pytest.fixture
def multi_company_user(populate_db):
    """A user linked to two approved companies and belonging to no group."""
    user = User.objects.create(email="multi@com1.lu", first_name="Multi", last_name="Company")
    for company in Company.objects.all()[:2]:
        user.companies.add(company)
        CompanyUser.objects.filter(user=user, company=company).update(approved=True)
    return user


@pytest.fixture
def onboarded_multi_company_user(multi_company_user):
    """The same user, past the terms gate, so only company selection is outstanding."""
    multi_company_user.accepted_terms = True
    multi_company_user.accepted_terms_date = timezone.now()
    multi_company_user.save()
    return multi_company_user


@pytest.fixture
def user_owing_terms(populate_db):
    """A single-company user who has not accepted the terms yet."""
    user = User.objects.create(email="terms@com1.lu", first_name="Owes", last_name="Terms")
    company = Company.objects.first()
    user.companies.add(company)
    CompanyUser.objects.filter(user=user, company=company).update(approved=True)
    return user


@pytest.fixture
def single_company_user(populate_db):
    user = User.objects.create(email="single@com1.lu", first_name="Single", last_name="Company")
    company = Company.objects.first()
    user.companies.add(company)
    CompanyUser.objects.filter(user=user, company=company).update(approved=True)
    return user


@pytest.mark.django_db()
def test_the_picker_is_rendered_at_the_url_that_was_requested(client, multi_company_user, settings):
    """The middleware returns the view's response, so the URL is not changed.

    A redirect-based version would move the user to the picker's own URL and would have
    to carry the original destination in ?next=.
    """
    settings.DEBUG = False
    client.force_login(multi_company_user)

    response = client.get("/incidents/")

    assert response.status_code == 200
    assert PICKER in _templates(response)


@pytest.mark.django_db()
def test_the_picker_is_served_before_two_factor_verification(client, multi_company_user, settings):
    """SessionExpiryMiddleware runs before RestrictViewsMiddleware, which owns the OTP gate."""
    settings.DEBUG = False
    client.force_login(multi_company_user)

    response = client.get("/")

    assert response.status_code == 200
    assert PICKER in _templates(response)


@pytest.mark.django_db()
def test_choosing_a_company_stores_it_in_the_session(client, multi_company_user, settings):
    settings.DEBUG = False
    client.force_login(multi_company_user)
    chosen = multi_company_user.companies.first()

    response = client.post("/", {"select_company": chosen.id})

    assert response.status_code == 200
    assert client.session["company_in_use"] == chosen.id


@pytest.mark.django_db()
def test_choosing_a_company_grants_the_operator_group(client, multi_company_user, settings):
    """The picker is how a company-linked user with no group acquires one."""
    settings.DEBUG = False
    assert not multi_company_user.groups.exists()
    client.force_login(multi_company_user)

    client.post("/", {"select_company": multi_company_user.companies.first().id})

    multi_company_user.refresh_from_db()
    assert list(multi_company_user.groups.values_list("name", flat=True)) == ["OperatorUser"]


@pytest.mark.django_db()
def test_a_company_administrator_gets_the_admin_group(client, multi_company_user, settings):
    settings.DEBUG = False
    chosen = multi_company_user.companies.first()
    CompanyUser.objects.filter(user=multi_company_user, company=chosen).update(is_company_administrator=True)
    client.force_login(multi_company_user)

    client.post("/", {"select_company": chosen.id})

    multi_company_user.refresh_from_db()
    assert list(multi_company_user.groups.values_list("name", flat=True)) == ["OperatorAdmin"]


@pytest.mark.django_db()
def test_a_company_the_user_is_not_linked_to_is_refused(client, multi_company_user, settings):
    settings.DEBUG = False
    outsider = Company.objects.create(identifier="OUT", name="Unrelated Company")
    client.force_login(multi_company_user)

    response = client.post("/", {"select_company": outsider.id})

    assert PICKER in _templates(response)
    assert "company_in_use" not in client.session


@pytest.mark.django_db()
def test_a_single_company_user_never_sees_the_picker(client, single_company_user, settings):
    """One company is selected for the user without asking."""
    settings.DEBUG = False
    client.force_login(single_company_user)

    response = client.get("/")

    assert PICKER not in _templates(response)
    assert client.session["company_in_use"] == single_company_user.companies.first().id


# The picker and the terms page are both returned in place of whatever was requested, so
# every way out of them has to be exempted explicitly or the page becomes a dead end.


@pytest.mark.django_db()
def test_logging_out_from_the_picker_actually_logs_out(client, multi_company_user, settings):
    settings.DEBUG = False
    client.force_login(multi_company_user)

    response = client.get("/logout")

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db()
def test_language_can_be_changed_from_the_picker(otp_client, onboarded_multi_company_user, settings):
    settings.DEBUG = False
    client = otp_client(onboarded_multi_company_user)

    response = client.post("/set-language/", {"language": "fr", "next": "/"})

    assert response.status_code == 302
    assert client.cookies["django_language"].value == "fr"


@pytest.mark.django_db()
def test_the_picker_page_can_load_the_javascript_catalogue(otp_client, onboarded_multi_company_user, settings):
    """registration/base.html pulls in the catalogue, so the picker would break its own scripts."""
    settings.DEBUG = False
    client = otp_client(onboarded_multi_company_user)

    response = client.get("/jsi18n/")

    assert response.status_code == 200
    assert "javascript" in response.headers["Content-Type"]


@pytest.mark.django_db()
def test_language_can_be_changed_from_the_terms_page(otp_client, user_owing_terms, settings):
    """Terms have to be readable in the user's own language before they are accepted."""
    settings.DEBUG = False
    client = otp_client(user_owing_terms)
    assert client.get("/").url == "/accept_terms/"

    response = client.post("/set-language/", {"language": "fr", "next": "/accept_terms/"})

    assert client.cookies["django_language"].value == "fr"
    assert response.url == "/accept_terms/"


@pytest.mark.django_db()
def test_the_picker_still_intercepts_everything_else(otp_client, onboarded_multi_company_user, settings):
    """The exemptions must not let a company-less session reach the application."""
    settings.DEBUG = False
    client = otp_client(onboarded_multi_company_user)

    response = client.get("/incidents/")

    assert PICKER in _templates(response)
