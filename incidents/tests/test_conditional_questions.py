from types import SimpleNamespace

import pytest
from django.template import Context, Template
from django.utils.translation import activate

from incidents.forms import QuestionForm
from incidents.models import (
    ConditionalQuestionOption,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    Workflow,
)


def create_question(question_type: str, reference: str, label: str) -> Question:
    question = Question.objects.create(question_type=question_type, reference=reference)
    question.set_current_language("en")
    question.label = label
    question.save()
    return question


def create_predefined_answer(question: Question, label: str, position: int) -> PredefinedAnswer:
    answer = PredefinedAnswer.objects.create(question=question, position=position)
    answer.set_current_language("en")
    answer.predefined_answer = label
    answer.save()
    return answer


def render_bootstrap_field(bound_field) -> str:
    """Render a field the way the declaration template does, through django-bootstrap5."""
    return Template("{% load django_bootstrap5 %}{% bootstrap_field field %}").render(Context({"field": bound_field}))


def build_form(report, data=None) -> QuestionForm:
    return QuestionForm(
        data=data,
        position=0,
        workflow=report.workflow,
        categories_workflow=[report.category],
        is_new_incident_workflow=True,
    )


@pytest.fixture
def conditional_report(db):
    """
    A single-category report holding a single-option trigger question, a mandatory question
    conditioned on its "Yes" answer, an optional single-choice-plus-free-text question conditioned on
    its "Partially" answer, and a mandatory question displayed unconditionally.
    """
    activate("en")

    workflow = Workflow.objects.create(name="conditional report")
    workflow.set_current_language("en")
    workflow.label = "Conditional report"
    workflow.save()

    category = QuestionCategory.objects.create()
    category.set_current_language("en")
    category.label = "Impact"
    category.save()

    category_option = QuestionCategoryOptions.objects.create(question_category=category, position=1)

    trigger_question = create_question("SO", "COND-TRIGGER", "Were personal data affected?")
    yes = create_predefined_answer(trigger_question, "Yes", 1)
    no = create_predefined_answer(trigger_question, "No", 2)
    partially = create_predefined_answer(trigger_question, "Partially", 3)

    trigger_option = QuestionOptions.objects.create(
        report=workflow,
        question=trigger_question,
        category_option=category_option,
        position=1,
        is_mandatory=True,
    )
    conditional_option = QuestionOptions.objects.create(
        report=workflow,
        question=create_question("FREETEXT", "COND-TARGET", "Which personal data were affected?"),
        category_option=category_option,
        position=2,
        is_mandatory=True,
        is_conditional=True,
    )
    plain_option = QuestionOptions.objects.create(
        report=workflow,
        question=create_question("FREETEXT", "COND-PLAIN", "Describe the incident"),
        category_option=category_option,
        position=3,
        is_mandatory=True,
    )

    details_question = create_question("ST", "COND-DETAILS", "Which systems were involved?")
    details_choice = create_predefined_answer(details_question, "Internal systems", 1)
    details_option = QuestionOptions.objects.create(
        report=workflow,
        question=details_question,
        category_option=category_option,
        position=4,
        is_conditional=True,
    )

    multi_question = create_question("MULTI", "COND-MULTI", "Which services were affected?")
    multi_answer = create_predefined_answer(multi_question, "Fixed voice", 1)
    multi_option = QuestionOptions.objects.create(
        report=workflow,
        question=multi_question,
        category_option=category_option,
        position=5,
    )
    multi_target_option = QuestionOptions.objects.create(
        report=workflow,
        question=create_question("FREETEXT", "COND-MULTI-TARGET", "Why did you choose this?"),
        category_option=category_option,
        position=6,
        is_conditional=True,
    )

    ConditionalQuestionOption.objects.create(
        question_options=trigger_option,
        predefined_answer=yes,
        next_question_options=conditional_option,
    )
    ConditionalQuestionOption.objects.create(
        question_options=trigger_option,
        predefined_answer=partially,
        next_question_options=details_option,
    )
    ConditionalQuestionOption.objects.create(
        question_options=multi_option,
        predefined_answer=multi_answer,
        next_question_options=multi_target_option,
    )

    return SimpleNamespace(
        workflow=workflow,
        category=category,
        conditional_option=conditional_option,
        trigger=f"__question__{trigger_option.id}",
        conditional=f"__question__{conditional_option.id}",
        plain=f"__question__{plain_option.id}",
        details=f"__question__{details_option.id}",
        details_answer=f"__question__{details_option.id}{QuestionForm.suffix_freetext}",
        details_choice=details_choice,
        multi=f"__question__{multi_option.id}",
        multi_target_id=multi_target_option.id,
        yes=yes,
        no=no,
        partially=partially,
    )


@pytest.mark.django_db
def test_a_conditional_question_may_be_mandatory(conditional_report):
    """A question marked both mandatory and conditionally displayed is a valid configuration."""
    conditional_report.conditional_option.full_clean()


@pytest.mark.django_db
def test_untriggered_mandatory_conditional_question_does_not_block_the_step(conditional_report):
    """While its trigger answer is unselected the question stays hidden, so it cannot be required."""
    form = build_form(
        conditional_report,
        {
            conditional_report.trigger: [str(conditional_report.no.id)],
            conditional_report.plain: "Something happened",
        },
    )

    assert form.is_valid(), form.errors
    assert conditional_report.conditional not in form.cleaned_data


@pytest.mark.django_db
def test_triggered_mandatory_conditional_question_must_be_answered(conditional_report):
    """Once the trigger answer is selected the question is displayed and its mandatory flag applies."""
    form = build_form(
        conditional_report,
        {
            conditional_report.trigger: [str(conditional_report.yes.id)],
            conditional_report.plain: "Something happened",
        },
    )

    assert not form.is_valid()
    assert conditional_report.conditional in form.errors


@pytest.mark.django_db
def test_triggered_mandatory_conditional_question_accepts_its_answer(conditional_report):
    """A displayed conditional question keeps the answer it was given."""
    form = build_form(
        conditional_report,
        {
            conditional_report.trigger: [str(conditional_report.yes.id)],
            conditional_report.conditional: "Names and postal addresses",
            conditional_report.plain: "Something happened",
        },
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data[conditional_report.conditional] == "Names and postal addresses"


@pytest.mark.django_db
def test_answer_of_an_untriggered_conditional_question_is_discarded(conditional_report):
    """An answer left behind by a trigger the user unselected must not reach save_answers()."""
    form = build_form(
        conditional_report,
        {
            conditional_report.trigger: [str(conditional_report.no.id)],
            conditional_report.conditional: "Answered before the trigger was unselected",
            conditional_report.plain: "Something happened",
        },
    )

    assert form.is_valid(), form.errors
    assert conditional_report.conditional not in form.cleaned_data


@pytest.mark.django_db
def test_details_field_of_a_conditional_question_is_folded_away_with_it(conditional_report):
    """The template reads is_conditional to hide a question, so its "Add details" field carries it too."""
    form = build_form(conditional_report)

    assert form.fields[conditional_report.details].is_conditional
    assert form.fields[conditional_report.details_answer].is_conditional


@pytest.mark.django_db
def test_triggered_conditional_question_keeps_its_details_answer(conditional_report):
    """A displayed conditional question keeps both its choice and the details typed alongside it."""
    form = build_form(
        conditional_report,
        {
            conditional_report.trigger: [str(conditional_report.partially.id)],
            conditional_report.details: [str(conditional_report.details_choice.id)],
            conditional_report.details_answer: "The mail server",
            conditional_report.plain: "Something happened",
        },
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data[conditional_report.details] == [str(conditional_report.details_choice.id)]
    assert form.cleaned_data[conditional_report.details_answer] == "The mail server"


@pytest.mark.django_db
def test_details_answer_of_an_untriggered_conditional_question_is_discarded(conditional_report):
    """Details left behind by a trigger the user unselected must not reach save_answers() either."""
    form = build_form(
        conditional_report,
        {
            conditional_report.trigger: [str(conditional_report.no.id)],
            conditional_report.details: [str(conditional_report.details_choice.id)],
            conditional_report.details_answer: "Typed before the trigger was unselected",
            conditional_report.plain: "Something happened",
        },
    )

    assert form.is_valid(), form.errors
    assert conditional_report.details not in form.cleaned_data
    assert conditional_report.details_answer not in form.cleaned_data


@pytest.mark.django_db
def test_single_option_trigger_marks_the_answer_opening_a_conditional_question(conditional_report):
    """syncConditionals() folds a question in and out by reading data-next-question-id on the answer."""
    rendered = render_bootstrap_field(build_form(conditional_report)[conditional_report.trigger])

    assert f'data-next-question-id="{conditional_report.conditional_option.id}"' in rendered


@pytest.mark.django_db
def test_multiple_choice_trigger_marks_the_answer_opening_a_conditional_question(conditional_report):
    """The mark has to survive whichever template django-bootstrap5 would have rendered the widget
    with: 26.2 emits a fixed set of attributes on each input, 26.3 emits the attributes of the
    option, and the wrapper carries them in neither the same way nor at all."""
    rendered = render_bootstrap_field(build_form(conditional_report)[conditional_report.multi])

    assert f'data-next-question-id="{conditional_report.multi_target_id}"' in rendered
    assert 'class="form-check-input"' in rendered


@pytest.mark.django_db
def test_conditional_question_is_rendered_without_the_html_required_attribute(conditional_report):
    """A hidden control carrying the attribute makes the browser refuse the submit with no message."""
    form = build_form(conditional_report)

    assert "required" not in str(form[conditional_report.conditional])
    assert "required" in str(form[conditional_report.plain])
