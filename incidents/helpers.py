import math
from collections import OrderedDict
from itertools import chain

from django.utils import timezone

from .models import IncidentWorkflow, QuestionCategoryOptions, SectorRegulationWorkflow


def is_deadline_exceeded(report, incident):
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
        actual_time = timezone.now()
        if sr_workflow.trigger_event_before_deadline == "DETECT_DATE":
            detection_date = None
            if incident.sector_regulation.is_detection_date_needed:
                detection_date = incident.incident_detection_date
            else:
                last_report = incident.get_latest_incident_workflow()
                if last_report is not None:
                    detection_date = last_report.report_timeline.incident_detection_date
            if detection_date is not None:
                dt = actual_time - incident.incident_detection_date
                if math.floor(dt.total_seconds() / 60 / 60) >= sr_workflow.delay_in_hours_before_deadline:
                    return "OUT"
        elif sr_workflow.trigger_event_before_deadline == "NOTIF_DATE":
            dt = actual_time - incident.incident_notification_date
            if math.floor(dt.total_seconds() / 60 / 60) >= sr_workflow.delay_in_hours_before_deadline:
                return "OUT"
        elif sr_workflow.trigger_event_before_deadline == "PREV_WORK" and incident.get_previous_workflow(report) is not False:
            previous_workflow = incident.get_previous_workflow(report)
            previous_incident_workflow = (
                IncidentWorkflow.objects.all().filter(incident=incident, workflow=previous_workflow.workflow).order_by("-timestamp").first()
            )
            if previous_incident_workflow is not None:
                dt = actual_time - previous_incident_workflow.timestamp
                if math.floor(dt.total_seconds() / 60 / 60) >= sr_workflow.delay_in_hours_before_deadline:
                    return "OUT"

    return "UNDE"


def get_workflow_categories(
    workflow,
    incident_workflow=None,
    is_new_incident_workflow=False,
):
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
