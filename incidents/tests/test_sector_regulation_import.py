import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from governanceplatform.models import Sector
from incidents.configuration_export import FORMAT_NAME, FORMAT_VERSION
from incidents.models import (
    ConditionalQuestionOption,
    Email,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    SectorRegulation,
    SectorRegulationWorkflow,
    SectorRegulationWorkflowEmail,
    Workflow,
)


@pytest.mark.django_db
def test_import_sector_regulation_reuses_questions(populate_db, tmp_path):
    target = _create_target(populate_db)
    existing_questions = _create_existing_questions(target)
    _create_existing_report(target)
    input_path = _write_configuration(tmp_path)
    question_count = Question.objects.count()
    answer_count = PredefinedAnswer.objects.count()
    stdout = StringIO()

    call_command(
        "import_sector_regulation",
        input_path,
        target.pk,
        stdout=stdout,
    )

    target.refresh_from_db()
    link = SectorRegulationWorkflow.objects.select_related("workflow").get(sector_regulation=target)
    imported_questions = {option.question for option in link.workflow.questionoptions_set.select_related("question")}
    assert link.workflow.name == "Imported report (import 2)"
    assert imported_questions == set(existing_questions)
    assert Question.objects.count() == question_count
    assert PredefinedAnswer.objects.count() == answer_count
    assert not ConditionalQuestionOption.objects.exists()
    assert SectorRegulationWorkflowEmail.objects.count() == 1
    assert target.safe_translation_getter("name", any_language=True) == ("Imported configuration")
    assert link.workflow.creator == target.regulator
    assert "2 questions reused" in stdout.getvalue()
    assert "1 predefined answers skipped" in stdout.getvalue()


@pytest.mark.django_db
def test_import_sector_regulation_create_forces_new_questions(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    _create_existing_questions(target)
    _create_existing_report(target)
    input_path = _write_configuration(tmp_path)
    question_count = Question.objects.count()
    answer_count = PredefinedAnswer.objects.count()
    stdout = StringIO()

    call_command(
        "import_sector_regulation",
        input_path,
        target.pk,
        create=True,
        stdout=stdout,
    )

    imported_references = {
        option.question.reference
        for link in SectorRegulationWorkflow.objects.filter(sector_regulation=target)
        for option in link.workflow.questionoptions_set.select_related("question")
    }
    assert imported_references == {
        "existing-reference_import_2",
        "target-reference_import_2",
    }
    assert Question.objects.count() == question_count + 2
    assert PredefinedAnswer.objects.count() == answer_count + 1
    assert ConditionalQuestionOption.objects.count() == 1
    assert (
        stdout.getvalue() == "Imported configuration into SectorRegulation "
        f"{target.pk}: 1 reports, 1 report links, 1 emails created, "
        "1 categories created, 1 category options created, "
        "2 questions created, 0 questions reused, "
        "1 predefined answers created, 0 predefined answers skipped, "
        "2 question options created, 1 conditional questions created, "
        "1 reminder emails created, 0 impacts created, "
        "0 sectors created, 0 sectors reused, 0 sectors linked.\n"
    )


@pytest.mark.django_db
def test_import_sector_regulation_creates_missing_sectors_and_reuses_existing(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    existing_sector = Sector.objects.get(acronym="ENE")
    existing_sector.creator = populate_db["regulators"][0]
    existing_sector.creator_name = "Original creator"
    existing_sector.save()
    original_name = existing_sector.safe_translation_getter("name", any_language=True)
    data = _configuration_data()
    data["sectors"] = [
        {
            "acronym": "NEW",
            "parent_acronym": "TOP",
            "translations": _translations(name="New child"),
        },
        {
            "acronym": "TOP",
            "parent_acronym": None,
            "translations": _translations(name="New parent"),
        },
        {
            "acronym": "ENE",
            "parent_acronym": None,
            "translations": _translations(name="Changed name"),
        },
    ]
    data["sector_regulation"]["sectors"] = [
        {"acronym": "NEW"},
        {"acronym": "ENE"},
    ]
    data["impacts"] = [
        {
            "translations": _translations(
                label="Imported impact",
                headline="Imported impact headline",
            ),
            "sectors": ["NEW"],
        }
    ]
    stdout = StringIO()

    call_command(
        "import_sector_regulation",
        _write_configuration(tmp_path, data),
        target.pk,
        stdout=stdout,
    )

    existing_sector.refresh_from_db()
    parent = Sector.objects.get(acronym="TOP")
    child = Sector.objects.get(acronym="NEW")
    target.refresh_from_db()
    assert parent.creator == target.regulator
    assert child.creator == target.regulator
    assert child.parent == parent
    assert existing_sector.creator == populate_db["regulators"][0]
    assert existing_sector.creator_name == "Original creator"
    assert existing_sector.safe_translation_getter("name", any_language=True) == original_name
    assert set(target.sectors.values_list("acronym", flat=True)) == {"ENE", "NEW"}
    assert "2 sectors created" in stdout.getvalue()
    assert "1 sectors reused" in stdout.getvalue()
    assert "2 sectors linked" in stdout.getvalue()


@pytest.mark.django_db
def test_import_sector_regulation_rolls_back_on_late_failure(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    data = _configuration_data()
    data["sector_regulation"]["sectors"] = [
        {
            "acronym": "MISSING",
            "parent_acronym": "UNKNOWN",
            "translations": [{"language_code": "en", "name": "Missing"}],
        }
    ]
    input_path = _write_configuration(tmp_path, data)
    counts_before = (
        Workflow.objects.count(),
        Email.objects.count(),
        QuestionCategory.objects.count(),
        Sector.objects.count(),
    )

    with pytest.raises(CommandError, match="no changes were saved"):
        call_command("import_sector_regulation", input_path, target.pk)

    assert not SectorRegulationWorkflow.objects.filter(sector_regulation=target).exists()
    assert (
        Workflow.objects.count(),
        Email.objects.count(),
        QuestionCategory.objects.count(),
        Sector.objects.count(),
    ) == counts_before
    target.refresh_from_db()
    assert target.safe_translation_getter("name", any_language=True) == ("Blank configuration")


@pytest.mark.django_db
def test_import_sector_regulation_rejects_non_blank_target(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    report = _create_existing_report(target)
    SectorRegulationWorkflow.objects.create(
        sector_regulation=target,
        workflow=report,
        position=1,
    )

    with pytest.raises(CommandError, match="is not blank"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path),
            target.pk,
        )


@pytest.mark.django_db
def test_import_sector_regulation_rejects_invalid_boolean(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    data = _configuration_data()
    data["reports"][0]["is_impact_needed"] = "false"

    with pytest.raises(CommandError, match="must be a boolean"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path, data),
            target.pk,
        )


@pytest.mark.django_db
def test_import_sector_regulation_rejects_invalid_choice(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    data = _configuration_data()
    data["questions"][0]["question_type"] = "INVALID"

    with pytest.raises(CommandError, match="unsupported value"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path, data),
            target.pk,
        )


@pytest.mark.django_db
def test_import_sector_regulation_rejects_unknown_reference(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    data = _configuration_data()
    data["question_options"][0]["report"] = "missing_report"

    with pytest.raises(CommandError, match="Unknown report reference"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path, data),
            target.pk,
        )

    assert not Email.objects.exists()


@pytest.mark.django_db
def test_import_sector_regulation_rejects_malformed_sector(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    data = _configuration_data()
    data["sector_regulation"]["sectors"] = [None]

    with pytest.raises(CommandError, match="sector.*must be an object"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path, data),
            target.pk,
        )


@pytest.mark.django_db
def test_import_sector_regulation_reports_unknown_target(populate_db, tmp_path):
    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path),
            999_999,
        )


@pytest.mark.django_db
def test_import_sector_regulation_rejects_unknown_format_version(
    populate_db,
    tmp_path,
):
    target = _create_target(populate_db)
    data = _configuration_data()
    data["format_version"] = FORMAT_VERSION + 1

    with pytest.raises(CommandError, match="Unsupported format version"):
        call_command(
            "import_sector_regulation",
            _write_configuration(tmp_path, data),
            target.pk,
        )


def test_import_sector_regulation_reports_missing_input(tmp_path):
    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "import_sector_regulation",
            tmp_path / "missing.json",
            1,
        )


def test_import_sector_regulation_reports_invalid_json(tmp_path):
    input_path = tmp_path / "invalid.json"
    input_path.write_text("{", encoding="utf-8")

    with pytest.raises(CommandError, match="Cannot read"):
        call_command("import_sector_regulation", input_path, 1)


def _create_target(populate_db) -> SectorRegulation:
    target = SectorRegulation.objects.create(
        regulation=populate_db["regulations"][0],
        regulator=populate_db["regulators"][1],
    )
    _set_english_translation(target, name="Blank configuration")
    return target


def _create_existing_questions(
    target: SectorRegulation,
) -> list[Question]:
    questions = []
    for reference, question_type, label in (
        ("existing-reference", "SO", "Existing question"),
        ("target-reference", "FREETEXT", "Target question"),
    ):
        question = Question.objects.create(
            reference=reference,
            question_type=question_type,
            creator=target.regulator,
        )
        _set_english_translation(question, label=label, tooltip="")
        questions.append(question)
    return questions


def _create_existing_report(target: SectorRegulation) -> Workflow:
    report = Workflow.objects.create(
        name="Imported report",
        creator=target.regulator,
    )
    _set_english_translation(
        report,
        label="Existing report",
        description="",
    )
    return report


def _set_english_translation(instance, **values: Any) -> None:
    instance.set_current_language("en")
    for field, value in values.items():
        setattr(instance, field, value)
    instance.save()


def _write_configuration(
    tmp_path: Path,
    data: dict[str, Any] | None = None,
) -> Path:
    input_path = tmp_path / "sector-regulation.json"
    input_path.write_text(
        json.dumps(data or _configuration_data()),
        encoding="utf-8",
    )
    return input_path


def _configuration_data() -> dict[str, Any]:
    return {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "sector_regulation": {
            "active": True,
            "is_detection_date_needed": False,
            "translations": _translations(name="Imported configuration"),
            "sectors": [],
            "opening_email": "email_1",
            "closing_email": None,
            "report_status_changed_email": None,
        },
        "emails": [
            {
                "key": "email_1",
                "name": "Imported email",
                "translations": _translations(
                    subject="Imported subject",
                    content="Imported content",
                ),
            }
        ],
        "reports": [
            {
                "key": "report_1",
                "name": "Imported report",
                "is_impact_needed": False,
                "submission_email": "email_1",
                "translations": _translations(
                    label="Imported report",
                    description="",
                ),
            }
        ],
        "categories": [
            {
                "key": "category_1",
                "translations": _translations(label="Imported category"),
            }
        ],
        "category_options": [
            {
                "key": "category_option_1",
                "category": "category_1",
                "position": 1,
            }
        ],
        "questions": [
            {
                "key": "question_1",
                "reference": "existing-reference",
                "question_type": "SO",
                "translations": _translations(
                    label="Existing question",
                    tooltip="",
                ),
                "predefined_answers": [
                    {
                        "key": "answer_1",
                        "position": 1,
                        "translations": _translations(predefined_answer="Yes"),
                    }
                ],
            },
            {
                "key": "question_2",
                "reference": "target-reference",
                "question_type": "FREETEXT",
                "translations": _translations(
                    label="Target question",
                    tooltip="",
                ),
                "predefined_answers": [],
            },
        ],
        "question_options": [
            {
                "key": "question_option_1",
                "report": "report_1",
                "question": "question_1",
                "category_option": "category_option_1",
                "position": 1,
                "is_mandatory": False,
                "is_conditional": False,
            },
            {
                "key": "question_option_2",
                "report": "report_1",
                "question": "question_2",
                "category_option": "category_option_1",
                "position": 2,
                "is_mandatory": False,
                "is_conditional": True,
            },
        ],
        "conditional_questions": [
            {
                "question_option": "question_option_1",
                "predefined_answer": "answer_1",
                "next_question_option": "question_option_2",
            }
        ],
        "sector_regulation_reports": [
            {
                "report": "report_1",
                "position": 1,
                "delay_in_hours_before_deadline": 0,
                "trigger_event_before_deadline": "NONE",
                "reminder_emails": [
                    {
                        "email": "email_1",
                        "trigger_event": "NOTIF_DATE",
                        "delay_in_hours": 2,
                        "translations": _translations(headline="Reminder headline"),
                    }
                ],
            }
        ],
        "impacts": [],
    }


def _translations(**fields: Any) -> list[dict[str, Any]]:
    return [{"language_code": "en", **fields}]
