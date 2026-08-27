import csv
import logging
import re
from collections import OrderedDict
from datetime import date
from urllib.parse import urlencode, urlparse

import pytz
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import CharField, F, Q, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.dateparse import parse_datetime
from django.utils.translation import get_language, override
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_countries import countries
from django_otp.decorators import otp_required
from formtools.wizard.views import SessionWizardView
from openpyxl import Workbook

from governanceplatform.decorators import check_user_is_correct, regulator_role_required
from governanceplatform.helpers import (
    annotate_translated_field_from_related_models,
    get_active_company_from_session,
    is_observer_user,
    is_user_operator,
    is_user_regulator,
    render_to_string_multi_languages,
    sort_queryset_by_field,
    translated_queryset,
    user_in_group,
)
from governanceplatform.models import (
    Regulation,
    Sector,
    User,
)
from governanceplatform.settings import (
    MAX_PRELIMINARY_NOTIFICATION_PER_DAY_PER_USER,
    PARLER_DEFAULT_LANGUAGE_CODE,
    PUBLIC_URL,
    SITE_NAME,
    TIME_ZONE,
)

from .access_control import (
    can_access_incident,
    can_create_incident_report,
    can_edit_incident_report,
    get_observer_incidents,
)
from .email import send_email, send_html_email
from .filters import IncidentFilter
from .forms import ContactForm, ExportIncidentsForm, IncidentStatusForm, RegulatorIncidentWorkflowCommentForm, get_forms_list
from .globals import (
    ALLOWED_SORT_FIELDS,
    REGIONAL_AREA,
    REPORT_STATUS_MAP,
    WORKFLOW_REVIEW_STATUS,
)
from .helpers import get_workflow_categories, is_deadline_exceeded, sanitize_spreadsheet_cell
from .models import (
    Answer,
    Impact,
    Incident,
    IncidentWorkflow,
    LogReportRead,
    PredefinedAnswer,
    QuestionOptions,
    ReportTimeline,
    SectorRegulation,
    SectorRegulationWorkflow,
    Workflow,
)
from .pdf_generation import get_pdf_report

logger = logging.getLogger(__name__)


@login_required
@otp_required
@check_user_is_correct
def get_incidents(request):
    """Returns the list of incidents depending on the account type."""
    user = request.user
    incidents = Incident.objects.filter(sector_regulation__isnull=False)
    html_view = "operator/incidents.html"
    search_value = request.GET.get("search", None)

    if "reset_sort" in request.GET:
        request.session.pop("incidents_sort_params", None)
        return redirect("incidents")

    if "reset" in request.GET or search_value == "":
        request.session.pop("incidents_filter_params", None)
        return redirect("incidents")

    # Save filter params in user's session
    current_params = request.session.get("incidents_filter_params", {}).copy()
    current_sort_params = request.session.get("incidents_sort_params", {}).copy()

    for key, values in request.GET.lists():
        if key in ["sort_field", "sort_direction"]:
            continue
        current_params[key] = values if key == "affected_sectors" else values[0]

    for key, value in request.GET.items():
        if key in ("sort_field", "sort_direction"):
            current_sort_params[key] = value

    incidents_filter_params = current_params
    incidents_sort_params = current_sort_params
    request.session["incidents_filter_params"] = incidents_filter_params
    request.session["incidents_sort_params"] = incidents_sort_params

    if is_user_regulator(user):
        html_view = "regulator/incidents.html"
        request.session["is_regulator_incidents"] = False
        if request.path == reverse("regulator_incidents"):
            html_view = "operator/incidents.html"
            # Filter regulator incidents
            incidents = incidents.filter(regulator=user.regulators.first())
            request.session["is_regulator_incidents"] = True
        elif user_in_group(user, "RegulatorUser"):
            # RegulatorUser has access to all incidents linked by sectors.
            incidents = incidents.filter(
                sector_regulation__regulator__in=user.regulators.all(),
                affected_sectors__in=request.user.get_sectors().all(),
            ).distinct()

        else:
            # Filter incidents by regulator
            incidents = incidents.filter(sector_regulation__regulator__in=user.regulators.all())
    elif is_observer_user(user):
        html_view = "observer/incidents.html"
        incidents = get_observer_incidents(user.observers.first())
    elif is_user_operator(user):
        # OperatorAdmin/User can see all the reports of the selected company.
        incidents = incidents.filter(
            company__id=request.session.get("company_in_use"),
            company__companyuser__user=user,
            company__companyuser__approved=True,
        )
    else:
        # IncidentUser can see only their reports.
        incidents = incidents.filter(contact_user=user)

    # Apply sorting
    sort_field = incidents_sort_params.get("sort_field", "last_update")
    sort_direction = incidents_sort_params.get("sort_direction", "desc")

    if sort_field == "company_name":
        annotated_name = ALLOWED_SORT_FIELDS.get(sort_field)["field"]
        incidents = annotate_translated_field_from_related_models(
            incidents,
            full_path="regulator__translations__full_name",
            annotated_name="__regulator_name",
        )
        incidents = incidents.annotate(
            **{
                annotated_name: Coalesce(
                    F("company__name"),
                    F("__regulator_name"),
                    F("company_name"),
                    output_field=CharField(),
                )
            }
        )

    if sort_field == "company_identifier":
        annotated_name = ALLOWED_SORT_FIELDS.get(sort_field)["field"]
        incidents = annotate_translated_field_from_related_models(
            incidents,
            full_path="regulator__translations__name",
            annotated_name="__regulator_identifier",
        )
        incidents = incidents.annotate(
            **{
                annotated_name: Coalesce(
                    F("company__identifier"),
                    F("__regulator_identifier"),
                    Value(""),
                    output_field=CharField(),
                )
            }
        )

    incidents = sort_queryset_by_field(
        incidents,
        sort_field,
        sort_direction,
        "incident_last_update",
        ALLOWED_SORT_FIELDS,
    )

    f = IncidentFilter(incidents_filter_params, queryset=incidents)
    incident_list = f.qs.prefetch_related(
        "sector_regulation__workflows__sectorregulationworkflow_set",
        "incidentworkflow_set__workflow__sectorregulationworkflow_set",
    )

    per_page = incidents_filter_params.get("per_page", 10)
    page_number = incidents_filter_params.get("page")
    paginator = Paginator(incident_list, per_page)
    page_obj = paginator.get_page(page_number)

    for incident in page_obj.object_list:
        incident.all_reports = []
        completed_workflows = incident.get_workflows_completed()
        all_workflows = incident.get_all_workflows()
        completed_workflow_ids = [wf.workflow.id for wf in completed_workflows]
        all_workflow_ids = [wf.id for wf in all_workflows]

        incident.formsStatus = IncidentStatusForm(
            instance=incident,
        )

        for idx, report in enumerate(all_workflows):
            latest = incident.get_latest_incident_workflow_by_workflow(report)
            latest_id = latest.id if latest else None
            report_id = report.id
            latest_incident_workflow = None

            latest_incident_workflow = next(
                (iw for iw in completed_workflows if iw.workflow.id == report.id and (latest_id is None or iw.id == latest_id)),
                None,
            )

            status = (
                latest_incident_workflow.review_status
                if latest_incident_workflow
                else is_deadline_exceeded(
                    report,
                    incident,
                )
            )

            mapping = REPORT_STATUS_MAP.get(status, REPORT_STATUS_MAP["UNDE"])

            is_disabled = False

            if html_view == "operator/incidents.html":
                if incident.incident_status == "CLOSE":
                    is_disabled = True
                if not completed_workflows and idx != 0:
                    is_disabled = True
                elif idx < len(all_workflow_ids) - 1 and all_workflow_ids[idx + 1] in completed_workflow_ids:
                    is_disabled = True
                elif idx < len(all_workflow_ids) - 1 and idx > 1 and all_workflow_ids[idx - 1] not in completed_workflow_ids:
                    is_disabled = True
                elif (
                    len(all_workflow_ids) > 1
                    and idx == len(all_workflow_ids) - 1
                    and all_workflow_ids[idx - 1] not in completed_workflow_ids
                ):
                    is_disabled = True

            incident.all_reports.append(
                {
                    "id": report_id,
                    "name": str(report),
                    "latest_incident_workflow": latest_incident_workflow,
                    "css_class": mapping["class"],
                    "tooltip": mapping["tooltip"],
                    "is_disabled": is_disabled,
                }
            )

    is_filtered = {k: v for k, v in incidents_filter_params.items() if k not in ["page", "per_page", "sort_field", "sort_direction"]}

    return render(
        request,
        html_view,
        context={
            "site_name": SITE_NAME,
            "filter": f,
            "sort_field": sort_field,
            "sort_direction": sort_direction,
            "incidents": page_obj,
            "is_filtered": bool(is_filtered),
            "is_regulator_incidents": request.session.get("is_regulator_incidents", False),
            "can_export_incidents": can_export_incidents(user),
        },
    )


@login_required
@otp_required
@check_user_is_correct
def get_form_list(request, form_list=None):
    """Initialize data for the preliminary notification."""
    if is_incidents_report_limit_reached(request):
        return HttpResponseRedirect("/incidents")
    if form_list is None:
        form_list = get_forms_list()
    contact_form = ContactForm()
    return FormWizardView.as_view(
        form_list,
        initial_dict={"0": contact_form.prepare_initial_value(request=request)},
        condition_dict={
            "3": lambda wizard: show_form_condition(wizard).get("has_sector", False),
            "4": lambda wizard: show_form_condition(wizard).get("detection_date_needed", False),
        },
    )(request)


@login_required
@otp_required
@check_user_is_correct
def create_workflow(request):
    incident_id = request.GET.get("incident_id", None)
    workflow_id = request.GET.get("workflow_id", None)
    if not workflow_id and not incident_id:
        messages.error(request, _("Missing data, incident report not created."))
        return redirect("incidents")

    incident = Incident.objects.filter(pk=incident_id).first()
    workflow = Workflow.objects.filter(id=workflow_id).first()

    if not workflow:
        messages.error(request, _("Workflow not found"))
        return redirect("incidents")

    if not incident:
        messages.error(request, _("Incident not found"))
        return redirect("incidents")

    if incident.incident_status == "CLOSE":
        messages.error(request, _("The incident has been closed"))
        return redirect("incidents")

    if not incident.is_fillable(workflow):
        messages.error(request, _("Forbidden"))
        return redirect("incidents")

    user = request.user
    company_id = request.session.get("company_in_use")

    if not can_create_incident_report(user, incident, company_id):
        messages.error(request, _("Forbidden"))
        return redirect("incidents")
    form_list = get_forms_list(incident=incident)
    request.incident = incident_id
    request.workflow = workflow
    request.incident_workflow = None
    return WorkflowWizardView.as_view(
        form_list,
    )(request)


@login_required
@otp_required
@check_user_is_correct
def review_workflow(request):
    company_id = request.session.get("company_in_use")
    incident_workflow_id = request.GET.get("incident_workflow_id", None)
    if not incident_workflow_id:
        messages.error(request, _("No incident report could be found."))
        return redirect("incidents")
    user = request.user
    try:
        incident_workflow = IncidentWorkflow.objects.get(pk=incident_workflow_id)
    except IncidentWorkflow.DoesNotExist:
        messages.error(request, _("No incident report could be found."))
        return redirect("incidents")

    incident = incident_workflow.incident

    is_regulator_incidents = request.session.get("is_regulator_incidents", False)

    is_regulator_incident = True if incident.regulator == user.regulators.first() and is_regulator_incidents else False

    if can_access_incident(user, incident, company_id):
        form_list = get_forms_list(
            incident=incident_workflow.incident,
            workflow=incident_workflow.workflow,
            incident_workflow=incident_workflow,
            is_regulator=is_user_regulator(user),
            is_regulator_incident=is_regulator_incident,
            read_only=True,
        )
        request.incident_workflow = incident_workflow.id
        return WorkflowWizardView.as_view(
            form_list,
            read_only=True,
        )(request)
    messages.error(request, _("Forbidden"))
    return redirect("incidents")


@login_required
@otp_required
@check_user_is_correct
def edit_workflow(request):
    incident_id = request.GET.get("incident_id", None)
    workflow_id = request.GET.get("workflow_id", None)
    incident_workflow_id = request.GET.get("incident_workflow_id", None)
    user = request.user
    company_id = request.session.get("company_in_use")
    incident_workflow = None
    if not workflow_id and not incident_id and not incident_workflow_id:
        messages.error(request, _("No incident report could be found."))
        return redirect("incidents")
    if workflow_id and incident_id:
        incident = Incident.objects.filter(pk=incident_id).first()
        workflow = Workflow.objects.filter(id=workflow_id).first()
        if not workflow:
            messages.error(request, _("Workflow not found"))
            return redirect("incidents")
        if not incident:
            messages.error(request, _("Incident not found"))
            return redirect("incidents")
        if incident.incident_status == "CLOSE":
            messages.error(request, _("The incident has been closed"))
            return redirect("incidents")
        if not is_user_regulator(user):
            if not incident.is_fillable(workflow):
                messages.error(request, _("Forbidden"))
                return redirect("incidents")
    # for the moment we only pass the incident workflow for regulator
    elif incident_workflow_id and is_user_regulator(user):
        try:
            incident_workflow = IncidentWorkflow.objects.get(pk=incident_workflow_id)
        except IncidentWorkflow.DoesNotExist:
            messages.error(request, _("No incident report could be found."))
            return redirect("incidents")
    else:
        messages.error(request, _("Forbidden"))
        return redirect("incidents")

    is_regulator_incidents = request.session.get("is_regulator_incidents", False)

    if incident_id and can_edit_incident_report(user, incident, company_id):
        is_regulator_incident = True if incident.regulator == user.regulators.first() and is_regulator_incidents else False

        if incident_workflow is None:
            incident_workflow = IncidentWorkflow.objects.filter(incident=incident_id, workflow=workflow_id).order_by("timestamp")
            incident_workflow = incident_workflow.last()

        if incident_workflow:
            request.incident = incident_workflow.incident.id
            form_list = get_forms_list(
                incident=incident_workflow.incident,
                workflow=incident_workflow.workflow,
                incident_workflow=incident_workflow,
                is_regulator=is_user_regulator(user),
                is_regulator_incident=is_regulator_incident,
            )
            request.incident_workflow = incident_workflow.id

            return WorkflowWizardView.as_view(
                form_list,
            )(request)
    if incident_workflow and can_edit_incident_report(user, incident_workflow.incident, company_id):
        is_regulator_incident = (
            True if incident_workflow.incident.regulator == user.regulators.first() and is_regulator_incidents else False
        )

        form_list = get_forms_list(
            incident=incident_workflow.incident,
            workflow=incident_workflow.workflow,
            incident_workflow=incident_workflow,
            is_regulator=is_user_regulator(user),
            is_regulator_incident=is_regulator_incident,
        )
        request.incident_workflow = incident_workflow.id

        return WorkflowWizardView.as_view(
            form_list,
        )(request)

    messages.error(request, _("Forbidden"))
    return redirect("incidents")


@login_required
@otp_required
@regulator_role_required
@check_user_is_correct
@require_http_methods(["POST"])
def edit_incident(request, incident_id: int):
    """Returns the list of incident as regulator."""

    company_id = request.session.get("company_in_use")

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        messages.error(request, _("Incident not found"))
        return redirect("incidents")

    if not can_edit_incident_report(request.user, incident, company_id):
        return redirect("incidents")

    incident_form = IncidentStatusForm(request.POST, instance=incident)

    if incident_form.is_valid():
        incident = incident_form.save(commit=False)
        response = {"id": incident.pk}
        incident_status = incident_form.cleaned_data.get("incident_status")
        old, new = incident_form.get_field_change("is_significative_impact")

        with transaction.atomic():
            incident.save()
            if old != new:
                message = "IMP. True" if new is True else "IMP. False"
                create_entry_log(request.user, incident, None, message, request)

        # Notify only once the closure is committed: a failed save must not leave
        # regulators told about a closure that never happened.
        if incident_status == "CLOSE" and incident.sector_regulation and incident.sector_regulation.closing_email:
            send_email(incident.sector_regulation.closing_email, incident)

        for field_name in incident_form.cleaned_data:
            response[field_name] = incident_form.cleaned_data[field_name]

        return JsonResponse(response)

    return redirect("incidents")


@login_required
@otp_required
@check_user_is_correct
def access_log(request, incident_id: int):
    user = request.user
    company_id = request.session.get("company_in_use")
    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        messages.error(request, _("Incident not found"))
        return JsonResponse({"error": "Incident not found"}, status=404)

    if not can_access_incident(user, incident, company_id):
        messages.error(request, _("Forbidden"))
        return JsonResponse({"error": "Forbidden"}, status=403)

    is_regulator_incidents = request.session.get("is_regulator_incidents", False)

    is_regulator_incident = True if incident.regulator == user.regulators.first() and is_regulator_incidents else False

    log = LogReportRead.objects.filter(incident=incident).order_by("-timestamp")
    if is_user_operator(user) or user_in_group(user, "IncidentUser"):
        log = log.exclude(user__regulatoruser__isnull=False).exclude(user__observers__isnull=False)
    if is_regulator_incident:
        log = log.filter(user__regulatoruser__regulator=user.regulators.first())
    context = {
        "log": log,
        "incident": incident,
    }
    return render(request, "modals/access_log.html", context)


@login_required
@otp_required
@check_user_is_correct
def download_incident_pdf(request, incident_id: int):
    user = request.user
    company_id = request.session.get("company_in_use")

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        messages.error(request, _("Incident not found"))
        return redirect("incidents")

    if not can_access_incident(user, incident, company_id):
        messages.error(request, _("Forbidden"))
        return redirect("incidents")

    try:
        pdf_report = get_pdf_report(incident, None, request)
        create_entry_log(user, incident, None, "DOWNLOAD", request)
    except Exception:
        logger.error(
            "Error generating incident PDF report",
            extra={
                "incident_id": incident.id,
                "user_id": user.id,
                "company_id": company_id,
            },
            exc_info=True,
        )
        messages.error(request, _("An error occurred while generating the report."))
        return HttpResponseRedirect("/incidents")

    response = HttpResponse(pdf_report, content_type="application/pdf")

    latest_workflow = incident.get_latest_incident_workflow()
    timestamp = latest_workflow.timestamp if latest_workflow else incident.incident_notification_date
    filename = f"Incident_{incident.incident_id}_{timestamp:%Y-%m-%d}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@login_required
@otp_required
@check_user_is_correct
def download_incident_report_pdf(request, incident_workflow_id: int):
    user = request.user
    company_id = request.session.get("company_in_use")

    try:
        incident_workflow = IncidentWorkflow.objects.get(pk=incident_workflow_id)
        incident = incident_workflow.incident
    except IncidentWorkflow.DoesNotExist:
        messages.error(request, _("No incident report could be found."))
        return redirect("incidents")

    if not can_access_incident(user, incident, company_id):
        messages.error(request, _("Forbidden"))
        return redirect("incidents")
    try:
        pdf_report = get_pdf_report(incident, incident_workflow, request)
        create_entry_log(user, incident, incident_workflow, "DOWNLOAD", request)
    except Exception:
        logger.error(
            "Error generating incident PDF report",
            extra={
                "incident_id": incident.id,
                "incident_workflow_id": incident_workflow_id,
                "user_id": user.id,
                "company_id": company_id,
            },
            exc_info=True,
        )
        messages.error(request, _("An error occurred while generating the report."))
        return HttpResponseRedirect("/incidents")

    response = HttpResponse(pdf_report, content_type="application/pdf")

    timestamp = incident_workflow.timestamp
    report_name = incident_workflow.workflow.name
    filename = f"{incident.incident_id}_{report_name}_{timestamp:%Y-%m-%d}.pdf"

    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@login_required
@otp_required
@check_user_is_correct
@require_http_methods(["POST"])
def delete_incident(request, incident_id: int):
    user = request.user
    company_id = request.session.get("company_in_use")

    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        messages.error(request, _("Incident not found"))
        return redirect("incidents")

    if not can_create_incident_report(user, incident, company_id):
        messages.error(request, _("Forbidden"))
        return redirect("incidents")

    try:
        with transaction.atomic():
            # Lock the row for the whole check-then-delete. On PostgreSQL a concurrent
            # IncidentWorkflow insert must take FOR KEY SHARE on this parent row, which
            # conflicts with FOR UPDATE, so a report cannot slip in and be cascaded away.
            locked_incident = Incident.objects.select_for_update().get(pk=incident.pk)
            if locked_incident.workflows.exists():
                messages.error(request, _("The incident could not be deleted."))
            else:
                locked_incident.delete()
                messages.success(request, _("The incident has been deleted."))
    except Exception:
        logger.error(
            "Error deleting incident",
            extra={
                "incident_id": incident_id,
                "user_id": user.id,
                "company_id": company_id,
            },
            exc_info=True,
        )
        messages.error(request, _("An error occurred while deleting the incident."))
        return redirect("incidents")
    return redirect("incidents")


@login_required
@otp_required
@check_user_is_correct
def export_incidents(request):
    user = request.user

    if not can_export_incidents(user):
        messages.error(request, _("Forbidden"))
        return JsonResponse({"error": "Forbidden"}, status=403)

    regulation_ids = []
    sectorregulation_ids = []
    workflows_ids = []
    regulator = None
    observer = None

    if user_in_group(user, "RegulatorAdmin"):
        regulator = user.regulators.first()
        if regulator:
            sectorregulations = regulator.sectorregulation_set.all()
            regulation_ids = sectorregulations.values_list("regulation", flat=True).distinct()
            sectorregulation_ids = sectorregulations.values_list("id", flat=True).distinct()
            workflows_ids = sectorregulations.values_list("workflows", flat=True).distinct()

    elif is_observer_user(user):
        observer = user.observers.first()
        if observer:
            observer_regulations = observer.observerregulation_set.values_list("regulation", flat=True).distinct()
            regulation_ids = observer_regulations
            sectorregulations = SectorRegulation.objects.filter(regulation__in=observer_regulations)
            sectorregulation_ids = sectorregulations.values_list("id", flat=True).distinct()
            workflows_ids = sectorregulations.values_list("workflows", flat=True).distinct()

    regulation_qs = Regulation.objects.filter(id__in=regulation_ids).order_by("id")

    sectorregulation_qs = SectorRegulation.objects.filter(id__in=sectorregulation_ids).order_by("id")

    # A workflow can be reused by several sector regulations, so every id the user
    # may see is aggregated and the template exposes them all to the report filter.
    workflow_qs = (
        Workflow.objects.filter(id__in=workflows_ids)
        .annotate(
            sectorregulation_ids=ArrayAgg(
                "sectorregulation__id",
                filter=Q(sectorregulation__id__in=sectorregulation_ids),
                distinct=True,
            )
        )
        .order_by("id")
    )

    if request.method == "POST":
        form = ExportIncidentsForm(
            request.POST,
            regulation_qs=regulation_qs,
            sectorregulation_qs=sectorregulation_qs,
            workflow_qs=workflow_qs,
        )
        if form.is_valid():
            incidents = Incident.objects.none()
            regulation = form.cleaned_data["regulation"]
            sectorregulation = form.cleaned_data["sectorregulation"]
            workflow = form.cleaned_data["workflow"]
            from_date = form.cleaned_data["from_date"]
            to_date = form.cleaned_data["to_date"]
            file_format = form.cleaned_data["file_format"]
            are_incidents = False

            if user_in_group(user, "RegulatorAdmin"):
                incidents = (
                    Incident.objects.filter(
                        sector_regulation=sectorregulation,
                        sector_regulation__regulation=regulation,
                        sector_regulation__regulator__in=user.regulators.all(),
                        incident_notification_date__date__gte=from_date,
                        incident_notification_date__date__lte=to_date,
                    )
                    .prefetch_related(
                        "affected_sectors",
                        "incidentworkflow_set__answer_set__question_options__question",
                        "incidentworkflow_set__answer_set__predefined_answers",
                        "incidentworkflow_set__impacts__sectors",
                    )
                    .order_by("-incident_notification_date")
                )

                are_incidents = incidents.exists()

            if is_observer_user(user):
                all_incidents = get_observer_incidents(user.observers.first()).order_by("-incident_notification_date")

                incidents = [
                    i
                    for i in all_incidents
                    if i.sector_regulation.regulation == regulation
                    and i.sector_regulation == sectorregulation
                    and from_date <= i.incident_notification_date.date() <= to_date
                ]

                are_incidents = bool(incidents)

            if not are_incidents:
                messages.error(request, _("No incidents available for export."))
                rendered_messages = render_error_messages(request)
                return JsonResponse({"messages": rendered_messages}, status=400)

            data = []

            for incident in incidents:
                last_report = incident.get_latest_incident_workflow_by_workflow(workflow)

                if last_report is None:
                    continue

                incident_data = {
                    "Name of operator": (incident.company.name if incident.company else incident.company_name),
                    "Reference": incident.incident_id,
                    "Incident notification creation date": (
                        incident.incident_notification_date.strftime("%d-%m-%Y %H:%M:%S") if incident.incident_notification_date else ""
                    ),
                    "Incident detection date": (
                        last_report.report_timeline.incident_detection_date.strftime("%d-%m-%Y %H:%M:%S")
                        if last_report.report_timeline and last_report.report_timeline.incident_detection_date
                        else ""
                    ),
                    "Incident start date": (
                        last_report.report_timeline.incident_starting_date.strftime("%d-%m-%Y %H:%M:%S")
                        if last_report.report_timeline and last_report.report_timeline.incident_starting_date
                        else ""
                    ),
                    "Incident resolution date": (
                        last_report.report_timeline.incident_resolution_date.strftime("%d-%m-%Y %H:%M:%S")
                        if last_report.report_timeline and last_report.report_timeline.incident_resolution_date
                        else ""
                    ),
                    "Legal basis": str(incident.sector_regulation.regulation),
                    "Significative impact": ("yes" if incident.is_significative_impact else "no"),
                    "Incident Status": incident.get_incident_status_display(),
                    "Contact Information": ", ".join(
                        [
                            f"{incident.contact_firstname} {incident.contact_lastname}",
                            incident.contact_email,
                            incident.contact_telephone,
                        ]
                    ),
                    "Technical Contact Information": ", ".join(
                        [
                            f"{incident.technical_firstname} {incident.technical_lastname}",
                            incident.technical_email,
                            incident.technical_telephone,
                        ]
                    ),
                    "Report": (str(last_report.workflow) if last_report.workflow else ""),
                    "Report status": (last_report.get_review_status_display() if last_report.review_status else ""),
                    "Report creation date": (last_report.timestamp.strftime("%d-%m-%Y %H:%M:%S") if last_report.timestamp else ""),
                }

                length_fixed_values = len(incident_data)

                for idx, sector in enumerate(incident.affected_sectors.all(), start=1):
                    incident_data[f"Impacted sectors {idx}"] = str(sector).replace(" → ", " -> ")

                for answer in last_report.answer_set.all():
                    question = answer.question_options.question
                    str_answer = str(answer).replace(";", ",")
                    if answer.predefined_answers.exists():
                        for idx, pa in enumerate(answer.predefined_answers.all(), start=1):
                            pa_answer = str(pa).replace(";", ",")
                            if question.question_type == "SO":
                                incident_data[f"{question}"] = pa_answer
                            elif question.question_type == "ST":
                                if str_answer != "":
                                    incident_data[f"{question}"] = f"{pa_answer} Details: {str_answer}"
                                else:
                                    incident_data[f"{question}"] = pa_answer
                            else:
                                incident_data[f"{question} {idx}"] = pa_answer
                    elif question.question_type == "CL" or question.question_type == "RL":
                        for idx, item in enumerate(str_answer.split(","), start=1):
                            incident_data[f"{question} {idx}"] = item.strip()
                    else:
                        incident_data[f"{question}"] = str_answer

                lang = get_language() or "en"

                impacts = translated_queryset(
                    last_report.impacts,
                    lang,
                    PARLER_DEFAULT_LANGUAGE_CODE,
                    ["label"],
                    True,
                ).order_by("_label_sort")

                for idx, impact in enumerate(impacts, start=1):
                    for sector in impact.sectors.all():
                        incident_data[f"{sector.get_safe_translation()} Impact {idx}"] = impact.label

                data.append(incident_data)

            if not data:
                messages.error(request, _("No incidents available for export."))
                rendered_messages = render_error_messages(request)
                return JsonResponse({"messages": rendered_messages}, status=400)

            keys = []
            for entry in data:
                for k in entry.keys():
                    if k not in keys:
                        keys.append(k)

            keys = group_keys_by_index(keys, length_fixed_values)

            if file_format == "xlsx":
                wb = Workbook()
                ws = wb.active
                ws.title = "Incidents"

                headers = [sanitize_spreadsheet_cell(key) for key in keys]
                ws.append(headers)
                for entry in data:
                    row = [sanitize_spreadsheet_cell(entry.get(key, "")) for key in keys]
                    ws.append(row)

                for column_cells in ws.columns:
                    length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
                    ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 60)

                response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                response["Content-Disposition"] = 'attachment; filename="export.xlsx"'
                wb.save(response)

            else:
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="export.csv"'

                writer = csv.writer(
                    response,
                    quoting=csv.QUOTE_ALL,
                )
                writer.writerow([sanitize_spreadsheet_cell(key) for key in keys])
                for entry in data:
                    row = [sanitize_spreadsheet_cell(entry.get(key, "")) for key in keys]
                    writer.writerow(row)

            LogEntry.objects.log_actions(
                user_id=user.id,
                queryset=incidents,
                action_flag=7,
                change_message=_(
                    "A total of {count} incidents were exported from regulation "
                    "{regulation} [{sectorregulation} - ({workflow})] within date range ({from_date} - {to_date}.)"
                ).format(
                    count=len(data),
                    regulation=regulation,
                    sectorregulation=sectorregulation,
                    workflow=workflow,
                    from_date=from_date,
                    to_date=to_date,
                ),
            )

            try:
                platformAdmin_group = Group.objects.get(name="PlatformAdmin")
            except Group.DoesNotExist:
                platformAdmin_group = None

            if platformAdmin_group:
                email_list = User.objects.filter(groups=platformAdmin_group).values_list("email", flat=True)
                html_message = render_to_string_multi_languages(
                    "emails/incident_mass_export.html",
                    {"regulation": str(regulation), "site_name": SITE_NAME},
                )
                with translation.override(settings.LANGUAGE_CODE):
                    subject = _("[{site}] New incident mass export").format(site=SITE_NAME)

                send_html_email(
                    subject,
                    html_message,
                    email_list,
                )

            return response

    form = ExportIncidentsForm(
        regulation_qs=regulation_qs,
        sectorregulation_qs=sectorregulation_qs,
        workflow_qs=workflow_qs,
    )
    return render(request, "modals/export_incidents.html", {"form": form})


def group_keys_by_index(keys, length_fixed_values):
    fixed_keys = keys[:length_fixed_values]
    dynamic_keys = keys[length_fixed_values:]
    groups = OrderedDict()
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


def is_incidents_report_limit_reached(request):
    if request.user.is_authenticated:
        # if a user make too many declaration we prevent to save
        number_preliminary_today = Incident.objects.filter(contact_user=request.user, incident_notification_date__date=date.today()).count()
        if number_preliminary_today >= MAX_PRELIMINARY_NOTIFICATION_PER_DAY_PER_USER:
            messages.error(
                request,
                _("The daily limit of incident reports has been reached. Please try again tomorrow."),
            )
            return True
    return False


# if there are no sectors or detection date needed don't show  condition dict for wizard
def show_form_condition(wizard):
    regulations_data = wizard.storage.get_step_data("1")
    regulators_data = wizard.storage.get_step_data("2")

    if not regulations_data or not regulators_data:
        return {"has_sector": False, "detection_date_needed": False}

    regulations_ids = regulations_data.getlist("1-regulations", [])
    regulator_ids = regulators_data.getlist("2-regulators", [])

    if not regulations_ids or not regulator_ids:
        return {"has_sector": False, "detection_date_needed": False}

    sector_regulation_qs = SectorRegulation.objects.filter(Q(regulation_id__in=regulations_ids) & Q(regulator_id__in=regulator_ids))

    has_sector = sector_regulation_qs.filter(sectors__isnull=False).exists()
    detection_date_needed = sector_regulation_qs.filter(is_detection_date_needed=True).exists()

    return {"has_sector": has_sector, "detection_date_needed": detection_date_needed}


class FormWizardView(SessionWizardView):
    """Wizard to manage the preliminary form."""

    template_name = "incidents/declaration.html"

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        context["steps"] = [
            _("Contact"),
            _("Legal bases"),
            _("Regulators"),
            _("Sectors"),
            _("Detection date"),
        ]
        context["action"] = "Create"
        context["is_regulator_incidents"] = self.request.session.get("is_regulator_incidents", False)
        return context

    def render_goto_step(self, goto_step, **kwargs):
        form = self.get_form(self.steps.current, data=self.request.POST)

        if form.is_valid():
            current_data = form.cleaned_data
            storaged_data = self.get_cleaned_data_for_step(self.steps.current) or None

            if storaged_data and self.steps.current in ["1", "2"] and current_data != storaged_data:
                self.storage.set_step_data(goto_step, {})
                self.storage.set_step_data("3", {})

            self.storage.set_step_data(self.steps.current, self.process_step(form))

        elif int(self.steps.current) < int(goto_step):
            return self.render_revalidation_failure(self.steps.current, form)
        else:
            self.storage.set_step_data(self.steps.current, {})

        return super().render_goto_step(goto_step, **kwargs)

    def get_form_initial(self, step):
        def get_step_list(step_num, key):
            step_data = self.storage.get_step_data(step_num) or None
            if not step_data:
                return []

            return step_data.getlist(key, [])

        if step == "2":  # Regulators
            regulations = get_step_list("1", "1-regulations")
            return self.initial_dict.get(step, {"regulations": regulations})

        if step == "3":  # Sectors
            regulations = get_step_list("1", "1-regulations")
            regulators = get_step_list("2", "2-regulators")
            sectors = get_step_list("3", "3-sectors")

            return self.initial_dict.get(
                step,
                {
                    "regulations": regulations,
                    "regulators": regulators,
                    "sectors": sectors,
                },
            )

        return self.initial_dict.get(step, {})

    def done(self, form_list, **kwargs):
        if is_incidents_report_limit_reached(self.request):
            return HttpResponseRedirect("/incidents")

        user = self.request.user
        data = self.get_all_cleaned_data()
        company = get_active_company_from_session(self.request) if not is_user_regulator(user) else None
        regulator = user.regulators.first() if is_user_regulator(user) else None
        sectors_id = extract_ids(data.get("sectors", []))
        regulators_id = extract_ids(data.get("regulators", []))
        regulations_id = extract_ids(data.get("regulations", []))
        company_name = f"{data.get('company_name')} ({_('Not verified')})"
        if company or regulator:
            company_name = company.name if company else str(regulator)

        sectors_filter = Q(sectors__in=sectors_id) if sectors_id else Q(sectors__isnull=True)

        sector_regulations = (
            SectorRegulation.objects.filter(
                sectors_filter,
                regulator__in=regulators_id,
                regulation__in=regulations_id,
                workflows__isnull=False,
                active=True,
            )
            .order_by()
            .distinct()
        )

        if not sector_regulations.exists():
            messages.error(self.request, _("No incident notification workflow found for the selected criteria."))
            return redirect("incidents")

        incident_timezone = data.get("incident_timezone", TIME_ZONE)
        incident_detection_date = data.get("detection_date", None)

        if incident_detection_date:
            local_tz = pytz.timezone(incident_timezone)
            local_dt = local_tz.localize(incident_detection_date.replace(tzinfo=None))
            incident_detection_date = local_dt.astimezone(pytz.utc)

        for sector_regulation in sector_regulations:
            opening_email_to_send = None
            with transaction.atomic():
                incident = Incident.objects.create(
                    contact_lastname=data.get("contact_lastname"),
                    contact_firstname=data.get("contact_firstname"),
                    contact_title=data.get("contact_title"),
                    contact_email=data.get("contact_email"),
                    contact_telephone=data.get("contact_telephone"),
                    # technical contact
                    technical_lastname=data.get("technical_lastname"),
                    technical_firstname=data.get("technical_firstname"),
                    technical_title=data.get("technical_title"),
                    technical_email=data.get("technical_email"),
                    technical_telephone=data.get("technical_telephone"),
                    incident_reference=data.get("incident_reference"),
                    complaint_reference=data.get("complaint_reference"),
                    contact_user=user,
                    company=company,
                    regulator=regulator,
                    company_name=company_name,
                    sector_regulation=sector_regulation,
                    incident_timezone=data.get("incident_timezone", TIME_ZONE),
                    incident_detection_date=incident_detection_date,
                )
                if incident:
                    # Detect if a regulator is submitting the incident
                    is_regulator_incidents = self.request.session.get("is_regulator_incidents", False)

                    self.is_regulator_incident = True if regulator and is_regulator_incidents else False
                    # check if the detection date is over
                    if sector_regulation.is_detection_date_needed:
                        sr_workflow = (
                            SectorRegulationWorkflow.objects.all()
                            .filter(
                                sector_regulation=sector_regulation,
                            )
                            .order_by("position")
                            .first()
                        )
                        # TO DO get the correct detection date
                        if sr_workflow.trigger_event_before_deadline == "DETECT_DATE":
                            dt = timezone.now() - incident.incident_detection_date
                            if round(dt.total_seconds() / 60 / 60, 0) > sr_workflow.delay_in_hours_before_deadline:
                                sr_workflow.review_status = "OUT"
                                sr_workflow.save()

                    sec = sector_regulation.sectors.values_list("id", flat=True)
                    selected_sectors = Sector.objects.filter(id__in=sectors_id).values_list("id", flat=True)
                    affected_sectors = selected_sectors & sec
                    incident.affected_sectors.set(affected_sectors)
                    # incident reference

                    company_for_ref = company.identifier if company else data.get("company_name", "")[:10]
                    sector_for_ref = ""
                    subsector_for_ref = ""

                    for sector in sector_regulation.sectors.all():
                        if sector.id in sectors_id:
                            if subsector_for_ref == "":
                                subsector_for_ref = sector.acronym[:3]
                                if sector.parent:
                                    sector_for_ref = sector.parent.acronym[:3]

                    incidents_per_company = (
                        company.incident_set.filter(incident_notification_date__year=date.today().year).count() if company else 1
                    )
                    if self.is_regulator_incident:
                        incidents_per_company = (
                            regulator.incident_set.filter(incident_notification_date__year=date.today().year).count() if regulator else 1
                        )

                    number_of_incident = f"{incidents_per_company:04}"
                    incident.incident_id = (
                        f"{company_for_ref}_{sector_for_ref}_{subsector_for_ref}_{number_of_incident}_{date.today().year}"
                    )

                    incident.save()

                    create_entry_log(user, incident, None, "CREATE", self.request)

                    # capture email to send after the atomic block
                    if sector_regulation.opening_email is not None:
                        opening_email_to_send = sector_regulation.opening_email

            # send The email notification opening — outside the atomic block
            if opening_email_to_send is not None:
                send_email(
                    opening_email_to_send,
                    incident,
                    send_to_observers=True,
                )

        if sector_regulations.count() > 1:
            return redirect("regulator_incidents") if self.is_regulator_incident else redirect("incidents")

        sr_workflow = SectorRegulationWorkflow.objects.filter(sector_regulation=sector_regulation).order_by("position").first()

        if not sr_workflow or not sr_workflow.workflow:
            return redirect("incidents")

        query_params = urlencode(
            {
                "incident_id": incident.id,
                "workflow_id": sr_workflow.workflow.id,
            }
        )

        url = f"{reverse('create_workflow')}?{query_params}"
        return redirect(url)


class WorkflowWizardView(SessionWizardView):
    """Wizard to manage the different workflows."""

    template_name = "incidents/declaration.html"
    incident = None
    workflow = None
    incident_workflow = None
    read_only = False

    def __init__(self, read_only=False, **kwargs):
        self.form_list = kwargs.pop("form_list")
        self.read_only = read_only
        super().__init__(**kwargs)

    def get_form_kwargs(self, step=None):
        user = self.request.user
        if step is None:
            step = self.steps.current
        kwargs = super().get_form_kwargs(step)

        position = int(step)
        is_regulator_incidents = self.request.session.get("is_regulator_incidents", False)

        if self.request.incident_workflow:
            self.incident_workflow = IncidentWorkflow.objects.get(pk=self.request.incident_workflow)
            self.incident = self.incident_workflow.incident
            self.workflow = self.incident_workflow.workflow
            self.is_regulator_incident = True if self.incident.regulator == user.regulators.first() and is_regulator_incidents else False
            sector_regulation = self.incident.sector_regulation
            regulation_sector_has_impacts = (
                sector_regulation is not None
                and Impact.objects.filter(
                    regulations=sector_regulation.regulation,
                    sectors__in=self.incident.affected_sectors.all(),
                ).exists()
            )

            self.workflow.is_impact_needed = bool(self.workflow.is_impact_needed and regulation_sector_has_impacts)

            is_new_incident_workflow = not self.read_only and (is_user_regulator(user) == self.is_regulator_incident)

            self.categories_workflow = get_workflow_categories(
                self.workflow,
                self.incident_workflow,
                is_new_incident_workflow,
            )

            if position == 0:
                kwargs.update(
                    {
                        "instance": self.incident_workflow.report_timeline,
                        "incident": self.incident,
                    }
                )
            # Regulator case
            elif (
                position == len(self.form_list) - 2
                and self.workflow.is_impact_needed
                and is_user_regulator(user)
                and not self.is_regulator_incident
            ):
                kwargs.update({"incident": self.incident})
            elif position == len(self.form_list) - 1 and is_user_regulator(user) and not self.is_regulator_incident:
                kwargs.update({"instance": self.incident_workflow})
            # Operator case
            elif (
                position == len(self.form_list) - 1
                and self.workflow.is_impact_needed
                and (not is_user_regulator(user) or self.is_regulator_incident)
            ):
                kwargs.update({"incident": self.incident})
            else:
                # regulator pass directly the incident_workflow
                kwargs.update(
                    {
                        "position": position - 1,
                        "incident_workflow": self.incident_workflow,
                        "categories_workflow": self.categories_workflow,
                        "is_new_incident_workflow": not self.read_only and (is_user_regulator(user) == self.is_regulator_incident),
                    }
                )
        elif self.request.incident:
            self.incident = Incident.objects.get(pk=self.request.incident)
            self.is_regulator_incident = True if self.incident.regulator == user.regulators.first() and is_regulator_incidents else False

            if not self.request.workflow:
                self.workflow = self.incident.get_next_step()
            else:
                self.workflow = self.request.workflow

            sector_regulation = self.incident.sector_regulation
            regulation_sector_has_impacts = (
                sector_regulation is not None
                and Impact.objects.filter(
                    regulations=sector_regulation.regulation,
                    sectors__in=self.incident.affected_sectors.all(),
                ).exists()
            )

            self.workflow.is_impact_needed = bool(self.workflow.is_impact_needed and regulation_sector_has_impacts)

            is_new_incident_workflow = not self.read_only and (is_user_regulator(user) == self.is_regulator_incident)

            self.categories_workflow = get_workflow_categories(
                self.workflow,
                self.incident_workflow,
                is_new_incident_workflow,
            )
            if position == 0:
                kwargs.update({"incident": self.incident})
            elif position == len(self.form_list) - 1 and self.workflow.is_impact_needed:
                kwargs.update({"incident": self.incident})
            else:
                kwargs.update(
                    {
                        "position": position - 1,
                        "workflow": self.workflow,
                        "incident": self.incident,
                        "categories_workflow": self.categories_workflow,
                        "is_new_incident_workflow": not self.read_only and (is_user_regulator(user) == self.is_regulator_incident),
                    }
                )

        return kwargs

    def get(self, request, *args, **kwargs):
        incident_workflow_id = request.GET.get("incident_workflow_id", None)
        if incident_workflow_id:
            company_id = request.session.get("company_in_use")
            user = request.user
            incident_workflow = IncidentWorkflow.objects.get(pk=incident_workflow_id)
            incident = incident_workflow.incident

            if incident_workflow and can_access_incident(user, incident, company_id):
                create_entry_log(user, incident_workflow.incident, incident_workflow, "READ", request)

        return super().get(self, request, *args, **kwargs)

    def get_form(self, step=None, data=None, files=None):
        if step is None:
            step = self.steps.current
        position = int(step)
        user = self.request.user
        self.is_review = False

        # Operator : Complete an existing workflow or see historic
        # Regulator : See the report
        form = super().get_form(step=step, data=data, files=files)

        if self.incident:
            form.incident = self.incident

        # Read only for regulator except for last form (save comment)
        # Read only for operator review (read_only = True)
        if self.read_only:
            last_form_index = -1
        else:
            last_form_index = len(self.form_list) - 1
        if (is_user_regulator(user) and position != last_form_index) and not self.is_regulator_incident or self.read_only:
            self.is_review = True
            for field in form.fields:
                form.fields[field].disabled = True
                form.fields[field].required = False

                # replace following widget by more readable in read only
                if form.fields[field].widget.__class__.__name__ == "DropdownCheckboxSelectMultiple":
                    COUNTRY_DICT = dict(countries)
                    REGIONAL_DICT = dict(REGIONAL_AREA)
                    initial = " - ".join(
                        map(
                            lambda val: str(COUNTRY_DICT.get(val, REGIONAL_DICT.get(val, val))),
                            form.fields[field].initial,
                        )
                    )

                    new_field = forms.CharField(
                        required=False,
                        disabled=True,
                        label=form.fields[field].label,
                        initial=initial,
                        widget=forms.TextInput(attrs=form.fields[field].widget.attrs),
                    )
                    new_field.is_conditional = form.fields[field].is_conditional
                    form.fields[field] = new_field

        else:
            for field_name in form.fields:
                field = form.fields[field_name]
                widget_classes = field.widget.attrs.get("class", "")
                if "answer-modified" in widget_classes:
                    field.widget.attrs["class"] = widget_classes.replace("answer-modified", "").strip()

        return form

    def get_context_data(self, form, **kwargs):
        user = self.request.user
        context = super().get_context_data(form=form, **kwargs)
        raw_date = self.storage.extra_data.get("autosave_comment_date")
        context["autosave_comment_date"] = parse_datetime(raw_date) if raw_date else None

        if self.workflow is not None:
            context["action"] = "Edit" if self.read_only or (is_user_regulator(user) and not self.is_regulator_incident) else "Create"
            context["is_regulator_incident"] = self.is_regulator_incident
            context["steps"] = []
            context["steps"].append(_("Incident Timeline"))
            context["steps"].extend(self.categories_workflow)
            if self.workflow.is_impact_needed:
                sector_regulation = self.incident.sector_regulation
                regulation_sector_has_impacts = (
                    sector_regulation is not None
                    and Impact.objects.filter(
                        regulations=sector_regulation.regulation,
                        sectors__in=self.incident.affected_sectors.all(),
                    ).exists()
                )
                if regulation_sector_has_impacts:
                    context["steps"].append(_("Impacts"))

            user = self.request.user
            if is_user_regulator(user) and not self.is_regulator_incident:
                context["steps"].append(_("Comment/Explanation"))

            # Flag every step whose form holds a changed answer so the wizard
            # nav highlights them. Only relevant where the "answer-modified"
            # markers are kept (regulator review / read-only); operators have
            # them stripped in get_form, so skip the extra form builds for them.
            context["modified_steps"] = []
            if self.read_only or (is_user_regulator(user) and not self.is_regulator_incident):
                saved_is_review = getattr(self, "is_review", False)
                current_step = self.steps.current
                for step in self.steps.all:
                    step_form = form if step == current_step else self.get_form(step)
                    if any("answer-modified" in field.widget.attrs.get("class", "") for field in step_form.fields.values()):
                        context["modified_steps"].append(step)
                self.is_review = saved_is_review
        return context

    def render_goto_step(self, goto_step, **kwargs):
        current_step = self.steps.current
        form = self.get_form(current_step, data=self.request.POST, files=self.request.FILES)

        if int(current_step) < int(goto_step) and not form.is_valid():
            # If the form is not valid, we don't allow to go to the next step
            return self.render_revalidation_failure(current_step, form)

        self.storage.set_step_data(current_step, self.process_step(form))
        self.storage.set_step_files(current_step, self.process_step_files(form))

        # If the user is in review mode and is going to the last step,
        # we ensure that all previous steps are stored, this avoid render validation.
        if self.is_review and not self.read_only and goto_step == self.steps.last:
            for step in self.steps.all:
                if step == goto_step or self.storage.get_step_data(step):
                    continue
                form = self.get_form(step)
                self.storage.set_step_data(step, self.process_step(form))

        # Temporarily store the regulator's comment until the form is submitted
        if not self.read_only and isinstance(form, RegulatorIncidentWorkflowCommentForm):
            autosave_date = timezone.now()
            self.storage.set_step_data(current_step, self.process_step(form))
            self.storage.extra_data["autosave_comment_date"] = autosave_date.isoformat()

        return super().render_goto_step(goto_step, **kwargs)

    def done(self, form_list, **kwargs):
        user = self.request.user
        data = self.get_all_cleaned_data()
        if (not is_user_regulator(user) or self.is_regulator_incident) and not self.read_only:
            incident_timezone = data.get("incident_timezone", TIME_ZONE)
            incident_starting_date = data.get("incident_starting_date", None)
            incident_detection_date = data.get("incident_detection_date", None)
            incident_resolution_date = data.get("incident_resolution_date", None)
            local_tz = pytz.timezone(incident_timezone)
            email = self.workflow.submission_email or None
            self.incident = self.incident or get_object_or_404(Incident, pk=self.request.incident)
            self.incident.review_status = "DELIV"
            self.incident.incident_timezone = incident_timezone

            if incident_starting_date:
                incident_starting_date = convert_to_utc(incident_starting_date, local_tz)

            if incident_detection_date and not (
                self.incident.sector_regulation and self.incident.sector_regulation.is_detection_date_needed
            ):
                self.incident.incident_detection_date = convert_to_utc(incident_detection_date, local_tz)

            if incident_resolution_date:
                incident_resolution_date = convert_to_utc(incident_resolution_date, local_tz)

            self.incident.save()
            # create the report timeline
            report_timeline = ReportTimeline.objects.create(
                report_timeline_timezone=incident_timezone,
                incident_starting_date=incident_starting_date,
                incident_detection_date=self.incident.incident_detection_date,
                incident_resolution_date=incident_resolution_date,
            )
            # manage question
            incident_workflow = save_answers(data, self.incident, self.workflow, report_timeline)
            create_entry_log(user, self.incident, incident_workflow, "CREATE", self.request)

            if email and not self.incident.incident_status == "CLOSE":
                send_email(email, self.incident, send_to_observers=True)
        # save the comment if the user is regulator
        elif is_user_regulator(user) and not self.read_only:
            incident_workflow = (
                IncidentWorkflow.objects.all().filter(incident=self.incident, workflow=self.workflow).order_by("-timestamp").first()
            )
            incident_workflow.comment = data.get("comment", None)
            review_status = data.get("review_status", None)
            if incident_workflow.review_status != review_status:
                if (
                    incident_workflow.incident.sector_regulation.report_status_changed_email
                    and not incident_workflow.incident.incident_status == "CLOSE"
                ):
                    send_email(
                        incident_workflow.incident.sector_regulation.report_status_changed_email,
                        incident_workflow.incident,
                    )
            if review_status is not None:
                incident_workflow.review_status = review_status
                with override(PARLER_DEFAULT_LANGUAGE_CODE):
                    status_label = dict(WORKFLOW_REVIEW_STATUS).get(review_status, "")
                    create_entry_log(
                        user,
                        self.incident,
                        incident_workflow,
                        f"REVIEW STATUS: {status_label}",
                        self.request,
                    )
            incident_workflow.save()
            create_entry_log(
                user,
                incident_workflow.incident,
                incident_workflow,
                "COMMENT",
                self.request,
            )

        return redirect("regulator_incidents") if self.is_regulator_incident else redirect("incidents")


def save_answers(data=None, incident=None, workflow=None, report_timeline=None):
    """Save the answers."""
    prefix = "__question__"
    questions_data = {key[slice(len(prefix), None)]: value for key, value in data.items() if key.startswith(prefix)}

    # We create a new incident workflow in all the case (history)
    incident_workflow = IncidentWorkflow.objects.create(incident=incident, workflow=workflow, report_timeline=report_timeline)
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
            question_option = question_options_map.get(question_id)
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

    return incident_workflow


def can_redirect(url: str) -> bool:
    """
    Check if a redirect is authorised.
    """
    o = urlparse(url)
    return o.netloc in PUBLIC_URL


def extract_ids(data: list) -> list:
    return [int(item) for item in data if item.isdigit()]


def convert_to_utc(date, local_tz):
    if date:
        local_dt = local_tz.localize(date.replace(tzinfo=None))
        return local_dt.astimezone(pytz.utc)
    return None


def create_entry_log(user, incident, incident_report, action, request=None):
    role = user.groups.first().name if user.groups.exists() else ""
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


def can_export_incidents(user):
    regulator = user.regulators.first()
    observer = user.observers.first()
    return (
        regulator
        and user.regulatoruser_set.filter(
            regulator=regulator,
            is_regulator_administrator=True,
            can_export_incidents=True,
        ).exists()
    ) or (observer and user.observeruser_set.filter(observer=observer, can_export_incidents=True).exists())


def render_error_messages(request):
    return render_to_string(
        "django_bootstrap5/messages.html",
        {"messages": messages.get_messages(request)},
        request=request,
    )
