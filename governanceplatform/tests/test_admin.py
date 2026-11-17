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


def _token_input(otp_client, users):
    """Only observer accounts see the RT configuration, on their own observer."""
    observer_admin = next(user for user in users if user_in_group(user, "ObserverAdmin"))
    observer = observer_admin.observers.first()
    body = otp_client(observer_admin).get(reverse("admin:governanceplatform_observer_change", args=[observer.pk])).content.decode()
    return re.search(r'<input[^>]*name="rt_token"[^>]*>', body).group(0)


@pytest.mark.django_db
def test_observer_token_field_is_an_unfold_password_input(otp_client, populate_db):
    token_input = _token_input(otp_client, populate_db["users"])

    assert token_input.count("type=") == 1
    assert 'type="password"' in token_input
    assert "value=" not in token_input
    assert "border-base-200" in token_input  # Unfold's input classes


@pytest.mark.django_db
def test_observer_token_field_masks_a_stored_token(otp_client, populate_db):
    observer = next(user for user in populate_db["users"] if user_in_group(user, "ObserverAdmin")).observers.first()
    observer.rt_token = "secret-token"
    observer.save()

    token_input = _token_input(otp_client, populate_db["users"])

    assert token_input.count("type=") == 1
    assert 'type="password"' in token_input
    assert f'value="{"*" * len("secret-token")}"' in token_input


def test_conditional_question_option_selects_are_unfold_selects():
    form = ConditionalQuestionOptionForm()

    for name in ("report", "question_options", "predefined_answer", "next_question_options"):
        assert isinstance(form.fields[name].widget, UnfoldAdminSelectWidget), name
