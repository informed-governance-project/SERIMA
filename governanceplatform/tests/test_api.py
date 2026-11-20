import hashlib
from datetime import timedelta

import pytest
import yaml
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from governanceplatform.globals import API_ELIGIBLE_ROLES
from governanceplatform.models import (
    APIKey,
    APIModuleAccess,
    Company,
    CompanyUser,
    Functionality,
    Regulation,
    Regulator,
    RegulatorUser,
    Sector,
    User,
)
from incidents.models import Answer, Incident, IncidentWorkflow, LogReportRead, SectorRegulation, SectorRegulationWorkflow, Workflow
from reporting.models import LogReporting, Project
from securityobjectives.models import LogStandardAnswer, Standard, StandardAnswer, StandardAnswerGroup

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def api_access():
    """Grant API access to every eligible role, so each test narrows it only where it means to."""
    access = {}
    for module, roles in API_ELIGIBLE_ROLES.items():
        access[module] = APIModuleAccess.objects.get_or_create(module=module)[0]
        access[module].roles.set([Group.objects.get_or_create(name=role)[0] for role in roles])
    return access


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


def bind_key(bearer, company):
    """Operator keys read the company they were created for."""
    APIKey.objects.filter(pk=bearer["key"].pk).update(company=company)


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
    bind_key(bearer, records["company"])
    module = enable_module(api_user, "securityobjectives")
    url = reverse("api:declaration-list")
    response = client.get(url, **auth(bearer))
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["status"] == "DELIV"
    assert "review_comment" not in response.json()["results"][0]
    hidden = reverse("api:declaration-detail", kwargs={"reference": records["hidden_declaration"].group.group_id})
    assert client.get(hidden, **auth(bearer)).status_code == 404
    module.roles.clear()
    assert client.get(url, **auth(bearer)).status_code == 403
    assert client.get(reverse("api:project-list"), **auth(bearer)).status_code == 403
    assert client.get(reverse("api:incident-list"), **auth(bearer)).status_code == 200
    link.approved = False
    link.save()
    assert client.get(reverse("api:incident-list"), **auth(bearer)).status_code == 403


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
    create = reverse("create_api_key")
    assert client.post(url, {"name": "x", "expires_in_days": 1, "password": "a-real-test-password"}).status_code == 405
    before = APIKey.objects.count()
    response = client.post(create, {"name": "bad", "expires_in_days": 0, "password": "wrong"})
    assert response.status_code == 200
    assert response.context["form"].errors.keys() == {"expires_in_days", "password"}
    assert APIKey.objects.count() == before
    response = client.post(create, {"name": "New key", "expires_in_days": 1, "password": "a-real-test-password"})
    token = response.context["token"]
    assert token and token.encode() in response.content
    assert list(response.context["api_keys"]) == list(api_user.api_keys.order_by("-created_at"))
    assert "no-store" in response["Cache-Control"]
    assert token.encode() not in client.get(url).content
    assert token.encode() not in client.get(create).content
    key = APIKey.objects.get(name="New key")
    other = User.objects.create(email="other@example.org")
    other_key, _ = APIKey.issue(user=other, name="Other", expires_at=timezone.now() + timedelta(days=1))
    assert client.post(reverse("revoke_api_key", args=[other_key.pk])).status_code == 404
    revoke = reverse("revoke_api_key", args=[key.pk])
    assert client.get(revoke).status_code == 405
    response = client.post(revoke)
    assert response.status_code == 200
    assert response.templates[0].name == "parts/api_keys_table.html"
    assert client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 401
    settings.API_ENABLED = False
    assert client.get(url).status_code == 404
    assert client.get(create).status_code == 404


def test_password_change_revokes_api_keys(client, api_user, bearer):
    api_user.set_password("a-first-password")
    api_user.save()
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 200
    api_user.set_password("a-second-password")
    api_user.save()
    bearer["key"].refresh_from_db()
    assert bearer["key"].revoked_at is not None
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 401


def test_saving_the_user_without_a_password_change_keeps_api_keys(client, api_user, bearer):
    api_user.set_password("a-first-password")
    api_user.save()
    key, token = APIKey.issue(user=api_user, name="After", expires_at=timezone.now() + timedelta(days=1))
    api_user.first_name = "Renamed"
    api_user.save()
    key.refresh_from_db()
    assert key.revoked_at is None


def test_two_factor_reset_revokes_api_keys(api_user, bearer):
    device = TOTPDevice.objects.create(user=api_user, name="default")
    device.delete()
    bearer["key"].refresh_from_db()
    assert bearer["key"].revoked_at is not None


def test_key_mutations_require_csrf(api_user, bearer, settings):
    settings.DEBUG = True
    client = Client(enforce_csrf_checks=True)
    client.force_login(api_user)
    assert client.post(reverse("create_api_key"), {"name": "x"}).status_code == 403
    assert client.post(reverse("revoke_api_key", args=[bearer["key"].pk])).status_code == 403


def test_openapi_and_swagger(client, api_user):
    for module in ["securityobjectives", "reporting"]:
        enable_module(api_user, module)
    response = client.get(reverse("api:schema"))
    assert response.status_code == 200
    schema = yaml.safe_load(response.content)
    assert schema["components"]["securitySchemes"]["APIKey"]["scheme"] == "bearer"
    for path in ["/api/v1/me/", "/api/v1/incidents/", "/api/v1/security-objectives/", "/api/v1/reporting/projects/"]:
        assert path in schema["paths"]
        assert set(schema["paths"][path]) == {"get"}
    assert client.get(reverse("api:swagger")).status_code == 200


def test_schema_hides_modules_whose_functionality_grants_no_role(client, api_user):
    reporting = Functionality.objects.create(type="reporting", name="reporting")
    paths = yaml.safe_load(client.get(reverse("api:schema")).content)["paths"]
    assert {"/api/v1/me/", "/api/v1/incidents/"} <= set(paths)
    assert not any(path.startswith(("/api/v1/security-objectives/", "/api/v1/reporting/")) for path in paths)
    reporting.roles.add(Group.objects.get(name="IncidentUser"))
    paths = yaml.safe_load(client.get(reverse("api:schema")).content)["paths"]
    assert "/api/v1/reporting/projects/" in paths
    assert "/api/v1/security-objectives/" not in paths


def test_swagger_page_uses_the_platform_layout_without_inline_script(client, api_user):
    response = client.get(reverse("api:swagger"))
    assert [template.name for template in response.templates][:2] == ["api/swagger_ui.html", "home/base.html"]
    assert b'id="swagger-ui"' in response.content
    assert b"SwaggerUIBundle(" not in response.content
    script = client.get(reverse("api:swagger") + "?script")
    assert script.status_code == 200
    assert script["Content-Type"].startswith("application/javascript")
    assert reverse("api:schema").encode() in script.content


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


def test_incident_list_is_not_logged(client, bearer, records):
    assert client.get(reverse("api:incident-list"), **auth(bearer)).status_code == 200
    assert not LogReportRead.objects.exists()


def test_incident_detail_logs_each_report(client, api_user, bearer, records):
    detail = reverse("api:incident-detail", kwargs={"reference": records["incident"].incident_id})
    client.get(detail, **auth(bearer))
    assert not LogReportRead.objects.exists()
    reports = set()
    for position, name in enumerate(["Early warning", "Notification"]):
        workflow = Workflow.objects.create(name=name, label=name)
        SectorRegulationWorkflow.objects.create(sector_regulation=records["workflow"], workflow=workflow, position=position)
        reports.add(IncidentWorkflow.objects.create(incident=records["incident"], workflow=workflow).pk)
    client.get(detail, **auth(bearer))
    assert set(LogReportRead.objects.values_list("incident_report", flat=True)) == reports
    log = LogReportRead.objects.first()
    assert (log.user, log.incident, log.action) == (api_user, records["incident"], "API READ")
    # an incident user belongs to no organisation, whatever company name their incident carries
    assert (log.role, log.entity_name, log.user_full_name) == ("IncidentUser", "", api_user.get_full_name())
    hidden = reverse("api:incident-detail", kwargs={"reference": records["hidden_incident"].incident_id})
    assert client.get(hidden, **auth(bearer)).status_code == 404
    assert not LogReportRead.objects.filter(incident=records["hidden_incident"]).exists()


def test_incident_detail_skips_answers_detached_from_their_question(client, bearer, records):
    workflow = Workflow.objects.create(name="Early warning", label="Early warning")
    SectorRegulationWorkflow.objects.create(sector_regulation=records["workflow"], workflow=workflow)
    report = IncidentWorkflow.objects.create(incident=records["incident"], workflow=workflow)
    Answer.objects.create(incident_workflow=report, question_options=None, answer="orphan")
    response = client.get(reverse("api:incident-detail", kwargs={"reference": records["incident"].incident_id}), **auth(bearer))
    assert response.status_code == 200
    assert response.json()["reports"][0]["answers"] == {}


def test_declaration_detail_is_logged_for_the_operator_company_but_not_the_list(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    bind_key(bearer, records["company"])
    enable_module(api_user, "securityobjectives")
    client.get(reverse("api:declaration-list"), **auth(bearer))
    assert not LogStandardAnswer.objects.exists()
    client.get(reverse("api:declaration-detail", kwargs={"reference": records["group"].group_id}), **auth(bearer))
    log = LogStandardAnswer.objects.get()
    assert (log.standard_answer, log.entity_name, log.action) == (records["declaration"], "Company", "API READ")


def test_regulator_declaration_read_is_logged_with_the_regulator(client, api_user, bearer, records):
    RegulatorUser.objects.create(user=api_user, regulator=records["regulator"], is_regulator_administrator=True)
    enable_module(api_user, "securityobjectives", records["regulator"])
    client.get(reverse("api:declaration-detail", kwargs={"reference": records["group"].group_id}), **auth(bearer))
    log = LogStandardAnswer.objects.get()
    assert (log.entity_name, log.role, log.action) == ("Regulator", "RegulatorAdmin", "API READ")


def test_declaration_list_omits_answers_that_detail_returns(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    bind_key(bearer, records["company"])
    enable_module(api_user, "securityobjectives")
    listed = client.get(reverse("api:declaration-list"), **auth(bearer)).json()["results"][0]
    detail = client.get(reverse("api:declaration-detail", kwargs={"reference": records["group"].group_id}), **auth(bearer)).json()
    assert "measures" not in listed
    assert detail["measures"] == []
    assert listed == {field: value for field, value in detail.items() if field != "measures"}


def test_project_reads_are_not_logged_like_on_the_web(client, api_user, bearer, records):
    RegulatorUser.objects.create(user=api_user, regulator=records["regulator"], is_regulator_administrator=True)
    enable_module(api_user, "reporting", records["regulator"])
    assert client.get(reverse("api:project-list"), **auth(bearer)).status_code == 200
    assert client.get(reverse("api:project-detail", kwargs={"reference": records["project"].api_id}), **auth(bearer)).status_code == 200
    assert not LogReporting.objects.exists()


def test_session_company_cannot_change_the_key_company(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    CompanyUser.objects.create(user=api_user, company=records["other_company"], approved=True)
    bind_key(bearer, records["company"])
    client.force_login(api_user)
    session = client.session
    session["company_in_use"] = records["other_company"].pk
    session.save()
    assert client.get(reverse("api:incident-list"), **auth(bearer)).json()["count"] == 1
    assert (
        client.get(reverse("api:incident-detail", kwargs={"reference": records["hidden_incident"].incident_id}), **auth(bearer)).status_code
        == 404
    )


def test_operator_key_reads_only_its_company(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    CompanyUser.objects.create(user=api_user, company=records["other_company"], approved=True)
    enable_module(api_user, "securityobjectives")
    bind_key(bearer, records["company"])
    incidents = client.get(reverse("api:incident-list"), **auth(bearer)).json()["results"]
    declarations = client.get(reverse("api:declaration-list"), **auth(bearer)).json()["results"]
    assert [incident["incident_id"] for incident in incidents] == [records["incident"].incident_id]
    assert [declaration["reference"] for declaration in declarations] == [str(records["group"].group_id)]
    hidden = reverse("api:incident-detail", kwargs={"reference": records["hidden_incident"].incident_id})
    assert client.get(hidden, **auth(bearer)).status_code == 404


def test_operator_key_without_company_is_refused(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    assert client.get(reverse("api:incident-list"), **auth(bearer)).status_code == 403


def test_operator_key_role_follows_its_company_membership(client, api_user, bearer, records, api_access):
    operator_admin = Group.objects.get_or_create(name="OperatorAdmin")[0]
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True, is_company_administrator=True)
    CompanyUser.objects.create(user=api_user, company=records["other_company"], approved=True)
    # the user last selected the company where they are not administrator
    api_user.groups.set([Group.objects.get_or_create(name="OperatorUser")[0]])
    Functionality.objects.create(type="securityobjectives", name="securityobjectives").roles.set([operator_admin])
    api_access["securityobjectives"].roles.set([operator_admin])
    bind_key(bearer, records["company"])
    assert client.get(reverse("api:declaration-list"), **auth(bearer)).status_code == 200
    bind_key(bearer, records["other_company"])
    assert client.get(reverse("api:declaration-list"), **auth(bearer)).status_code == 403


def test_operator_key_is_bound_to_the_approved_company_in_use(otp_client, api_user, records, settings):
    settings.DEBUG = True
    api_user.set_password("a-real-test-password")
    api_user.save()
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True)
    CompanyUser.objects.create(user=api_user, company=records["other_company"], approved=False)
    client = otp_client(api_user)
    data = {"name": "Operator key", "expires_in_days": 1, "password": "a-real-test-password"}
    session = client.session
    session["company_in_use"] = records["other_company"].pk
    session.save()
    response = client.post(reverse("create_api_key"), data)
    assert response.context["form"].non_field_errors()
    assert not APIKey.objects.filter(name="Operator key").exists()
    session = client.session
    session["company_in_use"] = records["company"].pk
    session.save()
    response = client.post(reverse("create_api_key"), data)
    assert response.context["token"]
    assert APIKey.objects.get(name="Operator key").company == records["company"]


def test_role_without_api_access_is_refused(client, bearer, records, api_access):
    api_access["incidents"].roles.clear()
    assert client.get(reverse("api:incident-list"), **auth(bearer)).status_code == 403
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 403


def test_api_access_is_granted_per_module(client, api_user, bearer, records, api_access):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True, is_company_administrator=True)
    bind_key(bearer, records["company"])
    api_user.groups.set([Group.objects.get_or_create(name="OperatorAdmin")[0]])
    enable_module(api_user, "securityobjectives")
    api_access["incidents"].roles.clear()
    assert client.get(reverse("api:incident-list"), **auth(bearer)).status_code == 403
    assert client.get(reverse("api:declaration-list"), **auth(bearer)).status_code == 200
    assert client.get(reverse("api:me"), **auth(bearer)).status_code == 200


def test_api_access_does_not_widen_web_access(client, api_user, bearer, records):
    CompanyUser.objects.create(user=api_user, company=records["company"], approved=True, is_company_administrator=True)
    bind_key(bearer, records["company"])
    api_user.groups.set([Group.objects.get_or_create(name="OperatorAdmin")[0]])
    # granted on the API, but the security objectives functionality is off for the role
    assert client.get(reverse("api:declaration-list"), **auth(bearer)).status_code == 403


def test_grant_to_an_ineligible_role_is_ignored(client, api_user, bearer, records, api_access):
    # IncidentUser can never reach reporting; a grant written past the admin form must not open it
    api_access["reporting"].roles.add(Group.objects.get(name="IncidentUser"))
    enable_module(api_user, "reporting")
    assert client.get(reverse("api:project-list"), **auth(bearer)).status_code == 403


def test_key_management_requires_an_api_module(otp_client, api_user, bearer, settings, api_access):
    client = otp_client(api_user)
    assert client.get(reverse("api_keys")).status_code == 200
    assert client.get(reverse("edit_account")).context["api_enabled"] is True
    api_access["incidents"].roles.clear()
    assert client.get(reverse("api_keys")).status_code == 403
    assert client.get(reverse("create_api_key")).status_code == 403
    assert client.get(reverse("edit_account")).context["api_enabled"] is False
    # an existing key can still be revoked
    response = client.post(reverse("revoke_api_key", kwargs={"key_id": bearer["key"].id}))
    assert response.status_code == 200
    bearer["key"].refresh_from_db()
    assert bearer["key"].revoked_at is not None


def test_admin_form_offers_and_accepts_only_eligible_roles(api_access):
    from governanceplatform.forms import APIModuleAccessAdminForm

    reporting = api_access["reporting"]
    form = APIModuleAccessAdminForm(instance=reporting)
    assert set(form.fields["roles"].queryset.values_list("name", flat=True)) == set(API_ELIGIBLE_ROLES["reporting"])
    incident_user = Group.objects.get(name="IncidentUser")
    form = APIModuleAccessAdminForm({"roles": [incident_user.pk]}, instance=reporting)
    assert not form.is_valid()
    assert "roles" in form.errors


def test_api_access_admin_edits_roles_only(otp_client, api_access):
    admin_user = User.objects.create(email="platform@example.org", is_staff=True, accepted_terms=True, accepted_terms_date=timezone.now())
    admin_user.groups.add(Group.objects.get_or_create(name="PlatformAdmin")[0])
    admin_user.user_permissions.add(*Permission.objects.filter(codename="change_apimoduleaccess"))
    client = otp_client(admin_user)
    assert client.get(reverse("admin:governanceplatform_apimoduleaccess_add")).status_code == 403
    response = client.get(reverse("admin:governanceplatform_apimoduleaccess_change", args=[api_access["reporting"].pk]))
    assert response.status_code == 200
    assert list(response.context["adminform"].form.fields) == ["roles"]
    delete = reverse("admin:governanceplatform_apimoduleaccess_delete", args=[api_access["reporting"].pk])
    assert client.get(delete).status_code == 403


def test_api_module_rows_follow_api_modules(monkeypatch, api_access):
    from django.apps import apps

    from governanceplatform import signals

    APIModuleAccess.objects.create(module="retired")
    monkeypatch.setattr(signals, "API_MODULES", {**signals.API_MODULES, "newmodule": "New module"})
    signals.sync_api_modules(sender=apps.get_app_config("governanceplatform"), apps=apps, using="default")

    assert set(APIModuleAccess.objects.values_list("module", flat=True)) == {"incidents", "securityobjectives", "reporting", "newmodule"}
    assert not APIModuleAccess.objects.get(module="newmodule").roles.exists()
    # existing grants survive the sync
    assert set(api_access["incidents"].roles.values_list("name", flat=True)) == set(API_ELIGIBLE_ROLES["incidents"])
