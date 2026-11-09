import hashlib
from datetime import timedelta

import pytest
import yaml
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from governanceplatform.models import APIKey, Company, CompanyUser, Functionality, Regulation, Regulator, RegulatorUser, Sector, User
from incidents.models import Incident, SectorRegulation
from reporting.models import Project
from securityobjectives.models import Standard, StandardAnswer, StandardAnswerGroup

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_user(settings):
    settings.API_ENABLED = True
    cache.clear()
    user = User.objects.create(email="reader@example.org", email_verified=True, accepted_terms=True, accepted_terms_date=timezone.now())
    user.groups.add(Group.objects.get_or_create(name="IncidentUser")[0])
    return user


@pytest.fixture
def bearer(api_user):
    key, token = APIKey.issue(user=api_user, name="Integration", expires_at=timezone.now() + timedelta(days=1))
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "key": key, "token": token}


def auth(bearer):
    return {"HTTP_AUTHORIZATION": bearer["HTTP_AUTHORIZATION"]}


@pytest.fixture
def records(api_user):
    regulator = Regulator.objects.create(name="Regulator")
    regulation = Regulation.objects.create(label="Regulation")
    workflow = SectorRegulation.objects.create(regulator=regulator, regulation=regulation, name="Workflow")
    company = Company.objects.create(name="Company", identifier="COM1")
    other_company = Company.objects.create(name="Other", identifier="COM2")
    sector = Sector.objects.create(name="Energy")
    standard = Standard.objects.create(label="Standard", regulator=regulator, regulation=regulation)
    incident = Incident.objects.create(sector_regulation=workflow, company=company, contact_user=api_user, company_name="Company")
    hidden_incident = Incident.objects.create(sector_regulation=workflow, company=other_company, company_name="Other")
    group = StandardAnswerGroup.objects.create(company=company)
    declaration = StandardAnswer.objects.create(
        standard=standard,
        group=group,
        submitter_company=company,
        submitter_user=api_user,
        year_of_submission=2026,
        status="PASS",
    )
    other_group = StandardAnswerGroup.objects.create(company=other_company)
    hidden_declaration = StandardAnswer.objects.create(
        standard=standard,
        group=other_group,
        submitter_company=other_company,
        year_of_submission=2026,
        status="DELIV",
    )
    project = Project.objects.create(author=api_user, standard=standard, years=[2026], reference_year=2026, name="Project")
    project.sectors.add(sector)
    return locals()


def enable_module(user, module, regulator=None):
    functionality = Functionality.objects.create(type=module, name=module)
    functionality.roles.set(user.groups.all())
    if regulator:
        regulator.functionalities.add(functionality)
    return functionality


def test_disabled_api_includes_schema_and_ui(client, settings):
    settings.API_ENABLED = False
    for url in [
        reverse("api:me"),
        reverse("api:incident-list"),
        reverse("api:declaration-list"),
        reverse("api:project-list"),
        reverse("api:schema"),
        reverse("api:swagger"),
    ]:
        assert client.get(url).status_code == 404


def test_key_digest_and_current_user(client, api_user, bearer):
    key = bearer["key"]
    assert key.digest == hashlib.sha256(bearer["token"].encode()).hexdigest()
    assert bearer["token"] not in str(key.__dict__)
    response = client.get(reverse("api:me"), **auth(bearer))
    assert response.status_code == 200
    assert response.json() == {"email": api_user.email, "first_name": "", "last_name": ""}
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("header", [None, "", "Bearer wrong", "Basic abc", "Bearer serima_" + "x" * 43, "Bearer a b"])
def test_missing_or_invalid_credentials(client, api_user, header):
    kwargs = {"HTTP_AUTHORIZATION": header} if header is not None else {}
    assert client.get(reverse("api:me"), **kwargs).status_code == 401


@pytest.mark.parametrize("state", ["expired", "revoked", "inactive", "terms", "stale_terms", "superuser"])
def test_key_and_owner_lifecycle(client, api_user, bearer, state):
    key = bearer["key"]
    if state == "expired":
        key.expires_at = timezone.now() - timedelta(seconds=1)
        key.save()
    elif state == "revoked":
        key.revoked_at = timezone.now()
        key.save()
    else:
        if state == "inactive":
            api_user.is_active = False
        elif state == "terms":
            api_user.accepted_terms = False
        elif state == "stale_terms":
            api_user.accepted_terms_date = timezone.now() - timedelta(days=366)
        else:
            api_user.is_superuser = True
        api_user.save()
    assert client.get(reverse("api:me"), **auth(bearer)).status_code in (401, 403)


def test_unverified_email_does_not_block_api(client, api_user, bearer):
    api_user.email_verified = False
    api_user.save()
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 200


def test_session_does_not_authenticate_api(client, api_user):
    client.force_login(api_user)
    assert client.get(reverse("api:me")).status_code == 401


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_api_rejects_writes(client, bearer, records, method):
    for name, kwargs in [
        ("api:me", {}),
        ("api:incident-list", {}),
        ("api:incident-detail", {"reference": records["incident"].incident_id}),
    ]:
        response = getattr(client, method)(reverse(name, kwargs=kwargs), {}, **auth(bearer))
        assert response.status_code == 405
    assert Incident.objects.count() == 2


def test_incident_user_sees_only_own_incidents(client, bearer, records):
    response = client.get(reverse("api:incident-list"), **auth(bearer))
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["incident_id"] == records["incident"].incident_id
    assert (
        client.get(reverse("api:incident-detail", kwargs={"reference": records["hidden_incident"].incident_id}), **auth(bearer)).status_code
        == 404
    )


def test_operator_scope_approval_and_live_permissions(client, api_user, bearer, records):
    link = CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    module = enable_module(api_user, "securityobjectives")
    url = reverse("api:declaration-list")
    response = client.get(url, **auth(bearer))
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["status"] == "DELIV"
    assert "review_comment" not in response.json()["results"][0]
    hidden = reverse("api:declaration-detail", kwargs={"reference": records["hidden_declaration"].group.group_id})
    assert client.get(hidden, **auth(bearer)).status_code == 404
    link.approved = False
    link.save()
    assert client.get(url, **auth(bearer)).json()["count"] == 0
    assert client.get(reverse("api:incident-list"), **auth(bearer)).json()["count"] == 0
    module.roles.clear()
    assert client.get(url, **auth(bearer)).status_code == 403
    assert client.get(reverse("api:project-list"), **auth(bearer)).status_code == 403


def test_regulator_sectors_and_module_switch(client, api_user, bearer, records):
    membership = RegulatorUser.objects.create(user=api_user, regulator=records["regulator"])
    api_user.refresh_from_db()
    module = enable_module(api_user, "reporting", records["regulator"])
    enable_module(api_user, "securityobjectives", records["regulator"])
    assert client.get(reverse("api:project-list"), **auth(bearer)).json()["count"] == 0
    membership.sectors.add(records["sector"])
    records["company"].sectors.add(records["sector"])
    records["incident"].affected_sectors.add(records["sector"])
    response = client.get(reverse("api:project-list"), **auth(bearer))
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["reference"] == str(records["project"].api_id)
    assert client.get(reverse("api:project-detail", kwargs={"reference": records["project"].api_id}), **auth(bearer)).status_code == 200
    assert client.get(reverse("api:incident-list"), **auth(bearer)).json()["count"] == 1
    assert client.get(reverse("api:declaration-list"), **auth(bearer)).json()["count"] == 1
    records["regulator"].functionalities.remove(module)
    assert client.get(reverse("api:project-list"), **auth(bearer)).status_code == 403


def test_ui_key_creation_once_revoke_and_ownership(otp_client, api_user, bearer, settings):
    settings.DEBUG = True
    api_user.set_password("a-real-test-password")
    api_user.save()
    client = otp_client(api_user)
    url = reverse("api_keys")
    before = APIKey.objects.count()
    assert client.post(url, {"name": "bad", "expires_in_days": 0, "password": "wrong"}).status_code == 200
    assert APIKey.objects.count() == before
    response = client.post(url, {"name": "New key", "expires_in_days": 1, "password": "a-real-test-password"})
    token = response.context["token"]
    assert token and token.encode() in response.content
    assert "no-store" in response["Cache-Control"]
    assert token.encode() not in client.get(url).content
    key = APIKey.objects.get(name="New key")
    other = User.objects.create(email="other@example.org")
    other_key, _ = APIKey.issue(user=other, name="Other", expires_at=timezone.now() + timedelta(days=1))
    assert client.post(reverse("revoke_api_key", args=[other_key.pk])).status_code == 404
    revoke = reverse("revoke_api_key", args=[key.pk])
    assert client.get(revoke).status_code == 405
    assert client.post(revoke).status_code == 302
    assert client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 401
    settings.API_ENABLED = False
    assert client.get(url).status_code == 404


def test_key_mutations_require_csrf(api_user, bearer, settings):
    settings.DEBUG = True
    client = Client(enforce_csrf_checks=True)
    client.force_login(api_user)
    assert client.post(reverse("api_keys"), {"name": "x"}).status_code == 403
    assert client.post(reverse("revoke_api_key", args=[bearer["key"].pk])).status_code == 403


def test_openapi_and_swagger(client, api_user):
    response = client.get(reverse("api:schema"))
    assert response.status_code == 200
    schema = yaml.safe_load(response.content)
    assert schema["components"]["securitySchemes"]["APIKey"]["scheme"] == "bearer"
    for path in ["/api/v1/me/", "/api/v1/incidents/", "/api/v1/security-objectives/", "/api/v1/reporting/projects/"]:
        assert path in schema["paths"]
        assert set(schema["paths"][path]) == {"get"}
    assert client.get(reverse("api:swagger")).status_code == 200


def test_pagination_is_bounded(client, api_user, bearer, records):
    Incident.objects.bulk_create(
        [Incident(sector_regulation=records["workflow"], contact_user=api_user, company_name="Company") for _ in range(50)]
    )
    response = client.get(reverse("api:incident-list"), {"page_size": 1000}, **auth(bearer))
    assert response.json()["count"] == 51
    assert len(response.json()["results"]) == 50
    assert len(client.get(reverse("api:incident-list"), {"page": 2}, **auth(bearer)).json()["results"]) == 1


def test_authenticated_requests_are_throttled(client, bearer, monkeypatch):
    from governanceplatform.api.views import APIThrottle

    monkeypatch.setattr(APIThrottle, "rate", "2/min")
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 200
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 200
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 429


def test_regulator_isolation_and_all_modules_reject_writes(client, api_user, bearer, records):
    RegulatorUser.objects.create(user=api_user, regulator=records["regulator"], is_regulator_administrator=True)
    enable_module(api_user, "reporting", records["regulator"])
    enable_module(api_user, "securityobjectives", records["regulator"])
    other = User.objects.create(email="another-regulator@example.org")
    other_regulator = Regulator.objects.create(name="Other regulator")
    RegulatorUser.objects.create(user=other, regulator=other_regulator, is_regulator_administrator=True)
    hidden = Project.objects.create(author=other, standard=records["standard"], years=[2026], reference_year=2026)
    assert client.get(reverse("api:project-detail", kwargs={"reference": hidden.api_id}), **auth(bearer)).status_code == 404
    records["declaration"].status = "UNDE"
    records["declaration"].save()
    assert client.get(reverse("api:declaration-detail", kwargs={"reference": records["group"].group_id}), **auth(bearer)).status_code == 404
    for module in ["declaration", "project"]:
        list_url = reverse(f"api:{module}-list")
        reference = records["project"].api_id if module == "project" else records["group"].group_id
        detail_url = reverse(f"api:{module}-detail", kwargs={"reference": reference})
        for method in ["post", "put", "patch", "delete"]:
            assert getattr(client, method)(list_url, {}, **auth(bearer)).status_code == 405
            assert getattr(client, method)(detail_url, {}, **auth(bearer)).status_code == 405


def test_observer_rules_and_ineligible_modules(client, api_user, bearer, records):
    from governanceplatform.models import Observer, ObserverRegulation, ObserverUser

    observer = Observer.objects.create(name="Observer")
    ObserverUser.objects.create(user=api_user, observer=observer)
    assert client.get(reverse("api:incident-list"), **auth(bearer)).json()["count"] == 0
    rule = ObserverRegulation.objects.create(observer=observer, regulation=records["regulation"])
    rule.sectors.add(records["sector"])
    records["incident"].affected_sectors.add(records["sector"])
    assert client.get(reverse("api:incident-list"), **auth(bearer)).json()["count"] == 1
    enable_module(api_user, "securityobjectives")
    enable_module(api_user, "reporting")
    assert client.get(reverse("api:declaration-list"), **auth(bearer)).status_code == 403
    assert client.get(reverse("api:project-list"), **auth(bearer)).status_code == 403


def test_session_company_cannot_expand_api_scope(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    client.force_login(api_user)
    session = client.session
    session["company_in_use"] = records["other_company"].pk
    session.save()
    assert client.get(reverse("api:incident-list"), **auth(bearer)).json()["count"] == 1
    assert (
        client.get(reverse("api:incident-detail", kwargs={"reference": records["hidden_incident"].incident_id}), **auth(bearer)).status_code
        == 404
    )
