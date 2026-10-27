"""
Control characters in typed declaration text.

Text pasted from Word or PDFs can carry invisible control characters, such as a PDF hyphen arriving as
STX (\x02), which openpyxl refuses to write when declarations are exported to Excel. The declaration
and review forms drop them before the text is saved.
"""

import pytest

from securityobjectives.forms import ReviewForm, SecurityObjectiveAnswerForm, SecurityObjectiveStatusForm

PASTED_FROM_PDF = "a company\x02wide policy\x0bapproved by the board"
WITHOUT_CONTROL_CHARACTERS = "a companywide policyapproved by the board"


@pytest.mark.parametrize("field_name", ["justification", "review_comment"])
def test_measure_answer_text_drops_control_characters(field_name):
    form = SecurityObjectiveAnswerForm({field_name: PASTED_FROM_PDF})

    assert form.is_valid(), form.errors
    assert form.cleaned_data[field_name] == WITHOUT_CONTROL_CHARACTERS


def test_measure_answer_text_keeps_line_breaks_and_tabs():
    form = SecurityObjectiveAnswerForm({"justification": "first line\r\n\tsecond line"})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["justification"] == "first line\r\n\tsecond line"


def test_planned_measures_drop_control_characters():
    form = SecurityObjectiveStatusForm({"actions": PASTED_FROM_PDF})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["actions"] == WITHOUT_CONTROL_CHARACTERS


@pytest.mark.django_db
def test_declaration_review_comment_drops_control_characters():
    form = ReviewForm(
        {"review_comment": f"<p>{PASTED_FROM_PDF}</p>"},
        initial={"status": "PASS", "is_readonly": False},
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["review_comment"] == f"<p>{WITHOUT_CONTROL_CHARACTERS}</p>"
