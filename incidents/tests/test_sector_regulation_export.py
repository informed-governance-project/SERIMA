import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from incidents.models import (
    ConditionalQuestionOption,
    PredefinedAnswer,
    QuestionOptions,
    SectorRegulationWorkflow,
    SectorRegulationWorkflowEmail,
)


@pytest.mark.django_db
def test_export_sector_regulation_configuration(populate_incident_db, tmp_path):
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
        creator_name="REG1",
    )
    reminder = SectorRegulationWorkflowEmail.objects.create(
        sector_regulation_workflow=SectorRegulationWorkflow.objects.get(
            sector_regulation_id=1,
            position=1,
        ),
        email_id=1,
        delay_in_hours=2,
    )
    reminder.set_current_language("en")
    reminder.headline = "Reminder headline"
    reminder.save()
    output_path = tmp_path / "sector-regulation.json"

    call_command("export_sector_regulation", 1, output=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["format"] == "governance-platform-sector-regulation"
    assert data["format_version"] == 1
    assert data["sector_regulation"]["translations"] == [{"language_code": "en", "name": "asectorial workflow"}]
    assert [report["name"] for report in data["reports"]] == [
        "Reg 1 preli",
        "Reg 1 final",
    ]
    assert [link["position"] for link in data["sector_regulation_reports"]] == [1, 2]
    assert [question["reference"] for question in data["questions"]] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert sum(len(question["predefined_answers"]) for question in data["questions"]) == 4
    question_references = {question["key"]: question["reference"] for question in data["questions"]}
    option_questions = {option["key"]: option["question"] for option in data["question_options"]}
    conditional = data["conditional_questions"][0]
    assert question_references[option_questions[conditional["question_option"]]] == "1"
    assert question_references[option_questions[conditional["next_question_option"]]] == "2"
    assert conditional["predefined_answer"] == "answer_1"
    assert conditional["creator_name"] == "REG1"
    assert data["sector_regulation_reports"][0]["reminder_emails"][0]["translations"] == [
        {
            "language_code": "en",
            "headline": "Reminder headline",
        }
    ]
    assert not _contains_database_id(data)


@pytest.mark.django_db
def test_export_sector_regulation_refuses_to_overwrite(
    populate_incident_db,
    tmp_path,
):
    output_path = tmp_path / "sector-regulation.json"
    output_path.write_text("existing", encoding="utf-8")

    with pytest.raises(CommandError, match="already exists"):
        call_command("export_sector_regulation", 1, output=output_path)

    assert output_path.read_text(encoding="utf-8") == "existing"


@pytest.mark.django_db
def test_export_sector_regulation_includes_regulation_impacts(
    populate_incident_db,
    tmp_path,
):
    sector_regulation = next(item for item in populate_incident_db["incidents_workflows"] if item.pk == 2)
    parent_sector = next(sector for sector in populate_incident_db["sectors"] if sector.acronym == "ENE")
    for sector in populate_incident_db["incidents_impacts"][0].sectors.all():
        sector.parent = parent_sector
        sector.save()
    for impact in populate_incident_db["incidents_impacts"]:
        impact.regulations.add(sector_regulation.regulation)
    output_path = tmp_path / "sector-regulation.json"

    call_command("export_sector_regulation", 2, output=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["impacts"]) == 3
    expected_sectors = sorted(sector.acronym for sector in populate_incident_db["incidents_impacts"][0].sectors.all())
    assert data["impacts"][0]["sectors"] == expected_sectors
    exported_sectors = {sector["acronym"]: sector for sector in data["sectors"]}
    assert set(expected_sectors) <= exported_sectors.keys()
    assert {exported_sectors[acronym]["parent_acronym"] for acronym in expected_sectors} == {"ENE"}
    assert "ENE" in exported_sectors


@pytest.mark.django_db
def test_export_sector_regulation_reports_unknown_identifier(tmp_path):
    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "export_sector_regulation",
            999_999,
            output=tmp_path / "missing.json",
        )


def _contains_database_id(value):
    if isinstance(value, dict):
        return any(key == "id" or key.endswith("_id") or _contains_database_id(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_database_id(child) for child in value)
    return False
