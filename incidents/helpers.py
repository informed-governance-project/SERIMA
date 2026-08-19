import math
from collections import OrderedDict
from itertools import chain

from django.db.models import BooleanField, Exists, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from governanceplatform.models import ApplicationConfig

from .models import (
    Answer,
    Incident,
    IncidentWorkflow,
    PredefinedAnswer,
    QuestionCategory,
    QuestionCategoryOptions,
    SectorRegulationWorkflow,
    Workflow,
)

# Application config keys designating the question that carries the cross-border
# dimension. The questionnaire is configuration, so the platform cannot know
# which question that is: a deployment names it here.
CROSS_BORDER_QUESTION_REFERENCE_KEY = "cross_border_question_reference"
CROSS_BORDER_POSITIVE_ANSWER_KEY = "cross_border_positive_answer"
DEFAULT_CROSS_BORDER_POSITIVE_ANSWER = "Yes"


def get_application_config(key, default=None):
    try:
        return ApplicationConfig.objects.get(key=key).value
    except ApplicationConfig.DoesNotExist:
        return default


def annotate_cross_border_impact(queryset):
    """Annotate incidents with ``is_cross_border_impact``.

    The flag reports the answer given in the most recent report answering the
    designated question, so an incident that becomes cross-border in a later
    report is picked up, and one that is corrected to "no" stops being flagged.

    When no question is designated the annotation is ``False`` everywhere and
    the queryset behaves exactly as before.
    """
    question_reference = get_application_config(CROSS_BORDER_QUESTION_REFERENCE_KEY)
    if not question_reference:
        return queryset.annotate(is_cross_border_impact=Value(False, output_field=BooleanField()))

    positive_answer = get_application_config(
        CROSS_BORDER_POSITIVE_ANSWER_KEY,
        DEFAULT_CROSS_BORDER_POSITIVE_ANSWER,
    )

    latest_answer_is_positive = (
        Answer.objects.filter(
            incident_workflow__incident=OuterRef("pk"),
            question_options__question__reference=question_reference,
        )
        .order_by("-incident_workflow__timestamp", "-timestamp")
        .annotate(
            is_positive=Exists(
                PredefinedAnswer.objects.filter(
                    answer__pk=OuterRef("pk"),
                    translations__predefined_answer__iexact=positive_answer,
                )
            )
        )
        .values("is_positive")[:1]
    )

    return queryset.annotate(
        is_cross_border_impact=Coalesce(
            Subquery(latest_answer_is_positive, output_field=BooleanField()),
            Value(False),
            output_field=BooleanField(),
        )
    )


def is_cross_border_incident(incident: Incident) -> bool:
    """Whether this single incident is currently reported as cross-border.

    Same rule as :func:`annotate_cross_border_impact`, for the one caller that
    holds an incident rather than a queryset. Returns ``False`` when no question
    is designated, so callers need no special case.
    """
    annotated = annotate_cross_border_impact(Incident.objects.filter(pk=incident.pk))
    return annotated.values_list("is_cross_border_impact", flat=True).first() or False


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
