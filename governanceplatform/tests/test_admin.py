import re

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.urls import reverse
from unfold.admin import BaseInlineMixin, ModelAdmin
from unfold.sites import UnfoldAdminSite
from unfold.widgets import UnfoldAdminSelectWidget

from governanceplatform.admin import admin_site
from governanceplatform.helpers import user_in_group
from governanceplatform.models import (
    ApplicationConfig,
    CompanyUser,
    Observer,
    ObserverConnector,
    ObserverRegulation,
    ObserverUser,
    RegulatorUser,
    Sector,
    User,
)
from incidents.forms import ConditionalQuestionOptionForm


def test_all_admin_registrations_use_unfold():
    assert isinstance(admin_site, UnfoldAdminSite)

    for model_admin in admin_site._registry.values():
        assert isinstance(model_admin, ModelAdmin)
        assert all(issubclass(inline, BaseInlineMixin) for inline in model_admin.inlines)


@pytest.mark.django_db(transaction=True)
def test_add_user_via_admin(otp_client, populate_db):
    """
    Test that when a user creates another via the admin interface,
    the new user's role is correct depending on the creator.
    """
    users = populate_db["users"]
    url = "/admin/governanceplatform/user/add/"

    # role mapping creator --> creation
    role_mapping = {
        "PlatformAdmin": "PlatformAdmin",
        "RegulatorAdmin": "RegulatorUser",
        "RegulatorUser": "OperatorUser",
        "OperatorAdmin": "OperatorUser",
        "ObserverAdmin": "ObserverUser",
    }

    for index, creator in enumerate(users, start=1):
        # new user data
        email = f"new_user{index}@serima.exemple.lu"
        data = {
            "email": email,
            "first_name": "test",
            "last_name": "test",
        }

        client = otp_client(creator)

        # check if the user is in a group who can create a user
        creator_group = next((group for group in role_mapping if user_in_group(creator, group)), None)
        if not creator_group:
            continue

        expected_group = role_mapping[creator_group]

        response = client.post(url, data, follow=True)
        assert response.status_code == 200
        created_user = User.objects.get(email=email)
        assert user_in_group(created_user, expected_group), f"{creator_group} → {expected_group} expected, but got something else"


@pytest.fixture
def observer_connector(populate_db):
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["rt"]
    observer.save()
    connector = ObserverConnector.objects.create(
        observer=observer,
        connector_type="rt",
        name="RT",
        config={"url": "https://rt.example.com", "queue": "incidents"},
    )
    connector.secret = "rt-token"
    connector.save()
    return connector


@pytest.mark.django_db
def test_connector_admin_scoped_to_own_observer(otp_client, populate_db, observer_connector):
    users = populate_db["users"]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    foreign_observer = Observer.objects.create(
        id=999,
        country="LU",
        address="456 rue de Luxembourg",
        email_for_notification="cert2@cert2.lu",
        name="CERT2",
    )
    foreign_connector = ObserverConnector.objects.create(observer=foreign_observer, connector_type="email", name="Email", config={})

    client = otp_client(obs_admin)
    response = client.get("/admin/governanceplatform/observerconnector/")
    assert response.status_code == 200
    assert observer_connector.name.encode() in response.content

    response = client.get(f"/admin/governanceplatform/observerconnector/{foreign_connector.pk}/change/")
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_connector_admin_masks_secret(otp_client, populate_db, observer_connector):
    users = populate_db["users"]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get(f"/admin/governanceplatform/observerconnector/{observer_connector.pk}/change/")

    assert response.status_code == 200
    assert b"rt-token" not in response.content
    assert ("*" * len("rt-token")).encode() in response.content


@pytest.mark.django_db
def test_connector_test_endpoint_permissions(otp_client, populate_db, observer_connector):
    users = populate_db["users"]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))
    url = f"/admin/governanceplatform/observerconnector/{observer_connector.pk}/test-connection/"

    client = otp_client(obs_admin)
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_allowed_connector_types_hidden_from_observer_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get(f"/admin/governanceplatform/observer/{observer.pk}/change/")

    assert response.status_code == 200
    assert b"allowed_connector_types" not in response.content


@pytest.mark.django_db
def test_allowed_connector_types_visible_to_platform_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    platform_admin = next(user for user in users if user_in_group(user, "PlatformAdmin"))

    client = otp_client(platform_admin)
    response = client.get(f"/admin/governanceplatform/observer/{observer.pk}/change/")

    assert response.status_code == 200
    assert b"allowed_connector_types" in response.content


@pytest.mark.django_db
def test_observer_admin_add_connector_limited_to_allowed_types(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get("/admin/governanceplatform/observerconnector/add/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="gpg_json"' in content
    assert 'value="rt"' not in content
    assert 'value="webhook"' not in content


@pytest.mark.django_db
def test_removing_allowed_type_deactivates_its_connectors(populate_db):
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["rt", "gpg_json"]
    observer.save()
    rt = ObserverConnector.objects.create(observer=observer, connector_type="rt", name="RT", config={})
    gpg_json = ObserverConnector.objects.create(observer=observer, connector_type="gpg_json", name="GPG JSON", config={})

    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    observer.deactivate_disallowed_connectors()

    rt.refresh_from_db()
    gpg_json.refresh_from_db()
    assert rt.is_active is False
    assert gpg_json.is_active is True


@pytest.mark.django_db
def test_disallowed_type_connector_hidden_from_observer_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    hidden = ObserverConnector.objects.create(observer=observer, connector_type="rt", name="RT hidden", config={})
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    list_response = client.get("/admin/governanceplatform/observerconnector/")
    change_response = client.get(f"/admin/governanceplatform/observerconnector/{hidden.pk}/change/")

    assert list_response.status_code == 200
    assert b"RT hidden" not in list_response.content
    assert change_response.status_code in (302, 404)


@pytest.mark.django_db
def test_notification_mode_editable_by_observer_admin(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    response = client.get(f"/admin/governanceplatform/observer/{observer.pk}/change/")

    assert response.status_code == 200
    assert b'name="notification_mode"' in response.content


@pytest.mark.django_db
def test_connector_two_step_add_flow(otp_client, populate_db):
    users = populate_db["users"]
    observer = populate_db["observers"][0]
    observer.allowed_connector_types = ["gpg_json"]
    observer.save()
    obs_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))

    client = otp_client(obs_admin)
    # step 1: the add form has no config fields and must save without them
    response = client.post(
        "/admin/governanceplatform/observerconnector/add/",
        {"observer": observer.pk, "connector_type": "gpg_json", "name": "GPG JSON", "is_active": "on"},
    )
    connector = ObserverConnector.objects.get(observer=observer, name="GPG JSON")
    # step 2: redirected straight to the change view where the config fields live
    assert response.status_code == 302
    assert response.url == f"/admin/governanceplatform/observerconnector/{connector.pk}/change/"
    change_page = client.get(response.url)
    assert change_page.status_code == 200
    assert b'name="config__gpg_public_key"' in change_page.content


def assert_add_user_rejects_email(client, email):
    user_count = User.objects.count()

    response = client.post(
        "/admin/governanceplatform/user/add/",
        {"email": email, "first_name": "test", "last_name": "test"},
    )

    assert response.status_code == 200
    assert "email" in response.context["adminform"].form.errors
    assert User.objects.count() == user_count


@pytest.mark.django_db
def test_add_user_via_admin_rejects_existing_email_in_other_case(otp_client, populate_db):
    users = populate_db["users"]
    creator = platform_admin(users)
    existing = next(user for user in users if user != creator)

    assert_add_user_rejects_email(otp_client(creator), existing.email.upper())


@pytest.mark.django_db
def test_operator_admin_add_user_rejects_existing_email_in_other_case(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = otp_client(context["operator_admin"])
    session = client.session
    session["company_in_use"] = context["company"].id
    session.save()

    assert_add_user_rejects_email(client, context["member"].email.upper())


@pytest.mark.django_db
def test_operator_admin_add_user_administrator_field_is_a_switch(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = otp_client(context["operator_admin"])
    session = client.session
    session["company_in_use"] = context["company"].id
    session.save()

    body = client.get(reverse("admin:governanceplatform_user_add")).content.decode()

    field = re.search(r'<input[^>]*id="id_is_administrator"[^>]*>', body).group(0)
    assert 'type="checkbox"' in field
    assert "rounded-full" in field


def platform_admin(users):
    return next(user for user in users if user_in_group(user, "PlatformAdmin"))


@pytest.mark.django_db
def test_reset_accepted_terms_on_post(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    response = client.post("/admin/governanceplatform/user/reset-accepted-terms/")

    assert response.status_code == 302
    assert not User.objects.filter(accepted_terms=True).exists()


@pytest.mark.django_db
def test_reset_accepted_terms_refuses_get(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    response = client.get("/admin/governanceplatform/user/reset-accepted-terms/")

    assert response.status_code == 404
    assert User.objects.filter(accepted_terms=True).exists()


@pytest.mark.django_db
def test_reset_cookie_acceptation_on_post(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))
    version = ApplicationConfig.objects.get(key="cookiebanner").value

    response = client.post("/admin/governanceplatform/user/reset-cookie-acceptation/")

    assert response.status_code == 302
    assert ApplicationConfig.objects.get(key="cookiebanner").value != version


@pytest.mark.django_db
def test_reset_cookie_acceptation_refuses_get(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))
    version = ApplicationConfig.objects.get(key="cookiebanner").value

    response = client.get("/admin/governanceplatform/user/reset-cookie-acceptation/")

    assert response.status_code == 404
    assert ApplicationConfig.objects.get(key="cookiebanner").value == version


@pytest.mark.django_db
def test_reset_buttons_ask_for_confirmation(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get("/admin/governanceplatform/user/").content.decode()
    header, toolbar = body.split('class="changelist-tools"', 1)

    for url in ("reset-accepted-terms/", "reset-cookie-acceptation/"):
        assert f'formaction="{url}"' not in header
        assert f'formaction="{url}"' in toolbar
    assert body.count("data-confirm-message=") >= 2
    assert 'id="account-action-confirm"' in body


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/admin/", "/admin/governanceplatform/", "/admin/governanceplatform/user/"])
def test_header_links_and_favicon_are_on_every_kind_of_admin_page(otp_client, populate_db, path):
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get(path).content.decode()

    assert body.count(f'href="{reverse("two_factor:profile")}"') == 1
    assert body.count(f'href="{reverse("password_change")}"') == 1
    assert body.count(f'href="{reverse("logout")}"') == 1
    assert body.count("images/favicon.svg") == 1


@pytest.mark.django_db
def test_change_form_keeps_the_header_and_moves_history_above_the_form(otp_client, populate_db):
    user = platform_admin(populate_db["users"])
    client = otp_client(user)

    body = client.get(reverse("admin:governanceplatform_user_change", args=[user.pk])).content.decode()
    tools = body[body.index('class="changeform-tools"') : body.index('id="user_form"')]

    assert body.count(f'href="{reverse("logout")}"') == 1
    assert 'class="addlink' not in body
    assert reverse("admin:governanceplatform_user_history", args=[user.pk]) in tools


@pytest.mark.django_db
def test_user_menu_is_in_the_header_not_the_sidebar(otp_client, populate_db):
    user = platform_admin(populate_db["users"])
    client = otp_client(user)

    body = client.get("/admin/").content.decode()
    menu = body[body.index('class="admin-dropdown admin-user-menu"') :]

    assert "openUserLinks" not in body
    assert "switchTheme(" not in body
    assert '<html lang="en" dir="ltr" class="light"' in body
    assert user.email in menu
    assert f'<span class="admin-user-menu-role">{user.get_permissions_groups()}</span>' in menu
    assert reverse("two_factor:profile") in menu
    assert reverse("password_change") in menu


@pytest.mark.django_db
def test_language_dropdown_submits_each_language(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get("/admin/").content.decode()
    form = body[body.index('id="set_language_form"') :]

    assert 'id="language_selector"' not in body
    assert form.count('name="language"') == len(settings.LANGUAGES)
    for code, _name in settings.LANGUAGES:
        assert f'value="{code}"' in form
    assert form.count('aria-current="true"') == 1


@pytest.mark.django_db
def test_pagination_links_to_the_neighbouring_pages(otp_client, populate_db, monkeypatch):
    monkeypatch.setattr(admin_site._registry[User], "list_per_page", 1)
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get("/admin/governanceplatform/user/?p=2").content.decode()
    pagination = body[body.index('class="admin-pagination"') :]
    total = pagination.split(" entries")[0].split()[-1]

    assert f"Showing 2 to 2 of {total} entries" in " ".join(pagination.split())
    assert '<span aria-current="page">2</span>' in pagination
    assert 'href="?p=1"' in pagination
    assert 'href="?p=3"' in pagination


@pytest.mark.django_db
def test_unpaginated_list_shows_only_the_count(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get("/admin/governanceplatform/user/").content.decode()
    pagination = body[body.index('class="admin-pagination"') :]

    assert "admin-pagination-pages" not in pagination
    assert str(User._meta.verbose_name_plural) in pagination.split("</div>")[0]


@pytest.mark.django_db
def test_regulator_user_cards_are_titled_with_the_user(otp_client, populate_db):
    admin = next(user for user in populate_db["users"] if user_in_group(user, "RegulatorAdmin"))
    regulator = admin.regulators.first()

    body = otp_client(admin).get(reverse("admin:governanceplatform_regulator_change", args=[regulator.pk])).content.decode()

    for regulator_user in regulator.regulatoruser_set.select_related("user"):
        assert f'<strong class="font-semibold select-none">{regulator_user}</strong>' in body


@pytest.mark.django_db
def test_regulator_user_cards_collapse_with_a_summary_and_a_toggle(otp_client, populate_db):
    admin = next(user for user in populate_db["users"] if user_in_group(user, "RegulatorAdmin"))
    regulator = admin.regulators.first()
    regulator_users = list(regulator.regulatoruser_set.all())

    body = otp_client(admin).get(reverse("admin:governanceplatform_regulator_change", args=[regulator.pk])).content.decode()

    assert body.count('class="inline-toggle"') == len(regulator_users) + 1  # the empty form for "Add another" too
    for regulator_user in regulator_users:
        assert f'<span class="inline-summary" x-show="!openRow">{regulator_user.get_inline_summary()}</span>' in body


@pytest.mark.django_db
def test_regulator_accounts_are_managed_from_the_regulator_not_the_user_form(otp_client, populate_db):
    admin = next(user for user in populate_db["users"] if user_in_group(user, "RegulatorAdmin"))
    account = User.objects.filter(regulators=admin.regulators.first()).exclude(pk=admin.pk).first()
    client = otp_client(admin)

    user_form = client.get(reverse("admin:governanceplatform_user_change", args=[account.pk])).content.decode()
    regulator_form = client.get(reverse("admin:governanceplatform_regulator_change", args=[admin.regulators.first().pk])).content.decode()

    assert 'id="regulatoruser_set-group"' not in user_form
    assert 'id="regulatoruser_set-group"' in regulator_form


def _initial_forms(body, prefix):
    return int(re.search(rf'name="{prefix}-INITIAL_FORMS" value="(\d+)"', body).group(1))


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("viewer_role", "link_model", "parent", "prefix"),
    [
        ("RegulatorAdmin", RegulatorUser, "regulator", "regulatoruser_set"),
        ("PlatformAdmin", ObserverUser, "observer", "observeruser_set"),
        ("RegulatorUser", CompanyUser, "company", "companyuser_set"),
    ],
)
def test_inlines_leave_out_deactivated_accounts(otp_client, populate_db, viewer_role, link_model, parent, prefix):
    viewer = next(user for user in populate_db["users"] if user_in_group(user, viewer_role))
    links = link_model.objects.exclude(user=viewer).select_related("user")
    if viewer_role == "RegulatorAdmin":
        links = links.filter(regulator=viewer.regulators.first())
    link = links.first()
    if viewer_role == "PlatformAdmin":
        # A platform administrator only sees the administrators of an observer.
        link.is_observer_administrator = True
        link.save()
    parent_pk = getattr(link, f"{parent}_id")
    url = reverse(f"admin:governanceplatform_{parent}_change", args=[parent_pk])
    client = otp_client(viewer)
    before = _initial_forms(client.get(url).content.decode(), prefix)

    link.user.is_active = False
    link.user.save()

    assert _initial_forms(client.get(url).content.decode(), prefix) == before - 1


@pytest.mark.django_db
def test_regulator_user_drop_down_offers_no_deactivated_account(otp_client, populate_db):
    admin = next(user for user in populate_db["users"] if user_in_group(user, "RegulatorAdmin"))
    removed = User.objects.create(email="removed@regulator.lu", is_active=False)
    removed.groups.add(Group.objects.get(name="RegulatorUser"))

    body = otp_client(admin).get(reverse("admin:governanceplatform_regulator_change", args=[admin.regulators.first().pk])).content.decode()

    assert "removed@regulator.lu" not in body


@pytest.mark.django_db
def test_regulator_user_summary_names_the_role_or_counts_the_sectors(populate_db):
    regulator_user = RegulatorUser.objects.filter(is_regulator_administrator=False).first()
    regulator_user.sectors.set(Sector.objects.all()[:2])

    assert regulator_user.get_inline_summary() == "2 sectors"

    regulator_user.is_regulator_administrator = True
    assert regulator_user.get_inline_summary() == "Administrator"


@pytest.mark.django_db
def test_observer_regulation_cards_are_titled_with_the_regulation(otp_client, populate_db):
    observer_regulation = ObserverRegulation.objects.select_related("observer", "regulation").first()
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get(reverse("admin:governanceplatform_observer_change", args=[observer_regulation.observer.pk])).content.decode()
    card = body[body.index(f'<strong class="font-semibold select-none">{observer_regulation.regulation}</strong>') :]

    assert f'<span class="inline-summary" x-show="!openRow">{observer_regulation.get_inline_summary()}</span>' in card


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("sector_count", "incident_rule", "summary"),
    [
        (0, {}, "All sectors · All incidents"),
        (2, {"conditions": [{"include": ["PUBLIC"]}]}, "2 sectors · 1 rule"),
        (1, {"conditions": [{"include": ["PUBLIC"]}, {"include": ["CRITICAL_INFRA"]}]}, "1 sector · 2 rules"),
    ],
)
def test_observer_regulation_summary_counts_sectors_and_rules(populate_db, sector_count, incident_rule, summary):
    observer_regulation = ObserverRegulation.objects.first()
    observer_regulation.incident_rule = incident_rule
    observer_regulation.sectors.set(Sector.objects.all()[:sector_count])

    assert observer_regulation.get_inline_summary() == summary


@pytest.mark.django_db
def test_add_button_is_labelled_in_the_list_toolbar(otp_client, populate_db):
    client = otp_client(platform_admin(populate_db["users"]))

    body = client.get("/admin/governanceplatform/user/").content.decode()
    toolbar = body[body.index('class="changelist-tools"') :]

    assert 'class="changelist-add-link' in toolbar
    assert f"Add {User._meta.verbose_name}" in toolbar
    assert 'class="addlink' not in body


def _secret_input(otp_client, users, connector):
    observer_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))
    url = reverse("admin:governanceplatform_observerconnector_change", args=[connector.pk])
    body = otp_client(observer_admin).get(url).content.decode()
    return re.search(r'<input[^>]*name="secret"[^>]*>', body).group(0)


@pytest.mark.django_db
def test_connector_secret_field_is_an_unfold_password_input(otp_client, populate_db, observer_connector):
    observer_connector.secret = None
    observer_connector.save()

    secret_input = _secret_input(otp_client, populate_db["users"], observer_connector)

    assert secret_input.count("type=") == 1
    assert 'type="password"' in secret_input
    assert "value=" not in secret_input
    assert "border-base-200" in secret_input  # Unfold's input classes


@pytest.mark.django_db
def test_connector_secret_field_masks_a_stored_secret(otp_client, populate_db, observer_connector):
    secret_input = _secret_input(otp_client, populate_db["users"], observer_connector)

    assert secret_input.count("type=") == 1
    assert 'type="password"' in secret_input
    assert f'value="{"*" * len("rt-token")}"' in secret_input


def test_conditional_question_option_selects_are_unfold_selects():
    form = ConditionalQuestionOptionForm()

    for name in ("report", "question_options", "predefined_answer", "next_question_options"):
        assert isinstance(form.fields[name].widget, UnfoldAdminSelectWidget), name


@pytest.mark.django_db
def test_sidebar_categories_fold_with_a_button_and_keep_the_current_one_open(otp_client, populate_db):
    body = otp_client(platform_admin(populate_db["users"])).get("/admin/governanceplatform/user/").content.decode()

    assert 'aria-controls="admin-nav-governanceplatform"' in body
    assert 'id="admin-nav-governanceplatform"' in body
    current = body[re.search(r'class="app-governanceplatform module\s+current-app\s*"', body).start() :]
    assert current.index('x-data="{ open: true }"') < current.index("admin-nav-group-toggle")
    assert "$persist(true).as('admin-nav-admin')" in body
