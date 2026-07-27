from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.management.color import no_style
from django.db import connection

from incidents.models import (
    ConditionalQuestionOption,
    Email,
    Impact,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    SectorRegulation,
    SectorRegulationWorkflow,
    SectorRegulationWorkflowEmail,
    Workflow,
)

if TYPE_CHECKING:
    from django.db.models import Model


@pytest.mark.django_db
def test_import_sector_regulation_reuses_questions(
    populate_incident_db,
    tmp_path,
):
    input_path = _export_configuration(tmp_path, 1)
    source = SectorRegulation.objects.get(pk=1)
    target = SectorRegulation.objects.create(
        pk=100,
        name="Blank configuration",
        regulation=source.regulation,
        regulator_id=2,
    )
    _reset_imported_model_sequences()
    question_count = Question.objects.count()
    answer_count = PredefinedAnswer.objects.count()

    call_command("import_sector_regulation", input_path, target.pk)

    target.refresh_from_db()
    links = list(
        SectorRegulationWorkflow.objects.filter(
            sector_regulation=target,
        )
        .select_related("workflow")
        .order_by("position")
    )
    assert len(links) == 2
    assert [link.workflow.name for link in links] == [
        "Reg 1 preli (import 2)",
        "Reg 1 final (import 2)",
    ]
    assert Question.objects.count() == question_count
    assert PredefinedAnswer.objects.count() == answer_count
    assert target.safe_translation_getter("name", any_language=True) == ("asectorial workflow")
    assert all(link.workflow.creator_id == target.regulator_id for link in links)
    assert all(
        option.question.reference in {"1", "2", "3", "4", "5"} for link in links for option in link.workflow.questionoptions_set.all()
    )


@pytest.mark.django_db
def test_import_sector_regulation_create_forces_new_questions(
    populate_incident_db,
    tmp_path,
):
    source_option = QuestionOptions.objects.get(
        report_id=1,
        question__reference="1",
    )
    next_option = QuestionOptions.objects.get(
        report_id=1,
        question__reference="2",
    )
    answer = (
        PredefinedAnswer.objects.filter(
            question=source_option.question,
        )
        .order_by("position", "pk")
        .first()
    )
    assert answer is not None
    ConditionalQuestionOption.objects.create(
        question_options=source_option,
        predefined_answer=answer,
        next_question_options=next_option,
    )
    SectorRegulationWorkflowEmail.objects.create(
        sector_regulation_workflow=SectorRegulationWorkflow.objects.get(
            sector_regulation_id=1,
            position=1,
        ),
        email_id=1,
        delay_in_hours=2,
        headline="Reminder headline",
    )
    input_path = _export_configuration(tmp_path, 1)
    source = SectorRegulation.objects.get(pk=1)
    target = SectorRegulation.objects.create(
        pk=101,
        name="Blank configuration",
        regulation=source.regulation,
        regulator=source.regulator,
    )
    _reset_imported_model_sequences()
    question_count = Question.objects.count()
    answer_count = PredefinedAnswer.objects.count()
    conditional_count = ConditionalQuestionOption.objects.count()
    reminder_count = SectorRegulationWorkflowEmail.objects.count()

    call_command(
        "import_sector_regulation",
        input_path,
        target.pk,
        create=True,
    )

    assert Question.objects.count() == question_count + 5
    assert PredefinedAnswer.objects.count() == answer_count + 4
    assert ConditionalQuestionOption.objects.count() == conditional_count + 1
    assert SectorRegulationWorkflowEmail.objects.count() == reminder_count + 1
    imported_references = {
        option.question.reference
        for link in SectorRegulationWorkflow.objects.filter(
            sector_regulation=target,
        )
        for option in link.workflow.questionoptions_set.all()
    }
    assert imported_references == {
        "1_import_2",
        "2_import_2",
        "3_import_2",
        "4_import_2",
        "5_import_2",
    }


@pytest.mark.django_db
def test_import_sector_regulation_rolls_back_on_late_failure(
    populate_incident_db,
    tmp_path,
):
    input_path = _export_configuration(tmp_path, 1)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    data["sector_regulation"]["sectors"] = [
        {
            "acronym": "MISSING",
            "parent_acronym": None,
            "translations": [{"language_code": "en", "name": "Missing"}],
        }
    ]
    input_path.write_text(json.dumps(data), encoding="utf-8")
    source = SectorRegulation.objects.get(pk=1)
    target = SectorRegulation.objects.create(
        pk=102,
        name="Blank configuration",
        regulation=source.regulation,
        regulator=source.regulator,
    )
    _reset_imported_model_sequences()
    counts_before = (
        Workflow.objects.count(),
        Email.objects.count(),
        QuestionCategory.objects.count(),
    )

    with pytest.raises(CommandError, match="no changes were saved"):
        call_command("import_sector_regulation", input_path, target.pk)

    assert not SectorRegulationWorkflow.objects.filter(sector_regulation=target).exists()
    assert (
        Workflow.objects.count(),
        Email.objects.count(),
        QuestionCategory.objects.count(),
    ) == counts_before
    target.refresh_from_db()
    assert target.safe_translation_getter("name", any_language=True) == ("Blank configuration")


@pytest.mark.django_db
def test_import_sector_regulation_rejects_non_blank_target(
    populate_incident_db,
    tmp_path,
):
    input_path = _export_configuration(tmp_path, 1)

    with pytest.raises(CommandError, match="is not blank"):
        call_command("import_sector_regulation", input_path, 1)


def _export_configuration(tmp_path, sector_regulation_id):
    input_path = tmp_path / f"sector-regulation-{sector_regulation_id}.json"
    call_command(
        "export_sector_regulation",
        sector_regulation_id,
        output=input_path,
    )
    return input_path


def _reset_imported_model_sequences():
    model_classes: list[type[Model]] = [
        Email,
        Workflow,
        QuestionCategory,
        QuestionCategoryOptions,
        Question,
        PredefinedAnswer,
        QuestionOptions,
        ConditionalQuestionOption,
        SectorRegulationWorkflow,
        SectorRegulationWorkflowEmail,
        Impact,
    ]
    statements = connection.ops.sequence_reset_sql(no_style(), model_classes)
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
