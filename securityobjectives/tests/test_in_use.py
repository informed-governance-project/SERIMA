"""Whether a security-objectives object still has answers referencing it.

can_change_or_delete_obj asks each object this via is_in_use() to decide whether its
creator may still edit or delete it, so a method that answered from the wrong table
would silently unlock objects operators have already answered against.
"""

import pytest

from governanceplatform.helpers import can_change_or_delete_obj
from governanceplatform.models import User
from securityobjectives.models import (
    MaturityLevel,
    SecurityMeasureAnswer,
    SecurityObjectiveEmail,
    StandardAnswer,
)


class _CollectingMessages:
    """Stand-in for the message store MessageMiddleware normally attaches."""

    def __init__(self):
        self.added = []

    def add(self, level, message, extra_tags=""):
        self.added.append((level, message))


@pytest.fixture
def answered(populate_so_db):
    """One answered security measure, with the objective, domain and standard above it."""
    answer = SecurityMeasureAnswer.objects.select_related("security_measure__security_objective__domain").first()
    measure = answer.security_measure
    return {
        "standard": populate_so_db["sas"][0].standard,
        "domain": measure.security_objective.domain,
        "security_objective": measure.security_objective,
        "security_measure": measure,
    }


@pytest.mark.django_db()
def test_standard_is_in_use_while_an_answer_references_it(answered):
    standard = answered["standard"]
    assert standard.is_in_use() is True

    StandardAnswer.objects.filter(standard=standard).delete()

    assert standard.is_in_use() is False


@pytest.mark.django_db()
def test_security_measure_is_in_use_while_an_answer_references_it(answered):
    measure = answered["security_measure"]
    assert measure.is_in_use() is True

    SecurityMeasureAnswer.objects.filter(security_measure=measure).delete()

    assert measure.is_in_use() is False


@pytest.mark.django_db()
def test_security_objective_is_in_use_through_its_measures(answered):
    security_objective = answered["security_objective"]
    assert security_objective.is_in_use() is True

    SecurityMeasureAnswer.objects.filter(security_measure__security_objective=security_objective).delete()

    assert security_objective.is_in_use() is False


@pytest.mark.django_db()
def test_domain_is_in_use_through_its_objectives(answered):
    domain = answered["domain"]
    assert domain.is_in_use() is True

    SecurityMeasureAnswer.objects.filter(security_measure__security_objective__domain=domain).delete()

    assert domain.is_in_use() is False


def test_maturity_levels_are_never_in_use():
    """Maturity levels are referenced by label, so answers never lock them."""
    assert MaturityLevel().is_in_use() is False


def test_email_templates_are_never_in_use():
    """Email templates stay editable so the wording can be revised."""
    assert SecurityObjectiveEmail().is_in_use() is False


@pytest.mark.django_db()
def test_can_change_or_delete_obj_refuses_a_domain_that_is_in_use(answered, rf):
    """The creator of an answered domain still may not change it."""
    domain = answered["domain"]
    creator_user = User.objects.filter(regulators=domain.creator).first()
    assert creator_user is not None

    request = rf.get("/")
    request.user = creator_user
    request._messages = _CollectingMessages()

    assert can_change_or_delete_obj(request, domain) is False

    SecurityMeasureAnswer.objects.filter(security_measure__security_objective__domain=domain).delete()

    request = rf.get("/")
    request.user = creator_user
    request._messages = _CollectingMessages()

    assert can_change_or_delete_obj(request, domain) is True


@pytest.fixture
def standard_admin(rf):
    """StandardAdmin bound to the custom admin site."""
    from governanceplatform.admin import admin_site
    from securityobjectives.models import Standard

    return admin_site._registry[Standard]


def _request_from(rf, user):
    request = rf.get("/")
    request.user = user
    request._messages = _CollectingMessages()
    return request


@pytest.mark.django_db()
def test_column_configuration_stays_changeable_while_the_standard_is_in_use(answered, standard_admin, rf):
    """The in-use lock must not freeze the declaration table column settings."""
    standard = answered["standard"]
    assert standard.is_in_use() is True
    creator = User.objects.filter(regulators=standard.regulator).first()

    assert standard_admin.has_change_permission(_request_from(rf, creator), standard) is True


@pytest.mark.django_db()
def test_structural_fields_are_frozen_while_the_standard_is_in_use(answered, standard_admin, rf):
    """Keeping the form open must not reopen the fields the lock exists to protect."""
    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()

    readonly = standard_admin.get_readonly_fields(_request_from(rf, creator), standard)

    for field in standard_admin.STRUCTURAL_FIELDS:
        assert field in readonly
    for field in ("maturity_level_label", "evidence_label", "show_maturity_level_column", "show_evidence_column"):
        assert field not in readonly


@pytest.mark.django_db()
def test_structural_fields_are_editable_while_the_standard_is_unused(answered, standard_admin, rf):
    standard = answered["standard"]
    StandardAnswer.objects.filter(standard=standard).delete()
    creator = User.objects.filter(regulators=standard.regulator).first()

    readonly = standard_admin.get_readonly_fields(_request_from(rf, creator), standard)

    for field in standard_admin.STRUCTURAL_FIELDS:
        assert field not in readonly


@pytest.mark.django_db()
def test_deleting_a_standard_in_use_is_still_refused(answered, standard_admin, rf):
    """Only the change rule was relaxed; deletion stays strict."""
    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()

    assert standard_admin.has_delete_permission(_request_from(rf, creator), standard) is False


@pytest.mark.django_db()
def test_a_regulator_who_is_not_the_creator_still_cannot_change_a_standard(answered, standard_admin, rf):
    """Relaxing the in-use half of the rule must leave the ownership half intact."""
    standard = answered["standard"]
    stranger = User.objects.exclude(regulators=standard.regulator).filter(regulators__isnull=False).first()

    assert standard_admin.has_change_permission(_request_from(rf, stranger), standard) is False


@pytest.mark.django_db()
def test_security_objectives_cannot_be_relinked_while_the_standard_is_in_use(answered, standard_admin, rf):
    """The objectives a standard contains stay frozen even though the form is open."""
    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()
    request = _request_from(rf, creator)
    inline = next(
        instance
        for instance in standard_admin.get_inline_instances(request, standard)
        if instance.model.__name__ == "SecurityObjectivesInStandard"
    )

    assert inline.has_add_permission(request, standard) is False
    assert inline.has_change_permission(request, standard) is False
    assert inline.has_delete_permission(request, standard) is False


@pytest.mark.django_db()
def test_lenient_and_strict_checks_do_not_share_a_cached_answer(answered, rf):
    """The per-request cache is keyed on the rule applied, not only the object."""
    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()
    request = _request_from(rf, creator)

    assert can_change_or_delete_obj(request, standard, ignore_in_use=True) is True
    assert can_change_or_delete_obj(request, standard) is False


@pytest.mark.django_db()
def test_column_configuration_is_saved_through_the_admin_while_in_use(answered, otp_client):
    """End to end: the admin form of an in-use standard accepts a column change."""
    from governanceplatform.helpers import user_in_group

    standard = answered["standard"]
    standard.set_current_language("en")
    creator = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))
    client = otp_client(creator)

    response = client.post(
        f"/admin/securityobjectives/standard/{standard.pk}/change/",
        data={
            "label": standard.label,
            "description": standard.description or "",
            "maturity_level_label": "Tier",
            "security_measure_label": "",
            "evidence_label": "Supporting proof",
            "is_implemented_label": "",
            "justification_label": "",
            "review_comment_label": "",
            "show_evidence_column": "on",
            "score_display": "FULL",
            "security_objectives_set-TOTAL_FORMS": "0",
            "security_objectives_set-INITIAL_FORMS": "0",
            "security_objectives_set-MIN_NUM_FORMS": "0",
            "security_objectives_set-MAX_NUM_FORMS": "0",
            "_continue": "Save and continue editing",
        },
        follow=True,
    )

    assert response.status_code == 200
    standard.refresh_from_db()
    standard.set_current_language("en")
    assert standard.maturity_level_label == "Tier"
    assert standard.evidence_label == "Supporting proof"
    # Unchecked checkbox is absent from the payload, so this proves the toggle saved.
    assert standard.show_maturity_level_column is False
    assert standard.show_evidence_column is True


@pytest.mark.django_db()
def test_a_structural_field_posted_to_an_in_use_standard_is_ignored(answered, otp_client):
    """The frozen fields are enforced on save, not merely hidden from the form."""
    from governanceplatform.helpers import user_in_group

    standard = answered["standard"]
    standard.set_current_language("en")
    creator = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))
    other_email = SecurityObjectiveEmail.objects.create()
    other_email.set_current_language("en")
    other_email.name = "Injected email"
    other_email.subject = "Injected"
    other_email.content = "Injected"
    other_email.save()
    client = otp_client(creator)

    client.post(
        f"/admin/securityobjectives/standard/{standard.pk}/change/",
        data={
            "label": standard.label,
            "description": standard.description or "",
            "maturity_level_label": "",
            "security_measure_label": "",
            "evidence_label": "",
            "is_implemented_label": "",
            "justification_label": "",
            "review_comment_label": "",
            "show_maturity_level_column": "on",
            "show_evidence_column": "on",
            "score_display": "FULL",
            "submission_email": str(other_email.pk),
            "security_objectives_set-TOTAL_FORMS": "0",
            "security_objectives_set-INITIAL_FORMS": "0",
            "security_objectives_set-MIN_NUM_FORMS": "0",
            "security_objectives_set-MAX_NUM_FORMS": "0",
            "_continue": "Save and continue editing",
        },
        follow=True,
    )

    standard.refresh_from_db()
    assert standard.submission_email != other_email


@pytest.mark.django_db()
def test_each_label_field_names_the_default_it_falls_back_to(answered, standard_admin, rf):
    """An empty label field must say which column name it will use instead."""
    from securityobjectives.globals import SO_DECLARATION_COLUMNS

    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()

    form = standard_admin.get_form(_request_from(rf, creator), standard)

    for key, column in SO_DECLARATION_COLUMNS.items():
        help_text = str(form.base_fields[f"{key}_label"].help_text)
        assert str(column["label"]) in help_text


@pytest.mark.django_db()
def test_the_default_named_in_the_help_text_follows_the_active_language(answered, standard_admin, rf):
    """The default is a translated string, so the hint must translate with it."""
    from django.utils.translation import override

    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()
    form = standard_admin.get_form(_request_from(rf, creator), standard)
    help_text = form.base_fields["maturity_level_label"].help_text

    with override("en"):
        assert "Maturity Level" in str(help_text)
    with override("fr"):
        assert "Niveau de maturité" in str(help_text)


@pytest.mark.django_db()
def test_each_visibility_toggle_shares_a_row_with_the_column_it_governs(answered, standard_admin, rf):
    """A toggle grouped away from its label leaves the admin guessing which it hides."""
    from securityobjectives.globals import SO_DECLARATION_COLUMNS

    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()

    fieldsets = standard_admin.get_fieldsets(_request_from(rf, creator), standard)
    rows = next(options["fields"] for title, options in fieldsets if "show_evidence_column" in str(options["fields"]))

    flattened = [field for row in rows for field in (row if isinstance(row, tuple) else (row,))]

    for key, column in SO_DECLARATION_COLUMNS.items():
        assert f"{key}_label" in flattened
        if column.get("toggleable"):
            row = next(row for row in rows if isinstance(row, tuple) and f"{key}_label" in row)
            assert f"show_{key}_column" in row


@pytest.mark.django_db()
def test_the_mandatory_flags_are_frozen_once_the_standard_is_in_use(answered, standard_admin, rf):
    """They decide completion, which is stored, so they must not move under a declaration."""
    standard = answered["standard"]
    assert standard.is_in_use() is True
    creator = User.objects.filter(regulators=standard.regulator).first()

    readonly = standard_admin.get_readonly_fields(_request_from(rf, creator), standard)

    assert "justification_mandatory" in readonly
    assert "actions_mandatory" in readonly
    # Hiding them changes what a complete answer is, so they freeze together.
    assert "show_justification_column" in readonly
    assert "show_actions" in readonly


@pytest.mark.django_db()
def test_the_mandatory_flags_are_editable_while_the_standard_is_unused(answered, standard_admin, rf):
    standard = answered["standard"]
    StandardAnswer.objects.filter(standard=standard).delete()
    creator = User.objects.filter(regulators=standard.regulator).first()

    readonly = standard_admin.get_readonly_fields(_request_from(rf, creator), standard)

    assert "justification_mandatory" not in readonly
    assert "actions_mandatory" not in readonly
    assert "show_justification_column" not in readonly
    assert "show_actions" not in readonly


@pytest.mark.django_db()
def test_the_planned_measures_label_stays_editable_while_the_standard_is_in_use(answered, standard_admin, rf):
    """The label is presentation, unlike the obligation beside it."""
    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()

    readonly = standard_admin.get_readonly_fields(_request_from(rf, creator), standard)

    assert "actions_label" not in readonly


def _unused_standard(answered):
    """The fixture's standard, with its declarations removed so its rules are editable."""
    standard = answered["standard"]
    StandardAnswer.objects.filter(standard=standard).delete()
    return standard


@pytest.mark.django_db()
def test_a_hidden_field_cannot_be_marked_mandatory(answered, standard_admin, rf):
    """Otherwise the obligation is a checkbox that quietly does nothing."""
    from securityobjectives.admin import StandardAdminForm

    standard = _unused_standard(answered)
    creator = User.objects.filter(regulators=standard.regulator).first()
    form_class = standard_admin.get_form(_request_from(rf, creator), standard)

    for obligation, visibility in StandardAdminForm.OBLIGATION_NEEDS_VISIBILITY:
        data = {
            "label": standard.label,
            "description": standard.description or "",
            "regulation": standard.regulation_id,
            "score_display": "FULL",
            obligation: "on",
        }
        form = form_class(data=data, instance=standard)

        assert not form.is_valid()
        assert obligation in form.errors


@pytest.mark.django_db()
def test_a_shown_field_may_be_marked_mandatory(answered, standard_admin, rf):
    """The counterpart, so the rule cannot pass by rejecting everything."""
    from securityobjectives.admin import StandardAdminForm

    standard = _unused_standard(answered)
    creator = User.objects.filter(regulators=standard.regulator).first()
    form_class = standard_admin.get_form(_request_from(rf, creator), standard)

    for obligation, visibility in StandardAdminForm.OBLIGATION_NEEDS_VISIBILITY:
        data = {
            "label": standard.label,
            "description": standard.description or "",
            "regulation": standard.regulation_id,
            "score_display": "FULL",
            obligation: "on",
            visibility: "on",
        }
        form = form_class(data=data, instance=standard)
        form.is_valid()

        assert obligation not in form.errors


@pytest.mark.django_db()
def test_the_column_settings_fieldset_carries_its_layout_class(answered, standard_admin, rf):
    """admin.css lines the Show and Mandatory checkboxes up through this class."""
    standard = answered["standard"]
    creator = User.objects.filter(regulators=standard.regulator).first()

    fieldsets = standard_admin.get_fieldsets(_request_from(rf, creator), standard)
    classes = next(options["classes"] for title, options in fieldsets if "actions_label" in str(options["fields"]))

    assert "so-columns" in classes


@pytest.mark.django_db()
def test_the_in_use_notice_is_shown_on_the_change_form(answered, otp_client):
    from governanceplatform.helpers import user_in_group

    standard = answered["standard"]
    creator = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))
    client = otp_client(creator)

    content = client.get(f"/admin/securityobjectives/standard/{standard.pk}/change/").content.decode()

    assert "This standard is in use" in content


@pytest.mark.django_db()
def test_saving_does_not_carry_the_notices_over_to_the_changelist(answered, otp_client):
    """They are queued per request, so one added on a save surfaces after the redirect."""
    from governanceplatform.helpers import user_in_group

    standard = answered["standard"]
    standard.set_current_language("en")
    creator = next(user for user in User.objects.filter(regulators=standard.regulator) if user_in_group(user, "RegulatorAdmin"))
    client = otp_client(creator)

    response = client.post(
        f"/admin/securityobjectives/standard/{standard.pk}/change/",
        data={
            "label": standard.label,
            "description": standard.description or "",
            "maturity_level_label": "",
            "security_measure_label": "",
            "evidence_label": "",
            "is_implemented_label": "",
            "justification_label": "",
            "review_comment_label": "",
            "actions_label": "",
            "show_maturity_level_column": "on",
            "show_evidence_column": "on",
            "show_review_comment_column": "on",
            "score_display": "FULL",
            "security_objectives_set-TOTAL_FORMS": "0",
            "security_objectives_set-INITIAL_FORMS": "0",
            "security_objectives_set-MIN_NUM_FORMS": "0",
            "security_objectives_set-MAX_NUM_FORMS": "0",
        },
        follow=True,
    )

    content = response.content.decode()

    assert "was changed successfully" in content
    assert "This standard is in use" not in content
    assert "Save your changes before you leave the tab" not in content
