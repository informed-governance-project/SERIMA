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
    ProcedureTemplatePage,
    ProcedureTemplateQuestion,
    ProcedureTemplateQuestionPlacement,
    ProcedureTemplateVersion,
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
    url = reverse("admin:selfregistration_proceduretemplate_add")
    client = otp_client(user)

    assert client.post(url, {"regulator": regulator.pk, "regulation": unassigned.pk}).status_code == 200
    assert not ProcedureTemplate.objects.exists()
    assert client.post(url, {"regulator": regulator.pk, "regulation": regulation.pk, "_save": "Save"}).status_code == 302
    assert ProcedureTemplate.objects.filter(regulator=regulator, regulation=regulation).exists()


def test_regulator_admin_can_edit_draft_but_not_published_version(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation)
    draft = ProcedureTemplateVersion.objects.create(template=template, version_number=1, name="Draft")
    published = ProcedureTemplateVersion.objects.create(
        template=template, version_number=2, name="Published", state=ProcedureTemplateVersion.State.PUBLISHED
    )
    client = otp_client(user)
    url = "admin:selfregistration_proceduretemplateversion_change"
    data = {
        "version_number": 1,
        "name": "Updated draft",
        "state": "published",
        "pages-TOTAL_FORMS": 0,
        "pages-INITIAL_FORMS": 0,
        "_save": "Save",
    }

    assert client.post(reverse(url, args=[draft.pk]) + "?language=en", data).status_code == 302
    draft.refresh_from_db()
    assert draft.name == "Updated draft"
    assert draft.state == ProcedureTemplateVersion.State.DRAFT
    assert client.post(reverse(url, args=[published.pk]) + "?language=en", data).status_code == 403


def test_admin_displays_translated_labels_for_related_records(sr_regulator_admin, otp_client, settings):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation)
    template_version = ProcedureTemplateVersion.objects.create(template=template, version_number=1, name="Company details")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Company address")
    page = PageInTemplate.objects.create(template_version=template_version, position=1, category=category)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Is the company registered?")
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

    template_label = "Autorité de régulation - Réglementation des services"
    for action in ("add", "changelist"):
        response = client.get(reverse(f"admin:selfregistration_proceduretemplateversion_{action}"))
        assert response.status_code == 200
        assert template_label in response.content.decode()

    placement_form = client.get(reverse("admin:selfregistration_proceduretemplateversion_change", args=[template_version.pk]))
    assert "Adresse de la société" in placement_form.content.decode()
    assert "La société est-elle enregistrée ?" in placement_form.content.decode()
    choice_list = client.get(reverse("admin:selfregistration_proceduretemplatechoice_changelist"))
    assert "La société est enregistrée" in choice_list.content.decode()


def test_sr_questionnaire_reuses_category_and_saves_questions_on_version(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation)
    first_version = ProcedureTemplateVersion.objects.create(template=template, version_number=1, name="Previous")
    draft = ProcedureTemplateVersion.objects.create(template=template, version_number=2, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact details")
    first_page = PageInTemplate.objects.create(template_version=first_version, category=category, position=1)
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplateversion_change", args=[draft.pk]) + "?language=en"

    page_data = {
        "version_number": 2,
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


def test_sr_questionnaire_can_swap_question_positions(sr_regulator_admin, otp_client):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation)
    draft = ProcedureTemplateVersion.objects.create(template=template, version_number=1, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact details")
    page = PageInTemplate.objects.create(template_version=draft, category=category, position=1)
    email = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    phone = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Phone")
    first = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=email, position=1)
    second = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=phone, position=2)
    prefix = "pages-0-placements"
    data = {
        "version_number": 1,
        "name": "Draft",
        "pages-TOTAL_FORMS": 1,
        "pages-INITIAL_FORMS": 1,
        "pages-0-id": page.pk,
        "pages-0-position": 1,
        "pages-0-category": category.pk,
        f"{prefix}-TOTAL_FORMS": 2,
        f"{prefix}-INITIAL_FORMS": 2,
        f"{prefix}-0-id": first.pk,
        f"{prefix}-0-position": 2,
        f"{prefix}-0-question": email.pk,
        f"{prefix}-1-id": second.pk,
        f"{prefix}-1-position": 1,
        f"{prefix}-1-question": phone.pk,
    }
    client = otp_client(user)
    url = reverse("admin:selfregistration_proceduretemplateversion_change", args=[draft.pk]) + "?language=en"

    response = client.post(url, data)
    assert response.status_code == 302, response.context["errors"] if response.status_code == 200 else response.status_code
    assert list(page.placements.values_list("question_id", "position")) == [(phone.pk, 1), (email.pk, 2)]


@pytest.mark.parametrize("state", [ProcedureTemplateVersion.State.DRAFT, ProcedureTemplateVersion.State.PUBLISHED])
def test_sr_can_remove_an_assigned_page_only_from_a_draft(sr_regulator_admin, otp_client, state):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    regulation = Regulation.objects.create(label="Assigned")
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=regulation)
    version = ProcedureTemplateVersion.objects.create(template=template, version_number=1, name="Questionnaire", state=state)
    other_version = ProcedureTemplateVersion.objects.create(template=template, version_number=2, name="Other")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact")
    page = PageInTemplate.objects.create(template_version=version, category=category, position=1)
    other_page = PageInTemplate.objects.create(template_version=other_version, category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    placement = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    other_placement = ProcedureTemplateQuestionPlacement.objects.create(page=other_page, question=question, position=1)
    prefix = "pages-0-placements"
    data = {
        "version_number": 1,
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
    url = reverse("admin:selfregistration_proceduretemplateversion_change", args=[version.pk]) + "?language=en"

    draft = state == ProcedureTemplateVersion.State.DRAFT
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
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=Regulation.objects.create(label="Assigned"))
    version = ProcedureTemplateVersion.objects.create(template=template, version_number=1, name="Draft")
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact")
    page = PageInTemplate.objects.create(template_version=version, category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Email")
    placement = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    prefix = "pages-0-placements"
    data = {
        "version_number": 1,
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
    url = reverse("admin:selfregistration_proceduretemplateversion_change", args=[version.pk]) + "?language=en"

    assert f"{prefix}-0-DELETE" in client.get(url).content.decode()
    assert client.post(url, data).status_code == 302
    assert not page.placements.exists()
    assert PageInTemplate.objects.filter(pk=page.pk).exists()
    assert ProcedureTemplateQuestion.objects.filter(pk=question.pk).exists()


@pytest.mark.parametrize(
    ("target", "removed"),
    [
        ("template", {"template", "version", "page", "placement"}),
        ("version", {"version", "page", "placement"}),
        ("category", {"category", "page", "placement"}),
        ("question", {"question", "choice", "placement"}),
        ("choice", {"choice"}),
    ],
)
def test_sr_regulator_admin_can_delete_configuration_with_its_dependencies(sr_regulator_admin, otp_client, target, removed):
    user, regulator, functionality = sr_regulator_admin
    functionality.roles.set(user.groups.all())
    regulator.functionalities.add(functionality)
    template = ProcedureTemplate.objects.create(regulator=regulator, regulation=Regulation.objects.create(label="Assigned"))
    version = ProcedureTemplateVersion.objects.create(
        template=template, version_number=1, name="Published", state=ProcedureTemplateVersion.State.PUBLISHED
    )
    category = ProcedureTemplatePage.objects.create(owner=regulator, title="Contact")
    page = PageInTemplate.objects.create(template_version=version, category=category, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, label="Send copies?")
    choice = ProcedureTemplateChoice.objects.create(question=question, position=1, label="Yes")
    placement = ProcedureTemplateQuestionPlacement.objects.create(page=page, question=question, position=1)
    records = {
        "template": template,
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
    for model in (PageInTemplate, ProcedureTemplateQuestionPlacement):
        assert not admin_site.is_registered(model)
        assert client.get(f"/admin/selfregistration/{model._meta.model_name}/").status_code == 404
