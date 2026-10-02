import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse

from governanceplatform.context_processors import user_modules
from governanceplatform.globals import FUNCTIONALITIES, FUNCTIONALITY_ELIGIBLE_ROLES
from governanceplatform.models import CompanyUser, Functionality, Observer, ObserverUser, User
from governanceplatform.permissions import GROUP_PERMISSIONS

# The shared fixture enables every eligible role on both functionalities, and only REG1 has SO.


def get_user(email: str) -> User:
    return User.objects.get(email=email)


def disable_role(functionality_type: str, role: str) -> None:
    Functionality.objects.get(type=functionality_type).roles.remove(Group.objects.get(name=role))


def menu_types(user: User) -> list[str]:
    request = RequestFactory().get("/")
    request.user = user
    return [module["type"] for module in user_modules(request)["user_modules"]]


@pytest.mark.django_db
def test_regulator_with_role_and_entity_enabled_reaches_module(otp_client, populate_db):
    client = otp_client(get_user("reguser@reg1.lu"))

    assert client.get(reverse("securityobjectives")).status_code == 200


@pytest.mark.django_db
def test_regulator_with_role_disabled_is_refused_although_entity_enabled(otp_client, populate_db):
    disable_role("securityobjectives", "RegulatorUser")
    client = otp_client(get_user("reguser@reg1.lu"))

    assert client.get(reverse("securityobjectives")).status_code == 404


@pytest.mark.django_db
def test_regulator_with_entity_disabled_is_refused_although_role_enabled(otp_client, populate_db):
    client = otp_client(get_user("reguser@reg2.lu"))

    assert client.get(reverse("securityobjectives")).status_code == 404


@pytest.mark.django_db
def test_disabling_one_regulator_role_leaves_the_other_untouched(otp_client, populate_db):
    disable_role("securityobjectives", "RegulatorUser")
    client = otp_client(get_user("regadmin@reg1.lu"))

    assert client.get(reverse("securityobjectives")).status_code == 200


@pytest.mark.django_db
def test_regulator_admin_pages_follow_role(otp_client, populate_db):
    disable_role("securityobjectives", "RegulatorAdmin")
    client = otp_client(get_user("regadmin@reg1.lu"))

    assert client.get(reverse("admin:app_list", args=["securityobjectives"])).status_code == 404


@pytest.mark.django_db
def test_regulator_admin_pages_open_with_role_and_entity(otp_client, populate_db):
    client = otp_client(get_user("regadmin@reg1.lu"))

    assert client.get(reverse("admin:app_list", args=["securityobjectives"])).status_code == 200


@pytest.mark.django_db
def test_operator_with_role_enabled_reaches_module_without_any_regulator(otp_client, populate_db):
    Functionality.objects.get(type="securityobjectives").regulator_set.clear()
    client = otp_client(get_user("opuser@com1.lu"))

    assert client.get(reverse("securityobjectives")).status_code == 200


@pytest.mark.django_db
def test_operator_with_role_disabled_is_refused(otp_client, populate_db):
    disable_role("securityobjectives", "OperatorUser")
    client = otp_client(get_user("opuser@com1.lu"))

    assert client.get(reverse("securityobjectives")).status_code == 404


@pytest.mark.django_db
def test_observer_gets_no_module_although_entity_enabled(populate_db):
    Observer.objects.get(id=1).functionalities.add(*Functionality.objects.all())

    assert get_user("obsadm@cert1.lu").get_module_permissions() == []


@pytest.mark.django_db
def test_menu_lists_module_when_both_checks_pass(populate_db):
    assert "securityobjectives" in menu_types(get_user("reguser@reg1.lu"))


@pytest.mark.django_db
def test_menu_hides_module_when_role_disabled(populate_db):
    disable_role("securityobjectives", "RegulatorUser")

    assert "securityobjectives" not in menu_types(get_user("reguser@reg1.lu"))


@pytest.mark.django_db
def test_menu_hides_module_for_operator_when_role_disabled(populate_db):
    disable_role("securityobjectives", "OperatorUser")

    assert "securityobjectives" not in menu_types(get_user("opuser@com1.lu"))


@pytest.mark.django_db
def test_incident_user_never_gets_a_module(populate_db):
    assert menu_types(get_user("iu1@iu.lu")) == ["incidents"]


def post_roles(client, functionality: Functionality, roles: list[str]):
    url = reverse("admin:governanceplatform_functionality_change", args=[functionality.pk]) + "?language=en"
    data = {
        "type": functionality.type,
        "name": functionality.safe_translation_getter("name", any_language=True),
        "roles": list(Group.objects.filter(name__in=roles).values_list("pk", flat=True)),
    }
    return client.post(url, data)


@pytest.mark.django_db
def test_admin_form_offers_only_eligible_roles(otp_client, populate_db):
    client = otp_client(get_user("pa@pa.lu"))
    reporting = Functionality.objects.get(type="reporting")

    response = client.get(reverse("admin:governanceplatform_functionality_change", args=[reporting.pk]))

    offered = {group.name for group in response.context["adminform"].form.fields["roles"].queryset}
    assert offered == {"RegulatorAdmin", "RegulatorUser"}


@pytest.mark.django_db
def test_admin_form_saves_eligible_roles(otp_client, populate_db):
    client = otp_client(get_user("pa@pa.lu"))
    reporting = Functionality.objects.get(type="reporting")

    response = post_roles(client, reporting, ["RegulatorAdmin"])

    assert response.status_code == 302
    assert list(reporting.roles.values_list("name", flat=True)) == ["RegulatorAdmin"]


@pytest.mark.django_db
def test_admin_form_rejects_role_not_eligible_for_functionality(otp_client, populate_db):
    client = otp_client(get_user("pa@pa.lu"))
    reporting = Functionality.objects.get(type="reporting")

    response = post_roles(client, reporting, ["RegulatorAdmin", "OperatorAdmin"])

    assert response.status_code == 200
    assert "roles" in response.context["adminform"].form.errors
    assert "OperatorAdmin" not in reporting.roles.values_list("name", flat=True)


@pytest.mark.django_db
def test_admin_form_rejects_observer_role(otp_client, populate_db):
    client = otp_client(get_user("pa@pa.lu"))
    so = Functionality.objects.get(type="securityobjectives")

    response = post_roles(client, so, ["RegulatorAdmin", "ObserverAdmin"])

    assert "roles" in response.context["adminform"].form.errors
    assert "ObserverAdmin" not in so.roles.values_list("name", flat=True)


@pytest.mark.django_db
def test_regulator_cannot_change_roles(otp_client, populate_db):
    client = otp_client(get_user("regadmin@reg1.lu"))
    reporting = Functionality.objects.get(type="reporting")

    post_roles(client, reporting, [])

    assert reporting.roles.count() == 2


@pytest.mark.django_db
def test_view_only_user_can_open_functionality(otp_client, populate_db):
    client = otp_client(get_user("regadmin@reg1.lu"))
    reporting = Functionality.objects.get(type="reporting")

    response = client.get(reverse("admin:governanceplatform_functionality_change", args=[reporting.pk]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_observer_admin_page_hides_functionalities(otp_client, populate_db):
    client = otp_client(get_user("pa@pa.lu"))

    response = client.get(reverse("admin:governanceplatform_observer_change", args=[1]))

    assert response.status_code == 200
    assert "functionalities" not in response.context["adminform"].form.fields


@pytest.mark.django_db
def test_admin_form_renders_only_eligible_roles(otp_client, populate_db):
    client = otp_client(get_user("pa@pa.lu"))
    reporting = Functionality.objects.get(type="reporting")

    response = client.get(reverse("admin:governanceplatform_functionality_change", args=[reporting.pk]))

    rendered = response.content.decode()
    assert "selectfilter" in rendered
    assert ">RegulatorUser</option>" in rendered
    assert ">OperatorAdmin</option>" not in rendered


@pytest.mark.django_db
@pytest.mark.parametrize("email", ["opadmin@com1.lu", "opuser@com1.lu", "obsadm@cert1.lu", "iu1@iu.lu"])
def test_reporting_is_refused_to_roles_without_access(otp_client, populate_db, email):
    client = otp_client(get_user(email))

    assert client.get(reverse("reporting")).status_code == 404


def get_user_with_role(role: str) -> User:
    """Roles follow the entity links, so the two the dataset lacks are made by flipping an admin flag."""
    if role == "OperatorAdmin":
        CompanyUser.objects.filter(user__email="opadmin@com1.lu").update(is_company_administrator=True)
        CompanyUser.objects.get(user__email="opadmin@com1.lu").save()
    if role == "ObserverUser":
        ObserverUser.objects.filter(user__email="obsadm@cert1.lu").update(is_observer_administrator=False)
        ObserverUser.objects.get(user__email="obsadm@cert1.lu").save()
    return User.objects.filter(groups__name=role).first()


# PlatformAdmin is redirected to the admin before any role check, so it has no pair to test.
NOT_ELIGIBLE_PAIRS = [
    (functionality_type, role)
    for functionality_type in FUNCTIONALITIES
    for role in GROUP_PERMISSIONS
    if role != "PlatformAdmin" and role not in FUNCTIONALITY_ELIGIBLE_ROLES[functionality_type]
]


@pytest.mark.django_db
@pytest.mark.parametrize(("functionality_type", "role"), NOT_ELIGIBLE_PAIRS)
def test_restrict_views_blocks_every_role_not_eligible(otp_client, populate_db, functionality_type, role):
    """A role row the admin form would refuse must still not open the module, so
    RestrictViewsMiddleware has to stay in step with FUNCTIONALITY_ELIGIBLE_ROLES."""
    user = get_user_with_role(role)
    Functionality.objects.get(type=functionality_type).roles.add(Group.objects.get(name=role))
    client = otp_client(user)

    assert client.get(reverse(functionality_type)).status_code == 404
