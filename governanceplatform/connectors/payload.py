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


def _build_questionnaire(incident_workflow) -> list[dict]:
    from incidents.models import Answer
    from incidents.pdf_generation import populate_questions_answers

    answers_by_category: dict = {}
    answers = Answer.objects.filter(incident_workflow=incident_workflow).order_by("question_options__position")
    for answer in answers:
        populate_questions_answers(answer, answers_by_category)

    categories = []
    for category_option in sorted(answers_by_category, key=lambda category: category.position):
        questions = [
            {
                "question": str(question_option),
                "answers": [_clean_text(str(answer)) for answer in answer_list],
            }
            for question_option, answer_list in sorted(answers_by_category[category_option].items(), key=lambda item: item[0].position)
        ]
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
