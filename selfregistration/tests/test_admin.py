import pytest
from django.urls import reverse
from django.utils import timezone

from governanceplatform.admin import admin_site
from governanceplatform.context_processors import user_modules
from governanceplatform.models import Functionality, Regulation, Regulator, RegulatorUser, User
from selfregistration.models import (
    PageInTemplate,
    ProcedureTemplate,
    ProcedureTemplateChoice,
    ProcedureTemplateConditionalQuestion,
    ProcedureTemplatePage,
    ProcedureTemplateQuestion,
    ProcedureTemplateQuestionGroup,
    ProcedureTemplateQuestionPlacement,
)


@pytest.mark.django_db
def test_template_admin_only_lists_templates_for_administered_regulators(rf):
    user = User.objects.create(email="regulator@example.test", is_staff=True)
    own_regulator = Regulator.objects.create()
    other_regulator = Regulator.objects.create()
    RegulatorUser.objects.create(user=user, regulator=other_regulator, is_regulator_administrator=False)
    RegulatorUser.objects.create(user=user, regulator=own_regulator, is_regulator_administrator=True)
    functionality = Functionality.objects.create(type="selfregistration", name="Self-registration")
    functionality.roles.set(user.groups.all())
    own_regulator.functionalities.add(functionality)
    other_regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create()
    own_template = ProcedureTemplate.objects.create(regulator=own_regulator, regulation=regulation)
    other_template = ProcedureTemplate.objects.create(regulator=other_regulator, regulation=regulation)

    model_admin = admin_site.get_model_admin(ProcedureTemplate)
    request = rf.get(reverse("admin:selfregistration_proceduretemplate_changelist"))
    request.user = user

    assert list(model_admin.get_queryset(request)) == [own_template]
    assert model_admin.get_object(request, str(other_template.pk)) is None


@pytest.fixture
def sr_regulator_admin(db):
    user = User.objects.create(
        email="sr-admin@example.test", is_staff=True, email_verified=True, accepted_terms=True, accepted_terms_date=timezone.now()
    )
    regulator = Regulator.objects.create()
    RegulatorUser.objects.create(user=user, regulator=regulator, is_regulator_administrator=True)
    functionality = Functionality.objects.create(type="selfregistration", name="Self-registration")
    return user, regulator, functionality


@pytest.mark.parametrize(("role_enabled", "regulator_enabled"), [(False, False), (False, True), (True, False), (True, True)])
def test_sr_entry_points_require_role_and_regulator(sr_regulator_admin, otp_client, rf, role_enabled, regulator_enabled):
    user, regulator, functionality = sr_regulator_admin
    if role_enabled:
        functionality.roles.set(user.groups.all())
    if regulator_enabled:
        regulator.functionalities.add(functionality)
    client = otp_client(user)
    module_url = reverse("selfregistration")
    admin_url = reverse("admin:app_list", args=["selfregistration"])
    request = rf.get("/")
    request.user = user

    enabled = role_enabled and regulator_enabled
    assert ("selfregistration" in {module["type"] for module in user_modules(request)["user_modules"]}) == enabled
    assert client.get(module_url).status_code == (302 if enabled else 404)
    assert client.get(admin_url).status_code == (200 if enabled else 404)


def test_regulator_admin_can_create_template_only_for_assigned_regulation(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    regulation.regulators.add(regulator)
    unassigned = Regulation.objects.create(label="Unassigned")
    url = reverse("admin:selfregistration_proceduretemplate_add") + "?language=en"
    client = otp_client(user)

    data = {"regulator": regulator.pk, "name": "Template", "delay": 7, "en": "", "_save": "Save"}
    assert client.post(url, {**data, "regulation": unassigned.pk}).status_code == 200
    assert not ProcedureTemplate.objects.exists()
    assert client.post(url, {**data, "regulation": regulation.pk}).status_code == 302
    procedure = ProcedureTemplate.objects.get(regulator=regulator, regulation=regulation)
    assert procedure.delay == 7 and procedure.periodic_update is None


def test_regulator_admin_can_edit_draft_but_not_published_version(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    draft = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Draft")
    published = ProcedureTemplate.objects.create(
        regulator=regulator, regulation=regulation, name="Published", state=ProcedureTemplate.State.PUBLISHED
    )
    client = otp_client(user)
    url = "admin:selfregistration_proceduretemplate_change"
    data = {
        "delay": 0,
        "name": "Updated draft",
        "state": "published",
        "regulator": Regulator.objects.create().pk,
        "regulation": Regulation.objects.create().pk,
        "pages-TOTAL_FORMS": 0,
        "pages-INITIAL_FORMS": 0,
        "_save": "Save",
    }

    assert client.post(reverse(url, args=[draft.pk]) + "?language=en", data).status_code == 302
    draft.refresh_from_db()
    assert draft.name == "Updated draft"
    assert draft.state == ProcedureTemplate.State.DRAFT
    assert (draft.regulator_id, draft.regulation_id) == (regulator.pk, regulation.pk)
    assert client.post(reverse(url, args=[published.pk]) + "?language=en", data).status_code == 403


def test_sr_publish_and_archive_actions_track_dated_editions(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    first = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="First")
    second = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Second")
    creation_date = first.creation_date
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplate_changelist")

    def run(action, template):
        assert client.post(url, {"action": action, "_selected_action": [template.pk], "index": "0"}).status_code == 302
        template.refresh_from_db()

    run("archive_procedure", first)
    assert first.state == ProcedureTemplate.State.DRAFT
    run("publish_procedure", first)
    assert first.state == ProcedureTemplate.State.PUBLISHED
    assert first.creation_date == creation_date < first.published_at == first.last_update
    run("publish_procedure", second)
    assert second.state == ProcedureTemplate.State.DRAFT
    run("archive_procedure", first)
    assert first.state == ProcedureTemplate.State.ARCHIVED
    assert first.creation_date == creation_date < first.published_at < first.last_update
    run("publish_procedure", second)
    assert second.state == ProcedureTemplate.State.PUBLISHED


def test_sr_question_add_form_saves_its_answer_choices(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplatequestion_add") + "?language=en"
    data = {
        "owner": regulator.pk,
        "question_type": ProcedureTemplateQuestion.Kind.SINGLE_CHOICE,
        "label": "Send copies?",
        "en": "",
        "choices-TOTAL_FORMS": 1,
        "choices-INITIAL_FORMS": 0,
        "choices-0-position": 1,
        "choices-0-label": "Yes",
    }

    assert "choices-__prefix__-label" in client.get(url).content.decode()
    response = client.post(url, data)
    assert response.status_code == 302, response.context["errors"] if response.status_code == 200 else response.status_code
    question = ProcedureTemplateQuestion.objects.get(owner=regulator)
    answer = question.choices.get()
    assert str(answer) == "Yes"
    assert answer.position == 1


@pytest.mark.parametrize("owned", [True, False])
def test_sr_regulators_can_copy_questions_and_translated_choices_as_new(sr_regulator_admin, otp_client, owned):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    source_owner = regulator if owned else Regulator.objects.create()
    source = ProcedureTemplateQuestion.objects.create(owner=source_owner, question_type=ProcedureTemplateQuestion.Kind.SINGLE_CHOICE)
    source.create_translation("en", label="Send copies?", help_text="Delivery preferences")
    source.create_translation("fr", label="Envoyer des copies ?", help_text="Préférences d’envoi")
    answer = source.choices.create(position=1)
    answer.create_translation("en", label="Yes")
    answer.create_translation("fr", label="Oui")
    client = otp_client(user)
    detail = reverse("admin:selfregistration_proceduretemplatequestion_change", args=[source.pk]) + "?language=en"
    copy_url = reverse("admin:selfregistration_proceduretemplatequestion_copy", args=[source.pk])

    page = client.get(detail)
    assert page.status_code == 200
    assert "Save as new" in page.content.decode()
    assert copy_url in page.content.decode()
    if not owned:
        assert client.post(detail, {"label": "Changed", "choices-0-label": "Changed"}).status_code == 403
    assert client.get(copy_url).status_code == 405
    assert client.post(copy_url, {"copy_owner": Regulator.objects.create().pk}).status_code == 404
    assert client.post(copy_url, {"copy_owner": regulator.pk}).status_code == 302
    copied = ProcedureTemplateQuestion.objects.exclude(pk=source.pk).get()
    assert copied.owner_id == regulator.pk and copied.reference != source.reference
    assert dict(copied.translations.values_list("language_code", "label")) == {"en": "Send copies?", "fr": "Envoyer des copies ?"}
    new_answer = copied.choices.get()
    assert new_answer.reference != answer.reference and new_answer.position == answer.position
    assert dict(new_answer.translations.values_list("language_code", "label")) == {"en": "Yes", "fr": "Oui"}


def test_admin_displays_translated_labels_for_related_records(sr_regulator_admin, otp_client, settings):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    regulation.regulators.add(regulator)
    template_version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Company details")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Company address")
    page = PageInTemplate.objects.create(template_version=template_version, position=1, category=category)
    question = ProcedureTemplateQuestion.objects.create(
        owner=regulator, question_type=ProcedureTemplateQuestion.Kind.SINGLE_CHOICE, label="Is the company registered?"
    )
    choice = ProcedureTemplateChoice.objects.create(question=question, position=1, label="Company is registered")
    for obj, field, label in (
        (regulator, "name", "Autorité de régulation"),
        (regulation, "label", "Réglementation des services"),
        (template_version, "name", "Fiche de la société"),
        (category, "title", "Adresse de la société"),
        (question, "label", "La société est-elle enregistrée ?"),
        (choice, "label", "La société est enregistrée"),
    ):
        obj.set_current_language("fr")
        setattr(obj, field, label)
        obj.save()
    ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    client = otp_client(user)
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"

    for action in ("add", "changelist"):
        response = client.get(reverse(f"admin:selfregistration_proceduretemplate_{action}"))
        assert response.status_code == 200
        assert "Autorité de régulation" in response.content.decode()
        assert "Réglementation des services" in response.content.decode()

    placement_form = client.get(reverse("admin:selfregistration_proceduretemplate_change", args=[template_version.pk]))
    assert "Adresse de la société" in placement_form.content.decode()
    assert "La société est-elle enregistrée ?" in placement_form.content.decode()
    question_form = client.get(reverse("admin:selfregistration_proceduretemplatequestion_change", args=[question.pk]) + "?language=fr")
    assert "La société est enregistrée" in question_form.content.decode()


def test_sr_questionnaire_reuses_category_and_saves_questions_on_version(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    first_version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Previous")
    draft = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact details")
    first_page = PageInTemplate.objects.create(template_version=first_version, category=category, position=1)
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplate_change", args=[draft.pk]) + "?language=en"

    page_data = {
        "delay": 0,
        "name": "Draft",
        "pages-TOTAL_FORMS": 1,
        "pages-INITIAL_FORMS": 0,
        "pages-0-position": 3,
        "pages-0-category": category.pk,
        "_continue": "Save",
    }
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    foreign_owner = Regulator.objects.create()
    foreign_question = ProcedureTemplateQuestion.objects.create(owner=foreign_owner, label="Foreign question")
    prefix = "pages-0-placements"
    question_data = {
        **page_data,
        f"{prefix}-TOTAL_FORMS": 1,
        f"{prefix}-INITIAL_FORMS": 0,
        f"{prefix}-0-position": 1,
        f"{prefix}-0-question": foreign_question.pk,
        f"{prefix}-0-mandatory": "on",
    }
    version_form = client.get(url)
    assert version_form.status_code == 200
    assert "pages-__prefix__-placements-TOTAL_FORMS" in version_form.content.decode()
    assert client.post(url, question_data).status_code == 200
    assert not draft.pages.exists()

    question_data[f"{prefix}-0-question"] = question.pk
    response = client.post(url, question_data)
    assert response.status_code == 302, response.context["errors"] if response.status_code == 200 else response.status_code
    page = draft.pages.get()
    assert (page.category_id, page.position) == (category.pk, 3)
    assert page.placements.get().question_id == question.pk
    first_page.refresh_from_db()
    assert first_page.position == 1
    assert not first_page.placements.exists()


def test_sr_questionnaire_interleaves_questions_and_groups_by_position(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    draft = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact details")
    page = PageInTemplate.objects.create(template_version=draft, category=category, position=1)
    email = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    phone = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Phone")
    group = ProcedureTemplateQuestionGroup.objects.create(owner=regulator, title="Contacts")
    first = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=email, position=1)
    second = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=phone, position=2)
    prefix = "pages-0-placements"
    data = {
        "delay": 0,
        "name": "Draft",
        "pages-TOTAL_FORMS": 1,
        "pages-INITIAL_FORMS": 1,
        "pages-0-id": page.pk,
        "pages-0-position": 1,
        "pages-0-category": category.pk,
        f"{prefix}-TOTAL_FORMS": 3,
        f"{prefix}-INITIAL_FORMS": 2,
        f"{prefix}-0-id": first.pk,
        f"{prefix}-0-position": 3,
        f"{prefix}-0-question": email.pk,
        f"{prefix}-1-id": second.pk,
        f"{prefix}-1-position": 1,
        f"{prefix}-1-question": phone.pk,
        f"{prefix}-2-position": 2,
        f"{prefix}-2-question_group": group.pk,
    }
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplate_change", args=[draft.pk]) + "?language=en"

    response = client.post(url, data)
    assert response.status_code == 302, response.context["errors"] if response.status_code == 200 else response.status_code
    assert list(page.placements.values_list("question_id", "question_group_id", "position")) == [
        (phone.pk, None, 1),
        (None, group.pk, 2),
        (email.pk, None, 3),
    ]


def test_sr_group_cannot_be_placed_on_two_new_pages_in_one_save(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    draft = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact details")
    group = ProcedureTemplateQuestionGroup.objects.create(owner=regulator, title="Contacts")
    data = {"delay": 0, "name": "Draft", "pages-TOTAL_FORMS": 2, "pages-INITIAL_FORMS": 0}
    for index in range(2):
        page_prefix = f"pages-{index}"
        items_prefix = f"{page_prefix}-placements"
        data.update(
            {
                f"{page_prefix}-position": index + 1,
                f"{page_prefix}-category": category.pk,
                f"{items_prefix}-TOTAL_FORMS": 1,
                f"{items_prefix}-INITIAL_FORMS": 0,
                f"{items_prefix}-0-position": 1,
                f"{items_prefix}-0-question_group": group.pk,
            }
        )
    url = reverse("admin:selfregistration_proceduretemplate_change", args=[draft.pk]) + "?language=en"

    response = otp_client(user).post(url, data)
    assert response.status_code == 200
    assert "This group already appears on another row of this version" in response.content.decode()
    assert not draft.pages.exists()


def test_sr_group_admin_saves_ordered_questions_for_its_regulator(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    group = ProcedureTemplateQuestionGroup.objects.create(owner=regulator, title="Contacts")
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    other_regulator = Regulator.objects.create()
    foreign_question = ProcedureTemplateQuestion.objects.create(owner=other_regulator, label="Foreign question")
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplatequestiongroup_change", args=[group.pk]) + "?language=en"
    data = {
        "title": "Contacts",
        "min_occurrences": 1,
        "max_occurrences": 5,
        "questions-TOTAL_FORMS": 1,
        "questions-INITIAL_FORMS": 0,
        "questions-0-position": 1,
        "questions-0-question": foreign_question.pk,
        "questions-0-mandatory": "on",
        "_continue": "Save",
    }

    assert client.post(url, data).status_code == 200
    assert not group.questions.exists()

    data["questions-0-question"] = question.pk
    response = client.post(url, data)
    assert response.status_code == 302, response.context["errors"] if response.status_code == 200 else response.status_code
    assert list(group.questions.values_list("question_id", "position", "mandatory")) == [(question.pk, 1, True)]


def test_sr_admin_saves_a_rule_for_a_group_on_the_trigger_page(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact details")
    page = version.pages.create(category=category, position=1)
    other_page = version.pages.create(category=category, position=2)
    empty_version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Unconditional draft")
    empty_version.pages.create(category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, question_type=ProcedureTemplateQuestion.Kind.MULTIPLE_CHOICE)
    trigger = page.placements.create(question=question, position=1)
    choice = question.choices.create(label="Yes", position=1)
    group = ProcedureTemplateQuestionGroup.objects.create(owner=regulator, title="Contacts")
    target = page.placements.create(question_group=group, position=2, is_conditional=True)
    other_target = other_page.placements.create(question=question, position=1, is_conditional=True)
    client = otp_client(user)

    version_url = reverse("admin:selfregistration_proceduretemplate_change", args=[version.pk])
    add_url = reverse("admin:selfregistration_proceduretemplateconditionalquestion_add", query={"template_version": version.pk})
    assert add_url in client.get(version_url).content.decode()
    response = client.get(add_url)
    assert response.status_code == 200
    fields = response.context["adminform"].form.fields
    assert list(fields) == ["template_version", "target", "trigger_question", "trigger_choice"]
    assert list(fields["template_version"].queryset) == [version]
    assert set(fields["target"].queryset) == {target, other_target}
    assert not fields["trigger_question"].queryset.exists()

    options_url = reverse("admin:selfregistration_conditional_options")
    path = {"template_version": version.pk, "target": target.pk}
    triggers = client.get(options_url, {**path, "field": "trigger_question"}).json()["options"]
    assert [option["id"] for option in triggers] == [trigger.pk]
    answers = client.get(options_url, {**path, "trigger_question": trigger.pk, "field": "trigger_choice"}).json()["options"]
    assert answers == [{"id": choice.pk, "label": "Yes"}]

    data = {"template_version": version.pk, "trigger_question": trigger.pk, "trigger_choice": choice.pk, "target": other_target.pk}
    response = client.post(add_url, data)
    assert response.status_code == 200
    assert "same page as the conditional item" in response.content.decode()
    assert not ProcedureTemplateConditionalQuestion.objects.exists()

    response = client.post(add_url, {**data, "target": target.pk})
    assert response.status_code == 302, response.context["errors"] if response.status_code == 200 else response.status_code
    assert version.conditional_questions.get().target == target


@pytest.mark.parametrize("state", [ProcedureTemplate.State.DRAFT, ProcedureTemplate.State.PUBLISHED])
def test_sr_admin_can_delete_draft_conditional_rules_from_the_list(sr_regulator_admin, otp_client, state):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    version = ProcedureTemplate.objects.create(regulator=regulator, regulation=Regulation.objects.create(label="Assigned"), state=state)
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contacts")
    page = version.pages.create(category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, question_type=ProcedureTemplateQuestion.Kind.SINGLE_CHOICE)
    choice = question.choices.create(label="Yes", position=1)
    trigger = page.placements.create(question=question, position=1)
    target = page.placements.create(question=ProcedureTemplateQuestion.objects.create(owner=regulator), position=2, is_conditional=True)
    rule = version.conditional_questions.create(trigger_question=trigger, trigger_choice=choice, target=target)
    client = otp_client(user)
    list_url = reverse("admin:selfregistration_proceduretemplateconditionalquestion_changelist")
    delete_url = reverse("admin:selfregistration_proceduretemplateconditionalquestion_delete", args=[rule.pk])
    editable = state == ProcedureTemplate.State.DRAFT

    changelist = client.get(list_url).content.decode()
    assert (f'class="admin-button admin-button--danger" href="{delete_url}"' in changelist) == editable
    assert ('aria-hidden="true">delete</span>Delete rule' in changelist) == editable
    assert client.get(delete_url).status_code == (200 if editable else 403)
    assert version.conditional_questions.exists()
    assert client.post(delete_url, {"post": "yes"}).status_code == (302 if editable else 403)
    assert version.conditional_questions.exists() == (not editable)
    assert page.placements.filter(pk=target.pk, is_conditional=True).exists()
    assert page.placements.filter(pk=trigger.pk, question__choices=choice).exists()


@pytest.mark.parametrize(
    "model",
    [
        ProcedureTemplate,
        ProcedureTemplatePage,
        ProcedureTemplateQuestion,
        ProcedureTemplateQuestionGroup,
        ProcedureTemplateConditionalQuestion,
    ],
)
def test_sr_lists_enable_selection_and_the_standard_bulk_action(sr_regulator_admin, otp_client, model):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    url = reverse(f"admin:selfregistration_{model._meta.model_name}_changelist")

    response = otp_client(user).get(url)

    assert response.status_code == 200
    assert "action_checkbox" in response.context["cl"].list_display
    assert "delete_selected" in dict(response.context["action_form"].fields["action"].choices)


def test_sr_bulk_delete_checks_each_conditional_rule_before_deleting(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contacts")
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, question_type=ProcedureTemplateQuestion.Kind.SINGLE_CHOICE)
    choice = question.choices.create(label="Yes", position=1)
    rule_ids = []
    for state in (ProcedureTemplate.State.DRAFT, ProcedureTemplate.State.DRAFT, ProcedureTemplate.State.PUBLISHED):
        version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, state=state)
        page = version.pages.create(category=category, position=1)
        trigger = page.placements.create(question=question, position=1)
        target = page.placements.create(question=question, position=2, is_conditional=True)
        rule = version.conditional_questions.create(trigger_question=trigger, trigger_choice=choice, target=target)
        rule_ids.append(rule.pk)

    *drafts, published = rule_ids
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplateconditionalquestion_changelist")
    action = {"action": "delete_selected", "_selected_action": drafts}
    response = client.post(url, {**action, "_selected_action": [*drafts, published], "post": "yes"})
    assert response.status_code == 403
    assert ProcedureTemplateConditionalQuestion.objects.count() == 3

    assert client.post(url, {**action, "index": "0"}).status_code == 200
    assert ProcedureTemplateConditionalQuestion.objects.count() == 3
    assert client.post(url, {**action, "post": "yes"}).status_code == 302
    assert list(ProcedureTemplateConditionalQuestion.objects.values_list("pk", flat=True)) == [published]


@pytest.mark.parametrize("state", [ProcedureTemplate.State.DRAFT, ProcedureTemplate.State.PUBLISHED])
def test_sr_can_remove_an_assigned_page_only_from_a_draft(sr_regulator_admin, otp_client, state):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Questionnaire", state=state)
    other_version = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation, name="Other")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact")
    page = PageInTemplate.objects.create(template_version=version, category=category, position=1)
    other_page = PageInTemplate.objects.create(template_version=other_version, category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    placement = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    other_placement = ProcedureTemplateQuestionPlacement.objects.create(page=other_page, question=question, position=1)
    prefix = "pages-0-placements"
    data = {
        "delay": 0,
        "name": "Questionnaire",
        "pages-TOTAL_FORMS": 1,
        "pages-INITIAL_FORMS": 1,
        "pages-0-id": page.pk,
        "pages-0-position": 1,
        "pages-0-category": category.pk,
        "pages-0-DELETE": "on",
        f"{prefix}-TOTAL_FORMS": 1,
        f"{prefix}-INITIAL_FORMS": 1,
        f"{prefix}-0-id": placement.pk,
        f"{prefix}-0-position": 2,
        f"{prefix}-0-question": question.pk,
    }
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplate_change", args=[version.pk]) + "?language=en"

    draft = state == ProcedureTemplate.State.DRAFT
    assert ("pages-0-DELETE" in client.get(url).content.decode()) == draft
    response = client.post(url, data)

    assert response.status_code == (302 if draft else 403)
    assert PageInTemplate.objects.filter(pk=page.pk).exists() is not draft
    assert ProcedureTemplateQuestionPlacement.objects.filter(pk=placement.pk).exists() is not draft
    assert ProcedureTemplatePage.objects.filter(pk=category.pk).exists()
    assert ProcedureTemplateQuestion.objects.filter(pk=question.pk).exists()
    assert ProcedureTemplateQuestionPlacement.objects.filter(pk=other_placement.pk, page=other_page).exists()


def test_sr_regulator_admin_removes_question_order_from_template_version(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    version = ProcedureTemplate.objects.create(regulator=regulator, regulation=Regulation.objects.create(label="Assigned"), name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact")
    page = PageInTemplate.objects.create(template_version=version, category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    placement = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    prefix = "pages-0-placements"
    data = {
        "delay": 0,
        "name": "Draft",
        "pages-TOTAL_FORMS": 1,
        "pages-INITIAL_FORMS": 1,
        "pages-0-id": page.pk,
        "pages-0-position": 1,
        "pages-0-category": category.pk,
        f"{prefix}-TOTAL_FORMS": 1,
        f"{prefix}-INITIAL_FORMS": 1,
        f"{prefix}-0-id": placement.pk,
        f"{prefix}-0-position": 1,
        f"{prefix}-0-question": question.pk,
        f"{prefix}-0-DELETE": "on",
    }
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplate_change", args=[version.pk]) + "?language=en"

    assert f"{prefix}-0-DELETE" in client.get(url).content.decode()
    assert client.post(url, data).status_code == 302
    assert not page.placements.exists()
    assert PageInTemplate.objects.filter(pk=page.pk).exists()
    assert ProcedureTemplateQuestion.objects.filter(pk=question.pk).exists()


@pytest.mark.parametrize(
    ("target", "removed"),
    [
        ("version", {"version", "page", "placement"}),
        ("category", {"category", "page", "placement"}),
        ("question", {"question", "choice", "placement"}),
    ],
)
def test_sr_regulator_admin_can_delete_configuration_with_its_dependencies(sr_regulator_admin, otp_client, target, removed):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    version = ProcedureTemplate.objects.create(
        regulator=regulator,
        regulation=Regulation.objects.create(label="Assigned"),
        name="Published",
        state=ProcedureTemplate.State.PUBLISHED,
    )
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact")
    page = PageInTemplate.objects.create(template_version=version, category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Send copies?")
    choice = ProcedureTemplateChoice.objects.create(question=question, position=1, label="Yes")
    placement = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    records = {
        "version": version,
        "category": category,
        "page": page,
        "question": question,
        "choice": choice,
        "placement": placement,
    }
    obj = records[target]
    client = otp_client(user)
    url = reverse(f"admin:selfregistration_{obj._meta.model_name}_delete", args=[obj.pk])

    assert client.post(url, {"post": "yes"}).status_code == 302
    assert {key for key, record in records.items() if not type(record).objects.filter(pk=record.pk).exists()} == removed


def test_sr_inline_models_are_not_available_as_standalone_admin_pages(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    client = otp_client(user)

    response = client.get(reverse("admin:app_list", args=["selfregistration"]))
    assert response.status_code == 200
    for model in (PageInTemplate, ProcedureTemplateQuestionPlacement, ProcedureTemplateChoice):
        assert not admin_site.is_registered(model)
        assert client.get(f"/admin/selfregistration/{model._meta.model_name}/").status_code == 404
