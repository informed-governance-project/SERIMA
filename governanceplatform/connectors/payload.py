import re

from django.utils import translation


def _iso(value):
    return value.isoformat() if value else None


def _clean_text(value: str) -> str:
    # answers carry CRLF line endings (browser textareas, "Details:\r\n" prefix); collapse to single spaces
    return re.sub(r"\s+", " ", value).strip()


def _build_sectors(incident) -> dict:
    # parent sector -> [child sector, ...], mirroring the PDF report
    sectors: dict[str, list[str]] = {}
    for sector in incident.affected_sectors.all():
        name = sector.get_safe_translation()
        if sector.parent:
            sectors.setdefault(sector.parent.get_safe_translation(), []).append(name)
        else:
            sectors.setdefault(name, [])
    return sectors


def _answer_fields(answer, question_type: str) -> dict:
    from django_countries import countries

    from incidents.globals import REGIONAL_AREA

    choices = [_clean_text(str(choice)) for choice in answer.predefined_answers.all()]
    text = _clean_text(answer.answer) if answer.answer else None
    if question_type == "MULTI":
        return {"answer": choices}
    if question_type == "SO":
        return {"answer": choices[0] if choices else None}
    if question_type == "MT":
        return {"answer": choices, "details": text}
    if question_type == "ST":
        return {"answer": choices[0] if choices else None, "details": text}
    if question_type in ("CL", "RL"):
        # stored as comma-separated codes
        names = dict(countries) if question_type == "CL" else dict(REGIONAL_AREA)
        return {"answer": [str(names.get(code, code)) for code in filter(None, (answer.answer or "").split(","))]}
    return {"answer": text}


def _build_questionnaire(incident_workflow) -> list[dict]:
    from incidents.models import Answer
    from incidents.pdf_generation import get_question_option_at_submission

    answers_by_category: dict = {}
    answers = (
        Answer.objects.filter(incident_workflow=incident_workflow).select_related("question_options").prefetch_related("predefined_answers")
    )
    for answer in answers:
        question_option = get_question_option_at_submission(answer)
        answers_by_category.setdefault(question_option.category_option, []).append((question_option, answer))

    categories = []
    for category_option in sorted(answers_by_category, key=lambda category: category.position):
        questions = {
            question_option.question.reference: {
                "question_reference": question_option.question.reference,
                "question": str(question_option),
                "question_type": question_option.question.question_type,
                **_answer_fields(answer, question_option.question.question_type),
            }
            for question_option, answer in sorted(answers_by_category[category_option], key=lambda item: item[0].position)
        }
        categories.append({"category": str(category_option), "questions": questions})
    return categories


def _build_reports(incident) -> list[dict]:
    reports = []
    for incident_workflow in incident.get_latest_incident_workflows():
        timeline = incident_workflow.report_timeline
        report = {
            "name": str(incident_workflow.workflow) if incident_workflow.workflow else "",
            "review_status": incident_workflow.get_review_status_display(),
            "timeline": {
                "detection_date": _iso(timeline.incident_detection_date) if timeline else None,
                "starting_date": _iso(timeline.incident_starting_date) if timeline else None,
                "resolution_date": _iso(timeline.incident_resolution_date) if timeline else None,
            },
            "questionnaire": _build_questionnaire(incident_workflow),
        }
        impacts = sorted(impact.safe_translation_getter("label", any_language=True) for impact in incident_workflow.impacts.all())
        if impacts:
            report["impacts"] = impacts
        reports.append(report)
    return reports


def build_incident_payload(incident) -> dict:
    """JSON-serializable equivalent of the PDF incident report (details, contacts, timeline, reports)."""
    # the payload is always in English, independent of the worker's active language
    with translation.override("en"):
        return _build_incident_payload(incident)


def _build_incident_payload(incident) -> dict:
    sector_regulation = incident.sector_regulation
    latest_report = incident.get_latest_incident_workflow()
    timeline = latest_report.report_timeline if latest_report else None

    return {
        "incident": {
            "id": incident.pk,
            "incident_id": incident.incident_id,
            "company_name": incident.company_name,
            "complaint_reference": incident.complaint_reference,
            "status": incident.get_incident_status_display(),
            "is_significative_impact": incident.is_significative_impact,
            "regulation": str(sector_regulation.regulation) if sector_regulation else "",
            "regulator": str(sector_regulation.regulator) if sector_regulation else "",
            "sectors": _build_sectors(incident),
            "timeline": {
                "timezone": incident.incident_timezone,
                "notification_date": _iso(incident.incident_notification_date),
                "detection_date": _iso(timeline.incident_detection_date) if timeline else None,
                "starting_date": _iso(timeline.incident_starting_date) if timeline else None,
                "resolution_date": _iso(timeline.incident_resolution_date) if timeline else None,
            },
            "contacts": {
                "incident": {
                    "first_name": incident.contact_firstname,
                    "last_name": incident.contact_lastname,
                    "title": incident.contact_title,
                    "email": incident.contact_email,
                    "telephone": incident.contact_telephone,
                },
                "technical": {
                    "first_name": incident.technical_firstname,
                    "last_name": incident.technical_lastname,
                    "title": incident.technical_title,
                    "email": incident.technical_email,
                    "telephone": incident.technical_telephone,
                },
            },
            "reports": _build_reports(incident),
        },
    }
