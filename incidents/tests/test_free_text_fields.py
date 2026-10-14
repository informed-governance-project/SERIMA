"""
Control characters in typed answers.

Text pasted from Word or PDFs can carry invisible control characters, such as a PDF hyphen arriving as
STX (\x02). Exporting such an answer to Excel crashed openpyxl, so the notification forms drop them
before the answer is saved.
"""

from types import SimpleNamespace

import pytest
from django.utils.translation import activate

from incidents.forms import ContactForm, QuestionForm, RegulatorIncidentWorkflowCommentForm
from incidents.models import QuestionCategory, QuestionCategoryOptions, QuestionOptions, Workflow
from incidents.tests.test_conditional_questions import build_form, create_predefined_answer, create_question

PASTED_FROM_PDF = "no evidence of any personal or company\x02critical data being compromised"
WITHOUT_CONTROL_CHARACTER = "no evidence of any personal or companycritical data being compromised"


@pytest.fixture
def free_text_report(db):
    """A single-category report holding a free-text question and a single-choice question with details."""
    activate("en")

    workflow = Workflow.objects.create(name="free text report")
    workflow.set_current_language("en")
    workflow.label = "Free text report"
    workflow.save()

    category = QuestionCategory.objects.create()
    category.set_current_language("en")
    category.label = "Description"
    category.save()
    category_option = QuestionCategoryOptions.objects.create(question_category=category, position=1)

    free_text_option = QuestionOptions.objects.create(
        report=workflow,
        question=create_question("FREETEXT", "FT-DESCRIPTION", "Describe the incident"),
        category_option=category_option,
        position=1,
    )
    details_question = create_question("ST", "FT-DETAILS", "Which systems were involved?")
    details_choice = create_predefined_answer(details_question, "Internal systems", 1)
    details_option = QuestionOptions.objects.create(
        report=workflow,
        question=details_question,
        category_option=category_option,
        position=2,
    )

    return SimpleNamespace(
        workflow=workflow,
        category=category,
        free_text=f"__question__{free_text_option.id}",
        details=f"__question__{details_option.id}",
        details_answer=f"__question__{details_option.id}{QuestionForm.suffix_freetext}",
        details_choice=details_choice,
    )


@pytest.mark.django_db
def test_free_text_answer_drops_control_characters(free_text_report):
    form = build_form(free_text_report, {free_text_report.free_text: PASTED_FROM_PDF})

    assert form.is_valid(), form.errors
    assert form.cleaned_data[free_text_report.free_text] == WITHOUT_CONTROL_CHARACTER


@pytest.mark.django_db
def test_details_answer_drops_control_characters(free_text_report):
    form = build_form(
        free_text_report,
        {
            free_text_report.details: [str(free_text_report.details_choice.id)],
            free_text_report.details_answer: PASTED_FROM_PDF,
        },
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data[free_text_report.details_answer] == WITHOUT_CONTROL_CHARACTER


@pytest.mark.django_db
def test_free_text_answer_keeps_line_breaks_and_tabs(free_text_report):
    form = build_form(free_text_report, {free_text_report.free_text: "first line\r\n\tsecond line"})

    assert form.is_valid(), form.errors
    assert form.cleaned_data[free_text_report.free_text] == "first line\r\n\tsecond line"


def test_regulator_review_comment_drops_control_characters():
    form = RegulatorIncidentWorkflowCommentForm(
        data={"comment": f"<p>{PASTED_FROM_PDF}</p>", "review_status": "PASS"},
        initial={"comment": ""},
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["comment"] == f"<p>{WITHOUT_CONTROL_CHARACTER}</p>"


def test_contact_details_drop_control_characters():
    form = ContactForm(
        data={
            "company_name": "ACME\x0b Corp",
            "contact_lastname": "Doe",
            "contact_firstname": "Jane",
            "contact_title": "CISO",
            "contact_email": "jane.doe@example.com",
            "contact_telephone": "+352 123\x1e456",
            "technical_lastname": "Doe",
            "technical_firstname": "John",
            "technical_title": "Engineer",
            "technical_email": "john.doe@example.com",
            "technical_telephone": "+352 654 321",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["company_name"] == "ACME Corp"
    assert form.cleaned_data["contact_telephone"] == "+352 123456"
