import math
import re
from collections import OrderedDict
from itertools import chain
from typing import TYPE_CHECKING, Any

import pytz
from django.utils import timezone

from governanceplatform.helpers import get_active_company_from_session, is_observer_user, is_user_operator, is_user_regulator

from .models import (
    Answer,
    Incident,
    IncidentWorkflow,
    LogReportRead,
    PredefinedAnswer,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    SectorRegulationWorkflow,
    Workflow,
)

if TYPE_CHECKING:
    from datetime import datetime

    from django.http import HttpRequest
    from pytz.tzinfo import BaseTzInfo

    from governanceplatform.models import User

SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def sanitize_spreadsheet_cell(value: object) -> object:
    """Prevent spreadsheet applications from interpreting exported text as a formula."""
    if isinstance(value, str) and value.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def is_deadline_exceeded(report: Workflow, incident: Incident) -> str:
    latest_incident_workflow = incident.get_latest_incident_workflow_by_workflow(report)
    if latest_incident_workflow is not None:
        return latest_incident_workflow.review_status
    if incident is not None and report is not None:
        sr_workflow = (
            SectorRegulationWorkflow.objects.all()
            .filter(
                sector_regulation=incident.sector_regulation,
                workflow=report,
            )
            .first()
        )
        if sr_workflow is None:
            return "UNDE"

        actual_time = timezone.now()
        if sr_workflow.trigger_event_before_deadline == "DETECT_DATE":
            detection_date = None
            if incident.sector_regulation is not None and incident.sector_regulation.is_detection_date_needed:
                detection_date = incident.incident_detection_date
            else:
                last_report = incident.get_latest_incident_workflow()
                if last_report is not None and last_report.report_timeline is not None:
                    detection_date = last_report.report_timeline.incident_detection_date
            if detection_date is not None:
                dt = actual_time - detection_date
                if math.floor(dt.total_seconds() / 60 / 60) >= sr_workflow.delay_in_hours_before_deadline:
                    return "OUT"
        elif sr_workflow.trigger_event_before_deadline == "NOTIF_DATE":
            dt = actual_time - incident.incident_notification_date
            if math.floor(dt.total_seconds() / 60 / 60) >= sr_workflow.delay_in_hours_before_deadline:
                return "OUT"
        elif sr_workflow.trigger_event_before_deadline == "PREV_WORK":
            previous_workflow = incident.get_previous_workflow(report)
            if previous_workflow is not False:
                previous_incident_workflow = (
                    IncidentWorkflow.objects.all()
                    .filter(incident=incident, workflow=previous_workflow.workflow)
                    .order_by("-timestamp")
                    .first()
                )
                if previous_incident_workflow is not None:
                    dt = actual_time - previous_incident_workflow.timestamp
                    if math.floor(dt.total_seconds() / 60 / 60) >= sr_workflow.delay_in_hours_before_deadline:
                        return "OUT"

    return "UNDE"


def get_workflow_categories(
    workflow: Workflow,
    incident_workflow: IncidentWorkflow | None = None,
    is_new_incident_workflow: bool = False,
) -> list[QuestionCategory]:
    if is_new_incident_workflow:
        category_options = (
            QuestionCategoryOptions.objects.filter(
                id__in=workflow.questionoptions_set.values_list("category_option", flat=True).distinct(),
                questionoptions__deleted_date=None,
            )
            .select_related("question_category")
            .order_by("position")
        )
        seen = set()
        categories = []
        for option in category_options:
            category = option.question_category
            if category.id not in seen:
                seen.add(category.id)
                categories.append(category)

    elif incident_workflow:
        workflow = incident_workflow.workflow

        active_question_options = (
            workflow.questionoptions_set.filter(
                updated_at__lte=incident_workflow.timestamp,
                deleted_date=None,
            )
            .select_related("category_option__question_category")
            .order_by("category_option__position")
            .distinct()
        )

        old_question_options = (
            workflow.questionoptions_set.filter(
                historic__isnull=False,
            )
            .prefetch_related("historic__category_option__question_category")
            .distinct()
        )

        # fetch the categories which are deleted and
        # are not fetched in other request
        deleted_question_options = (
            workflow.questionoptions_set.filter(
                updated_at__lte=incident_workflow.timestamp,
                deleted_date__gte=incident_workflow.timestamp,
            )
            .select_related("category_option__question_category")
            .order_by("category_option__position")
            .distinct()
        )

        active_categories = (q.category_option for q in active_question_options)
        deleted_categories = (q.category_option for q in deleted_question_options)

        old_categories = []
        for q in old_question_options:
            historic = q.historic.filter(timestamp__gte=incident_workflow.timestamp).first()
            if historic:
                old_categories.append(historic.category_option)

        categories_options = list(OrderedDict.fromkeys(chain(active_categories, old_categories, deleted_categories)))
        categories_options = sorted(categories_options, key=lambda c: c.position)
        categories = [c.question_category for c in categories_options]
    else:
        categories = []
    return categories


def group_keys_by_index(keys: list[str], length_fixed_values: int) -> list[str]:
    fixed_keys = keys[:length_fixed_values]
    dynamic_keys = keys[length_fixed_values:]
    groups: OrderedDict[str, list[tuple[int, str]]] = OrderedDict()
    for key in dynamic_keys:
        match = re.match(r"^(.*\D)\s*:?\s*(\d+)$", key)
        if match:
            prefix = match.group(1).strip()
            index = int(match.group(2))
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append((index, key))
        else:
            if key not in groups:
                groups[key] = []
            groups[key].append((0, key))

    grouped_keys = []
    for _prefix, items in groups.items():
        items.sort(key=lambda x: x[0])
        grouped_keys.extend([key for _, key in items])
    return fixed_keys + grouped_keys


def extract_ids(data: list[str]) -> list[int]:
    return [int(item) for item in data if item.isdigit()]


def convert_to_utc(date: datetime | None, local_tz: BaseTzInfo) -> datetime | None:
    if date:
        local_dt = local_tz.localize(date.replace(tzinfo=None))
        return local_dt.astimezone(pytz.utc)
    return None


def create_entry_log(
    user: User, incident: Incident, incident_report: IncidentWorkflow | None, action: str, request: HttpRequest | None = None
) -> None:
    group = user.groups.first()
    role = group.name if group else ""
    entity_name = ""

    if is_user_operator(user) and request:
        active_company = get_active_company_from_session(request)
        entity_name = active_company.name if active_company else ""
    elif is_user_regulator(user):
        regulator = user.regulators.first()
        entity_name = regulator.name if regulator else ""
    elif is_observer_user(user):
        observer = user.observers.first()
        entity_name = observer.name if observer else ""

    LogReportRead.objects.create(
        user=user,
        incident=incident,
        incident_report=incident_report,
        action=action,
        role=role,
        entity_name=entity_name,
    )


def save_answers(incident_workflow: IncidentWorkflow, workflow: Workflow, data: dict[str, Any]) -> None:
    """Save the answers."""
    prefix = "__question__"
    questions_data = {key[slice(len(prefix), None)]: value for key, value in data.items() if key.startswith(prefix)}

    # TO DO manage impact
    if workflow.is_impact_needed:
        impacts = data.get("impacts", [])
        incident_workflow.impacts.set(impacts)
        incident = incident_workflow.incident
        incident.is_significative_impact = False

        if len(impacts) > 0:
            incident.is_significative_impact = True

        incident.save()

    question_options_map = (
        QuestionOptions.objects.filter(report=workflow).select_related("question").prefetch_related("conditional_targets").in_bulk()
    )

    all_predefined_answer_ids = {int(val) for v in questions_data.values() if isinstance(v, list) for val in v if str(val).isdigit()}

    for key, value in questions_data.items():
        question_id = None
        try:
            question_id = int(key)
        except ValueError, TypeError:
            continue
        if question_id:
            question_option = question_options_map[question_id]
            question = question_option.question
            question_type = question.question_type

            # Check if predefined answer was selected for conditional questions
            if question_option.is_conditional:
                required_predefined_answers_list = {c.predefined_answer_id for c in question_option.conditional_targets.all()}
                if not required_predefined_answers_list.intersection(all_predefined_answer_ids):
                    continue

            predefined_answers = []

            if question_type == "FREETEXT":
                answer = value
            elif question_type == "DATE":
                answer = value.strftime("%Y-%m-%d %H:%M") if value else None
            elif question_type == "CL" or question_type == "RL":
                answer = ",".join(map(str, value))
            else:  # MULTI
                predefined_answers = list(PredefinedAnswer.objects.filter(pk__in=value))
                answer = questions_data.get(f"{key}_freetext_answer", None)
            answer_object = Answer.objects.create(
                incident_workflow=incident_workflow,
                question_options=question_option,
                answer=answer,
            )
            answer_object.predefined_answers.set(predefined_answers)
