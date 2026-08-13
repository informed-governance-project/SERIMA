from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from governanceplatform import helpers


def test_table_exists(monkeypatch):
    """Return whether the requested table is present in the database schema."""
    monkeypatch.setattr(helpers.connection.introspection, "table_names", lambda: ["users", "incidents"])

    assert helpers.table_exists("users") is True
    assert helpers.table_exists("missing") is False


def test_generate_token(monkeypatch):
    """Generate a URL-safe token limited to 32 characters."""
    monkeypatch.setattr(helpers.secrets, "token_urlsafe", lambda length: "a" * length + "ignored")

    assert helpers.generate_token() == "a" * 32


@pytest.mark.parametrize(("authenticated", "groups", "expected"), [(False, ["RegulatorUser"], False), (True, ["RegulatorAdmin"], False)])
def test_user_in_group(authenticated, groups, expected):
    """Check group membership only for authenticated users."""
    user = SimpleNamespace(
        is_authenticated=authenticated,
        groups=SimpleNamespace(all=lambda: [SimpleNamespace(name=name) for name in groups]),
    )

    assert helpers.user_in_group(user, "RegulatorUser") is expected


def test_instance_user_in_group():
    """Detect whether a user instance belongs to the requested group."""
    user = SimpleNamespace(groups=SimpleNamespace(all=lambda: [SimpleNamespace(name="OperatorUser")]))

    assert helpers.instance_user_in_group(user, "OperatorUser") is True
    assert helpers.instance_user_in_group(user, "RegulatorUser") is False


@pytest.mark.parametrize(
    ("helper", "matching_group"),
    [
        (helpers.is_user_regulator, "RegulatorUser"),
        (helpers.is_user_operator, "OperatorAdmin"),
        (helpers.is_observer_user, "ObserverUser"),
    ],
)
def test_role_helpers_accept_one_of_their_groups(monkeypatch, helper, matching_group):
    """Recognize users belonging to one of the groups for each supported role."""
    monkeypatch.setattr(helpers, "user_in_group", lambda user, group: group == matching_group)

    assert helper(object()) is True


@pytest.mark.parametrize(
    ("is_observer", "is_receiving_all_incident", "expected"),
    [(False, None, False), (True, None, False), (True, True, True)],
)
def test_is_observer_user_viewing_all_incident(monkeypatch, is_observer, is_receiving_all_incident, expected):
    """Allow global incident access only to observers configured for it."""
    monkeypatch.setattr(helpers, "is_observer_user", lambda user: is_observer)
    observer_instance = None if is_receiving_all_incident is None else SimpleNamespace(is_receiving_all_incident=is_receiving_all_incident)
    user = SimpleNamespace(observers=SimpleNamespace(first=lambda: observer_instance))

    assert helpers.is_observer_user_viewing_all_incident(user) is expected


def test_get_active_company_from_session():
    """Return the user's company selected in the current session."""
    company = object()
    companies = MagicMock()
    companies.filter.return_value.first.return_value = company
    request = SimpleNamespace(session={"company_in_use": 42}, user=SimpleNamespace(companies=companies))

    assert helpers.get_active_company_from_session(request) is company
    companies.filter.assert_called_once_with(id=42)


def test_get_active_company_from_session_without_selected_company():
    """Return no company when the session has no active company selection."""
    companies = MagicMock()
    request = SimpleNamespace(session={}, user=SimpleNamespace(companies=companies))

    assert helpers.get_active_company_from_session(request) is None
    companies.filter.assert_not_called()


def test_can_access_incident_for_incident_owner(monkeypatch):
    """Allow an incident user to access an incident they own."""
    user = object()
    incident = SimpleNamespace(id=7)
    monkeypatch.setattr(helpers, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(helpers, "is_user_operator", lambda user: False)
    monkeypatch.setattr(helpers, "is_observer_user", lambda user: False)
    monkeypatch.setattr(helpers, "is_observer_user_viewing_all_incident", lambda user: False)
    monkeypatch.setattr(helpers, "user_in_group", lambda user, group: group == "IncidentUser")
    incident_filter = MagicMock()
    incident_filter.exists.return_value = True
    monkeypatch.setattr(helpers.Incident.objects, "filter", lambda **kwargs: incident_filter)

    assert helpers.can_access_incident(user, incident) is True


def test_can_access_incident_rejects_non_owner(monkeypatch):
    """Reject an incident user who does not own the incident."""
    user = object()
    incident = SimpleNamespace(id=7)

    monkeypatch.setattr(helpers, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(helpers, "is_user_operator", lambda user: False)
    monkeypatch.setattr(helpers, "is_observer_user", lambda user: False)
    monkeypatch.setattr(
        helpers,
        "is_observer_user_viewing_all_incident",
        lambda user: False,
    )
    monkeypatch.setattr(
        helpers,
        "user_in_group",
        lambda user, group: group == "IncidentUser",
    )

    incident_filter = MagicMock()
    incident_filter.exists.return_value = False
    monkeypatch.setattr(
        helpers.Incident.objects,
        "filter",
        lambda **kwargs: incident_filter,
    )

    assert helpers.can_access_incident(user, incident) is False


def test_can_create_incident_report_rejects_unrelated_user(monkeypatch):
    """Reject report creation when the user has no relationship to the incident."""
    monkeypatch.setattr(helpers, "user_in_group", lambda user, group: False)
    monkeypatch.setattr(helpers, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(helpers, "is_user_operator", lambda user: False)

    assert helpers.can_create_incident_report(object(), SimpleNamespace(contact_user=None)) is False


def test_can_edit_incident_report_for_matching_regulator_admin(monkeypatch):
    """Allow a regulator administrator to edit an incident for their regulator."""
    regulator = object()
    user = SimpleNamespace(regulators=SimpleNamespace(first=lambda: regulator))
    incident = SimpleNamespace(contact_user=None, sector_regulation=SimpleNamespace(regulator=regulator))
    monkeypatch.setattr(helpers, "user_in_group", lambda user, group: group == "RegulatorAdmin")
    monkeypatch.setattr(helpers, "is_user_regulator", lambda user: False)
    monkeypatch.setattr(helpers, "is_user_operator", lambda user: False)

    assert helpers.can_edit_incident_report(user, incident) is True


def test_set_creator_sets_current_regulator_on_new_object():
    """Assign the current regulator as the creator of a new object."""
    regulator = SimpleNamespace(id=9)
    request = SimpleNamespace(user=SimpleNamespace(regulators=SimpleNamespace(first=lambda: regulator)))
    obj = SimpleNamespace(creator_name=None, creator_id=None)

    assert helpers.set_creator(request, obj, change=False) is obj
    assert obj.creator_name is regulator
    assert obj.creator_id == 9


def test_can_change_or_delete_unsaved_object():
    """Allow changes to an object that has not been saved yet."""
    request = SimpleNamespace()
    obj = SimpleNamespace(pk=None)

    assert helpers.can_change_or_delete_obj(request, obj) is True


def test_can_change_or_delete_workflow_owned_by_regulator(monkeypatch):
    """Allow only the regulator owning an unused workflow to modify it."""
    regulator = object()
    other_regulator = object()
    owner_request = SimpleNamespace(user=SimpleNamespace(regulators=SimpleNamespace(first=lambda: regulator)))
    other_request = SimpleNamespace(user=SimpleNamespace(regulators=SimpleNamespace(first=lambda: other_regulator)))
    workflow = MagicMock(spec=helpers.Workflow)
    workflow.pk = 4
    workflow.creator = regulator
    workflow._meta = SimpleNamespace(verbose_name="workflow")
    warning = MagicMock()
    monkeypatch.setattr(helpers.messages, "warning", warning)

    assert helpers.can_change_or_delete_obj(owner_request, workflow) is True
    assert helpers.can_change_or_delete_obj(other_request, workflow) is False
    warning.assert_called_once()


def test_translated_queryset_adds_fallback_and_sort_annotations():
    """Add requested-language, fallback, and case-insensitive sort annotations."""
    initial = MagicMock()
    with_language_values = MagicMock()
    with_fallback = MagicMock()
    final = MagicMock()
    initial.annotate.return_value = with_language_values
    with_language_values.annotate.return_value = with_fallback
    with_fallback.annotate.return_value = final

    result = helpers.translated_queryset(initial, "fr", "en", ["label"], orderable=True)

    assert result is final
    assert set(initial.annotate.call_args.kwargs) == {"_label_lang", "_label_default"}
    assert set(with_language_values.annotate.call_args.kwargs) == {"_label"}
    assert set(with_fallback.annotate.call_args.kwargs) == {"_label_sort"}


@override_settings(PARLER_DEFAULT_LANGUAGE_CODE="en")
def test_annotate_translated_field_from_related_models(monkeypatch):
    """Annotate a related translated field with the configured language fallback."""
    monkeypatch.setattr(helpers.translation, "get_language", lambda: "fr")
    initial = MagicMock()
    translated = MagicMock()
    final = MagicMock()
    initial.annotate.return_value = translated
    translated.annotate.return_value = final

    result = helpers.annotate_translated_field_from_related_models(
        initial,
        full_path="sector__translations__label",
        annotated_name="sector_label",
    )

    assert result is final
    assert set(initial.annotate.call_args.kwargs) == {"_label_lang", "_label_default"}
    assert set(translated.annotate.call_args.kwargs) == {"sector_label"}


def test_generate_display_methods_for_direct_and_related_fields():
    """Generate admin display methods for direct and related translated fields."""
    methods = helpers.generate_display_methods(["label"], [("sector", "name")])
    admin = object()
    related = SimpleNamespace(safe_translation_getter=lambda field, any_language: "Energy")
    obj = SimpleNamespace(_label="Question", sector=related)

    assert methods["label_display"](admin, obj) == "Question"
    assert methods["label_display"].admin_order_field == "_label"
    assert methods["sector_display"](admin, obj) == "Energy"


@override_settings(LANGUAGE_CODE="en", LANGUAGES=(("en", "English"), ("fr", "French")))
def test_render_to_string_multi_languages_skips_identical_translation(monkeypatch):
    """Exclude duplicate non-default translations from multilingual rendering."""
    monkeypatch.setattr(helpers.translation, "override", lambda language: nullcontext())
    monkeypatch.setattr(helpers.translation, "gettext", lambda name: name)
    monkeypatch.setattr(helpers, "render_to_string", lambda template, context: "same content")

    assert helpers.render_to_string_multi_languages("email.html", {}) == "<h3>English (en)</h3>\n                same content"


def test_sanitize_html_removes_scripts_and_unsafe_styles():
    """Strip disallowed tags and CSS properties while retaining safe content."""
    html = '<p style="color: red; position: fixed">Safe</p><script>alert(1)</script>'

    sanitized = helpers.sanitize_html(html)

    assert sanitized == '<p style="color: red;">Safe</p>alert(1)'
