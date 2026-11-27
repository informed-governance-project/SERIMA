import pytest
from django.core.exceptions import ValidationError

from governanceplatform.models import Regulation, Regulator
from selfregistration.models import (
    ProcedureTemplate,
    ProcedureTemplateChoice,
    ProcedureTemplatePage,
    ProcedureTemplateQuestion,
    ProcedureTemplateQuestionGroup,
)


@pytest.mark.parametrize(
    ("model", "field", "fields", "expected"),
    [
        (ProcedureTemplate, "name", {}, "Company details"),
        (ProcedureTemplatePage, "title", {}, "Company details"),
        (ProcedureTemplateQuestion, "label", {}, "Company details"),
        (ProcedureTemplateChoice, "label", {"position": 1}, "Company details"),
    ],
)
def test_translatable_procedure_models_use_a_label_instead_of_the_default_object_name(model, field, fields, expected):
    obj = model(**fields)
    obj.set_current_language("en")
    setattr(obj, field, "Company details")

    assert str(obj) == expected


@pytest.mark.django_db
def test_group_trigger_reveals_a_question_in_its_own_occurrence():
    regulator = Regulator.objects.create()
    version = ProcedureTemplate.objects.create(regulator=regulator, regulation=Regulation.objects.create())
    page = version.pages.create(category=ProcedureTemplatePage.objects.create(owner=regulator), position=1)
    group = ProcedureTemplateQuestionGroup.objects.create(owner=regulator)
    group_placement = page.placements.create(question_group=group, position=1)
    question = ProcedureTemplateQuestion.objects.create(owner=regulator, question_type=ProcedureTemplateQuestion.Kind.SINGLE_WITH_COMMENT)
    choice = question.choices.create(position=1)
    trigger = group.questions.create(question=question, position=1)
    detail = ProcedureTemplateQuestion.objects.create(owner=regulator)
    outside = page.placements.create(question=detail, position=2, is_conditional=True)
    target = group.questions.create(question=detail, position=2, is_conditional=True)

    with pytest.raises(ValidationError, match="that same group"):
        version.conditional_questions.create(trigger_question=trigger, trigger_choice=choice, target=outside)

    rule = version.conditional_questions.create(trigger_question=trigger, trigger_choice=choice, target=target)
    assert rule.group_placement == group_placement
    group_placement.delete()
    assert not version.conditional_questions.exists()
    assert group.questions.count() == 2


@pytest.mark.django_db
def test_conditional_rule_rejects_an_answer_from_a_different_question_and_a_non_choice_trigger():
    regulator = Regulator.objects.create()
    version = ProcedureTemplate.objects.create(regulator=regulator, regulation=Regulation.objects.create())
    page = version.pages.create(category=ProcedureTemplatePage.objects.create(owner=regulator), position=1)
    trigger_question = ProcedureTemplateQuestion.objects.create(owner=regulator, question_type=ProcedureTemplateQuestion.Kind.SINGLE_CHOICE)
    detail = ProcedureTemplateQuestion.objects.create(owner=regulator)
    choice = detail.choices.create(position=1)
    trigger = page.placements.create(question=trigger_question, position=1)
    target = page.placements.create(question=detail, position=2, is_conditional=True)

    with pytest.raises(ValidationError, match="must belong to the trigger question"):
        version.conditional_questions.create(trigger_question=trigger, trigger_choice=choice, target=target)

    trigger.question = detail
    trigger.save()
    with pytest.raises(ValidationError, match="question with predefined answer choices"):
        version.conditional_questions.create(trigger_question=trigger, trigger_choice=choice, target=target)
