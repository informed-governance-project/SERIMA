"""Account actions an OperatorAdmin performs on the user accounts of its own company (#861)."""

from types import SimpleNamespace

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from governanceplatform.admin import UserAdmin
from governanceplatform.helpers import user_in_group
from governanceplatform.models import Company, CompanyUser, User

CHANGELIST_URL = "/admin/governanceplatform/user/"


def operator_client(otp_client, actor, company):
    """Log `actor` in and put `company` in session, as the company selection view would."""
    client = otp_client(actor)
    session = client.session
    session["company_in_use"] = company.id
    session.save()
    return client


def post_action(otp_client, context, action, target):
    client = operator_client(otp_client, context["operator_admin"], context["company"])
    return client.post(f"{CHANGELIST_URL}{target.pk}/{action}/")


def fake_request(actor, company, method="POST"):
    return SimpleNamespace(method=method, user=actor, session={"company_in_use": company.id})


def history_of(user):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(User),
        object_id=str(user.pk),
    )


def model_admin():
    return UserAdmin(User, None)


# --- company_links: the rule every account action is scoped by -------------------------------


@pytest.mark.django_db
def test_company_links_finds_the_pending_link(operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    request = fake_request(context["operator_admin"], context["company"])

    links = model_admin().company_links(request, User.objects.all(), approved=False)

    assert list(links) == [context["pending_link"]]


@pytest.mark.django_db
def test_company_links_never_leaves_the_active_company(operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    other_company = Company.objects.get(identifier="COM2")
    foreign = User.objects.get(email="iu2@iu.lu")
    CompanyUser.objects.create(user=foreign, company=other_company, approved=False)
    request = fake_request(context["operator_admin"], context["company"])

    links = model_admin().company_links(request, User.objects.all(), approved=False)

    assert foreign not in [link.user for link in links]


@pytest.mark.django_db
def test_company_links_excludes_the_callers_own_link(operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    context["admin_link"].approved = False
    context["admin_link"].save()
    request = fake_request(context["operator_admin"], context["company"])

    links = model_admin().company_links(request, User.objects.all(), approved=False)

    assert context["operator_admin"] not in [link.user for link in links]


@pytest.mark.django_db
def test_company_links_selects_by_approval_state(operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    request = fake_request(context["operator_admin"], context["company"])

    approved = model_admin().company_links(request, User.objects.all(), approved=True)

    assert context["member_link"] in list(approved)
    assert context["pending_link"] not in list(approved)


@pytest.mark.django_db
def test_company_links_is_empty_on_a_get(operator_admin_with_pending_link):
    """The actions change state, so nothing is reachable outside a POST."""
    context = operator_admin_with_pending_link
    request = fake_request(context["operator_admin"], context["company"], method="GET")

    assert not model_admin().company_links(request, User.objects.all(), approved=False).exists()


@pytest.mark.django_db
def test_company_links_is_empty_for_a_non_operator_admin(operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    request = fake_request(User.objects.get(email="opuser@com1.lu"), context["company"])

    assert not model_admin().company_links(request, User.objects.all(), approved=False).exists()


@pytest.mark.django_db
def test_company_links_is_empty_without_an_active_company(operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    request = SimpleNamespace(method="POST", user=context["operator_admin"], session={})

    assert not model_admin().company_links(request, User.objects.all(), approved=False).exists()


# --- approve ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_approve_marks_the_link_approved(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    post_action(otp_client, context, "approve-company-link", context["incident_user"])

    context["pending_link"].refresh_from_db()
    assert context["pending_link"].approved is True


@pytest.mark.django_db
def test_approve_upgrades_the_incident_user_role(otp_client, operator_admin_with_pending_link):
    """The CompanyUser post_save signal does this, which a bulk update would skip."""
    context = operator_admin_with_pending_link
    assert user_in_group(context["incident_user"], "IncidentUser")

    post_action(otp_client, context, "approve-company-link", context["incident_user"])

    context["incident_user"].refresh_from_db()
    assert user_in_group(context["incident_user"], "OperatorUser")
    assert not user_in_group(context["incident_user"], "IncidentUser")


@pytest.mark.django_db
def test_approve_associates_the_already_notified_incidents(otp_client, operator_admin_with_pending_link):
    """The consequence the confirmation dialog warns about."""
    from incidents.models import Incident

    context = operator_admin_with_pending_link
    incident = Incident.objects.create(contact_user=context["incident_user"])

    post_action(otp_client, context, "approve-company-link", context["incident_user"])

    incident.refresh_from_db()
    assert incident.company == context["company"]
    assert incident.incident_id.startswith(context["company"].identifier)


@pytest.mark.django_db
def test_approve_is_recorded_in_the_account_history(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    post_action(otp_client, context, "approve-company-link", context["incident_user"])

    entry = history_of(context["incident_user"]).get()
    assert entry.action_flag == CHANGE
    assert entry.user == context["operator_admin"]
    assert entry.get_change_message() == "Approved the link with the operator."


@pytest.mark.django_db
def test_approve_refuses_a_get(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    response = client.get(f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/")

    assert response.status_code == 404
    context["pending_link"].refresh_from_db()
    assert context["pending_link"].approved is False


@pytest.mark.django_db
def test_approve_refuses_a_link_in_another_company(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    other_company = Company.objects.get(identifier="COM2")
    foreign = User.objects.get(email="iu2@iu.lu")
    foreign_link = CompanyUser.objects.create(user=foreign, company=other_company, approved=False)

    response = post_action(otp_client, context, "approve-company-link", foreign)

    assert response.status_code == 404
    foreign_link.refresh_from_db()
    assert foreign_link.approved is False


@pytest.mark.django_db
def test_approve_refuses_the_callers_own_link(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    context["admin_link"].approved = False
    context["admin_link"].save()

    response = post_action(otp_client, context, "approve-company-link", context["operator_admin"])

    assert response.status_code == 404
    context["admin_link"].refresh_from_db()
    assert context["admin_link"].approved is False


@pytest.mark.django_db
def test_approve_is_closed_to_regulators(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = otp_client(User.objects.get(email="reguser@reg1.lu"))

    response = client.post(f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/")

    assert response.status_code == 404
    context["pending_link"].refresh_from_db()
    assert context["pending_link"].approved is False


# --- reject ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_reject_removes_the_link(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    post_action(otp_client, context, "reject-company-link", context["incident_user"])

    assert not CompanyUser.objects.filter(user=context["incident_user"], company=context["company"]).exists()


@pytest.mark.django_db
def test_reject_demotes_and_deactivates_the_account(otp_client, operator_admin_with_pending_link):
    """
    The CompanyUser post_delete signal deactivates an account left with no company link, so the
    rejected account is demoted to IncidentUser and disabled.
    """
    context = operator_admin_with_pending_link

    post_action(otp_client, context, "reject-company-link", context["incident_user"])

    context["incident_user"].refresh_from_db()
    assert user_in_group(context["incident_user"], "IncidentUser")
    assert context["incident_user"].is_active is False


@pytest.mark.django_db
def test_reject_is_recorded_in_the_account_history(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    post_action(otp_client, context, "reject-company-link", context["incident_user"])

    assert history_of(context["incident_user"]).get().get_change_message() == "Rejected the link with the operator."


@pytest.mark.django_db
def test_reject_refuses_a_link_in_another_company(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    other_company = Company.objects.get(identifier="COM2")
    foreign = User.objects.get(email="iu2@iu.lu")
    CompanyUser.objects.create(user=foreign, company=other_company, approved=False)

    response = post_action(otp_client, context, "reject-company-link", foreign)

    assert response.status_code == 404
    assert CompanyUser.objects.filter(user=foreign, company=other_company).exists()


# --- toggle_user_role ------------------------------------------------------------------------


@pytest.mark.django_db
def test_toggle_promotes_to_administrator(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    post_action(otp_client, context, "toggle-user-role", context["member"])

    context["member_link"].refresh_from_db()
    context["member"].refresh_from_db()
    assert context["member_link"].is_company_administrator is True
    assert user_in_group(context["member"], "OperatorAdmin")


@pytest.mark.django_db
def test_toggle_demotes_an_administrator(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    context["member_link"].is_company_administrator = True
    context["member_link"].save()

    post_action(otp_client, context, "toggle-user-role", context["member"])

    context["member_link"].refresh_from_db()
    context["member"].refresh_from_db()
    assert context["member_link"].is_company_administrator is False
    assert user_in_group(context["member"], "OperatorUser")


@pytest.mark.django_db
def test_toggle_records_the_direction_in_the_history(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    client.post(f"{CHANGELIST_URL}{context['member'].pk}/toggle-user-role/")
    client.post(f"{CHANGELIST_URL}{context['member'].pk}/toggle-user-role/")

    messages = [entry.get_change_message() for entry in history_of(context["member"]).order_by("action_time")]
    assert messages == ["Changed as administrator of the operator.", "Removed as administrator of the operator."]


@pytest.mark.django_db
def test_toggle_refuses_an_account_awaiting_approval(otp_client, operator_admin_with_pending_link):
    """The role of an account that is not a member yet is not the operator's to change."""
    context = operator_admin_with_pending_link

    response = post_action(otp_client, context, "toggle-user-role", context["incident_user"])

    assert response.status_code == 404
    context["pending_link"].refresh_from_db()
    assert context["pending_link"].is_company_administrator is False


# --- reset_2FA_token -------------------------------------------------------------------------


@pytest.mark.django_db
def test_reset_2fa_deletes_the_devices(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    TOTPDevice.objects.create(user=context["member"], name="device", confirmed=True)

    post_action(otp_client, context, "reset-2fa-token", context["member"])

    assert not TOTPDevice.objects.filter(user=context["member"]).exists()


@pytest.mark.django_db
def test_reset_2fa_is_recorded_in_the_account_history(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    TOTPDevice.objects.create(user=context["member"], name="device", confirmed=True)

    post_action(otp_client, context, "reset-2fa-token", context["member"])

    assert history_of(context["member"]).get().get_change_message() == "Reset the 2FA token."


@pytest.mark.django_db
def test_reset_2fa_refuses_an_account_awaiting_approval(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    TOTPDevice.objects.create(user=context["incident_user"], name="device", confirmed=True)

    response = post_action(otp_client, context, "reset-2fa-token", context["incident_user"])

    assert response.status_code == 404
    assert TOTPDevice.objects.filter(user=context["incident_user"]).exists()


# --- redirect_to_changelist ------------------------------------------------------------------


@pytest.mark.django_db
def test_the_operator_returns_to_the_filtered_changelist(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    response = client.post(
        f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/",
        {"changelist_filters": "q=iu1"},
    )

    assert response["Location"] == f"{CHANGELIST_URL}?q=iu1"


@pytest.mark.django_db
def test_the_redirect_cannot_leave_the_changelist(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    response = client.post(
        f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/",
        {"changelist_filters": "//evil.example.com"},
    )

    assert response["Location"].startswith(CHANGELIST_URL)


# --- the changelist column -------------------------------------------------------------------


@pytest.mark.django_db
def test_the_column_is_offered_to_operator_admins_only(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    operator = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL)
    regulator = otp_client(User.objects.get(email="reguser@reg1.lu")).get(CHANGELIST_URL)

    assert "account_actions" in operator.context["cl"].list_display
    assert "account_actions" not in regulator.context["cl"].list_display


@pytest.mark.django_db
def test_a_pending_row_offers_approve_and_reject(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL).content.decode()

    assert f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/" in body
    assert f"{CHANGELIST_URL}{context['incident_user'].pk}/reject-company-link/" in body


@pytest.mark.django_db
def test_an_approved_row_offers_the_role_and_2fa_actions(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL).content.decode()

    assert f"{CHANGELIST_URL}{context['member'].pk}/toggle-user-role/" in body
    assert f"{CHANGELIST_URL}{context['member'].pk}/reset-2fa-token/" in body
    assert f"{CHANGELIST_URL}{context['member'].pk}/approve-company-link/" not in body


@pytest.mark.django_db
def test_the_callers_own_row_offers_nothing(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL).content.decode()

    for action in ("approve-company-link", "reject-company-link", "toggle-user-role", "reset-2fa-token"):
        assert f"{CHANGELIST_URL}{context['operator_admin'].pk}/{action}/" not in body


@pytest.mark.django_db
def test_the_role_label_tracks_the_current_role(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])
    assert "Set Administrator" in client.get(CHANGELIST_URL).content.decode()

    context["member_link"].is_company_administrator = True
    context["member_link"].save()

    assert "Unset Administrator" in client.get(CHANGELIST_URL).content.decode()


@pytest.mark.django_db
def test_every_button_carries_its_own_confirmation_message(otp_client, operator_admin_with_pending_link):
    """The dialog reads its text from the button, so the copy has to reach the page."""
    context = operator_admin_with_pending_link

    body = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL).content.decode()

    # Fragments rather than whole sentences: the wording is still being tuned, the consequence
    # reaching the button is what matters.
    assert "notified incidents" in body
    assert "suggested link" in body
    assert "logged out" in body
    assert "new authenticator" in body


# --- the banner ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_banner_announces_a_pending_suggestion(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL).content.decode()

    assert "There is a suggestion to link a User Account to your company" in body


@pytest.mark.django_db
def test_no_banner_when_nothing_is_pending(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    context["pending_link"].delete()

    body = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL).content.decode()

    assert "There is a suggestion to link a User Account" not in body


# --- the detail view -------------------------------------------------------------------------


@pytest.mark.django_db
def test_operator_admins_get_the_custom_change_form(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    response = operator_client(otp_client, context["operator_admin"], context["company"]).get(
        f"{CHANGELIST_URL}{context['member'].pk}/change/"
    )

    assert "admin/custom_change_user_form.html" in [template.name for template in response.templates if template.name]


@pytest.mark.django_db
def test_other_roles_keep_the_default_change_form(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    response = otp_client(User.objects.get(email="regadmin@reg1.lu")).get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")

    assert "admin/custom_change_user_form.html" not in [template.name for template in response.templates if template.name]


@pytest.mark.django_db
def test_the_template_choice_does_not_leak_between_requests(otp_client, operator_admin_with_pending_link):
    """Assigning self.change_form_template would persist on the shared ModelAdmin instance."""
    context = operator_admin_with_pending_link
    operator_client(otp_client, context["operator_admin"], context["company"]).get(f"{CHANGELIST_URL}{context['member'].pk}/change/")

    response = otp_client(User.objects.get(email="regadmin@reg1.lu")).get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")

    assert "admin/custom_change_user_form.html" not in [template.name for template in response.templates if template.name]


@pytest.mark.django_db
def test_each_field_action_shares_a_row_with_its_field(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    response = operator_client(otp_client, context["operator_admin"], context["company"]).get(
        f"{CHANGELIST_URL}{context['member'].pk}/change/"
    )
    rows = [row for _, options in response.context["adminform"].fieldsets for row in options["fields"]]

    assert ("get_2FA_activation", "reset_2FA_action") in rows
    assert ("get_is_administrator", "administrator_action") in rows


@pytest.mark.django_db
def test_the_detail_view_offers_the_field_actions_for_an_approved_account(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = (
        operator_client(otp_client, context["operator_admin"], context["company"])
        .get(f"{CHANGELIST_URL}{context['member'].pk}/change/")
        .content.decode()
    )

    assert f"{CHANGELIST_URL}{context['member'].pk}/reset-2fa-token/" in body
    assert f"{CHANGELIST_URL}{context['member'].pk}/toggle-user-role/" in body


@pytest.mark.django_db
def test_the_detail_view_role_label_tracks_the_current_role(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])
    url = f"{CHANGELIST_URL}{context['member'].pk}/change/"
    assert "Set Administrator" in client.get(url).content.decode()

    context["member_link"].is_company_administrator = True
    context["member_link"].save()

    assert "Unset Administrator" in client.get(url).content.decode()


@pytest.mark.django_db
def test_the_detail_view_hides_the_field_actions_for_a_pending_account(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = (
        operator_client(otp_client, context["operator_admin"], context["company"])
        .get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")
        .content.decode()
    )

    assert f"{CHANGELIST_URL}{context['incident_user'].pk}/reset-2fa-token/" not in body
    assert f"{CHANGELIST_URL}{context['incident_user'].pk}/toggle-user-role/" not in body


@pytest.mark.django_db
def test_the_detail_view_prompts_to_resolve_a_pending_suggestion(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = (
        operator_client(otp_client, context["operator_admin"], context["company"])
        .get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")
        .content.decode()
    )

    assert f"Add this user to Company {context['company'].name}?" in body
    assert f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/" in body


@pytest.mark.django_db
def test_the_prompt_sits_above_the_form(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = (
        operator_client(otp_client, context["operator_admin"], context["company"])
        .get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")
        .content.decode()
    )

    assert body.index('class="titles-and-tools"') < body.index('class="pending-link-prompt"') < body.index('id="content-main"')


@pytest.mark.django_db
def test_no_prompt_for_an_approved_account(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    body = (
        operator_client(otp_client, context["operator_admin"], context["company"])
        .get(f"{CHANGELIST_URL}{context['member'].pk}/change/")
        .content.decode()
    )

    assert "pending-link-prompt" not in body


# --- what an account awaiting approval withholds ---------------------------------------------


@pytest.mark.django_db
def test_a_pending_account_is_read_only(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    response = operator_client(otp_client, context["operator_admin"], context["company"]).get(
        f"{CHANGELIST_URL}{context['incident_user'].pk}/change/"
    )

    assert response.context["has_change_permission"] is False
    assert response.context["has_delete_permission"] is False
    assert 'name="_save"' not in response.content.decode()


@pytest.mark.django_db
def test_a_pending_account_cannot_be_edited(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    original = context["incident_user"].first_name

    response = operator_client(otp_client, context["operator_admin"], context["company"]).post(
        f"{CHANGELIST_URL}{context['incident_user'].pk}/change/",
        {"first_name": "Renamed", "last_name": "X", "email": context["incident_user"].email},
    )

    assert response.status_code == 403
    context["incident_user"].refresh_from_db()
    assert context["incident_user"].first_name == original


@pytest.mark.django_db
def test_a_pending_account_cannot_be_deleted(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    assert client.get(f"{CHANGELIST_URL}{context['incident_user'].pk}/delete/").status_code == 403
    assert client.post(f"{CHANGELIST_URL}{context['incident_user'].pk}/delete/", {"post": "yes"}).status_code == 403
    assert CompanyUser.objects.filter(user=context["incident_user"], company=context["company"]).exists()


@pytest.mark.django_db
def test_approving_restores_both_permissions(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    client.post(f"{CHANGELIST_URL}{context['incident_user'].pk}/approve-company-link/")

    response = client.get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")
    assert response.context["has_change_permission"] is True
    assert response.context["has_delete_permission"] is True


@pytest.mark.django_db
def test_an_approved_account_stays_editable(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    response = operator_client(otp_client, context["operator_admin"], context["company"]).get(
        f"{CHANGELIST_URL}{context['member'].pk}/change/"
    )

    assert response.context["has_change_permission"] is True


@pytest.mark.django_db
def test_the_predicate_works_on_an_instance_without_annotations(operator_admin_with_pending_link):
    """
    Django calls the permission methods with objects that never went through get_queryset, such as
    the one response_add hands back straight from form.save().
    """
    context = operator_admin_with_pending_link
    request = fake_request(context["operator_admin"], context["company"])
    plain_member = User.objects.get(pk=context["member"].pk)
    plain_pending = User.objects.get(pk=context["incident_user"].pk)

    assert not hasattr(plain_member, "has_pending_company_link")
    assert model_admin().is_awaiting_approval(request, plain_member) is False
    assert model_admin().is_awaiting_approval(request, plain_pending) is True


@pytest.mark.django_db
def test_an_operator_admin_can_still_create_a_user(otp_client, operator_admin_with_pending_link):
    """response_add asks for change permission on the unannotated object it just saved."""
    context = operator_admin_with_pending_link
    email = "created_by_operator@com1.lu"

    response = operator_client(otp_client, context["operator_admin"], context["company"]).post(
        "/admin/governanceplatform/user/add/",
        {"email": email, "first_name": "New", "last_name": "User"},
        follow=True,
    )

    assert response.status_code == 200
    assert CompanyUser.objects.filter(user__email=email, company=context["company"]).exists()


@pytest.mark.django_db
def test_a_regulator_keeps_its_rights_over_a_pending_account(otp_client, operator_admin_with_pending_link):
    context = operator_admin_with_pending_link

    response = otp_client(User.objects.get(email="regadmin@reg1.lu")).get(f"{CHANGELIST_URL}{context['incident_user'].pk}/change/")

    assert response.context["has_change_permission"] is True


# --- delete ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_deleting_an_approved_account_only_unlinks_it(otp_client, operator_admin_with_pending_link):
    """delete_model drops the company link for an operator admin rather than deleting the account."""
    context = operator_admin_with_pending_link

    response = operator_client(otp_client, context["operator_admin"], context["company"]).post(
        f"{CHANGELIST_URL}{context['member'].pk}/delete/", {"post": "yes"}
    )

    assert response.status_code == 302
    assert User.objects.filter(pk=context["member"].pk).exists()
    assert not CompanyUser.objects.filter(user=context["member"], company=context["company"]).exists()


@pytest.mark.django_db
def test_the_delete_link_carries_a_confirmation_message(otp_client, operator_admin_with_pending_link):
    """The dialog replaces Django's confirmation page, so the consequence has to reach the page."""
    context = operator_admin_with_pending_link

    body = (
        operator_client(otp_client, context["operator_admin"], context["company"])
        .get(f"{CHANGELIST_URL}{context['member'].pk}/change/")
        .content.decode()
    )
    holder = body[body.index('id="account-delete-confirm"') :][:400]

    assert 'class="deletelink"' in body
    assert "data-confirm-message" in holder
    assert context["member"].email in holder


@pytest.mark.django_db
def test_unlinking_the_last_company_deactivates_the_account(otp_client, operator_admin_with_pending_link):
    """
    Issue requirement: an account left with no operator is disabled. The CompanyUser post_delete
    signal does it, so it applies to the delete path as well as to reject.
    """
    context = operator_admin_with_pending_link
    assert context["member"].companies.count() == 1

    operator_client(otp_client, context["operator_admin"], context["company"]).post(
        f"{CHANGELIST_URL}{context['member'].pk}/delete/", {"post": "yes"}
    )

    context["member"].refresh_from_db()
    assert context["member"].is_active is False


@pytest.mark.django_db
def test_unlinking_one_company_does_not_re_enable_a_disabled_account(otp_client, operator_admin_with_pending_link):
    """
    Losing a link is not a reason to re-enable an account. An account disabled on purpose stays
    disabled when an operator removes one of its other company links.
    """
    context = operator_admin_with_pending_link
    member = context["member"]
    CompanyUser.objects.create(user=member, company=Company.objects.get(identifier="COM2"), approved=True)
    member.refresh_from_db()
    member.is_active = False
    member.save(update_fields=["is_active"])

    operator_client(otp_client, context["operator_admin"], context["company"]).post(f"{CHANGELIST_URL}{member.pk}/delete/", {"post": "yes"})

    member.refresh_from_db()
    assert member.is_active is False


@pytest.mark.django_db
def test_the_permission_question_is_asked_once_per_object(operator_admin_with_pending_link):
    """
    Django asks for change and delete permission repeatedly while rendering one page, and the
    answer costs a query, so it is only looked up once.
    """
    context = operator_admin_with_pending_link
    request = fake_request(context["operator_admin"], context["company"])
    pending = User.objects.get(pk=context["incident_user"].pk)
    admin = model_admin()

    with CaptureQueriesContext(connection) as queries:
        for _ in range(5):
            assert admin.is_awaiting_approval(request, pending) is True

    pending_lookups = [q for q in queries.captured_queries if 'FROM "governanceplatform_companyuser"' in q["sql"]]
    assert len(pending_lookups) == 1
    assert len(queries.captured_queries) <= 3


@pytest.mark.django_db
def test_the_2fa_column_counts_a_static_device(otp_client, operator_admin_with_pending_link):
    """
    otp_static is installed, so the column has to answer for every device type the platform
    accepts, not only for TOTP.
    """
    context = operator_admin_with_pending_link
    StaticDevice.objects.create(user=context["member"], name="backup tokens", confirmed=True)

    response = operator_client(otp_client, context["operator_admin"], context["company"]).get(CHANGELIST_URL)
    row = next(user for user in response.context["cl"].queryset if user.pk == context["member"].pk)

    assert row.has_2fa is True
    assert model_admin().get_2FA_activation(row) is True


@pytest.mark.django_db
def test_the_changelist_cost_does_not_grow_with_the_number_of_rows(otp_client, operator_admin_with_pending_link):
    """The 2FA column used to query per row instead of reading the annotation."""
    context = operator_admin_with_pending_link
    client = operator_client(otp_client, context["operator_admin"], context["company"])

    with CaptureQueriesContext(connection) as before:
        client.get(CHANGELIST_URL)

    for index in range(6):
        extra = User.objects.create(email=f"extra{index}@com1.lu", first_name="x", last_name="y")
        CompanyUser.objects.create(user=extra, company=context["company"], approved=True)

    with CaptureQueriesContext(connection) as after:
        client.get(CHANGELIST_URL)

    assert len(after.captured_queries) <= len(before.captured_queries) + 2
