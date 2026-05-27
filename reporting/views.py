import os
import tempfile
import uuid
from urllib.parse import quote as urlquote

import redis
from celery import chain, chord, current_app, group
from celery.exceptions import CeleryError
from celery.result import GroupResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django.views.decorators.http import require_http_methods
from django_otp.decorators import otp_required

from governanceplatform.helpers import (
    get_sectors_grouped,
    is_user_regulator,
    sort_queryset_by_field,
    user_in_group,
)
from governanceplatform.models import Company, Regulation, Sector
from securityobjectives.models import Standard, StandardAnswer

from .filters import CompanyProjectFilter, ProjectFilter, RecommendationFilter
from .forms import (
    CompanyProjectDashboard,
    CreateProjectForm,
    ImportRiskAnalysisForm,
    ObservationRecommendationOrderForm,
    RecommendationsSelectFormSet,
    ReviewCommentForm,
)
from .globals import (
    ALLOWED_DASHBOARD_SORT_FIELDS,
    ALLOWED_PROJECT_DASHBOARD_SORT_FIELDS,
    CELERY_TASK_STATUS,
)
from .helpers import create_entry_log
from .import_risk_analysis import validate_json_file
from .models import (
    CompanyProject,
    CompanyReporting,
    GeneratedReport,
    LogReporting,
    Observation,
    ObservationRecommendation,
    ObservationRecommendationThrough,
    Project,
    Template,
)
from .tasks import (
    cleanup_files,
    cleanup_ra_tmp_file_task,
    delete_project_task,
    generate_data,
    generate_docx_task,
    generate_pdf_task,
    import_risk_analysis_task,
    on_chord_error,
    save_file_task,
    zip_files_task,
)


def has_change_permission(request, project, action):
    def check_conditions():
        user = request.user
        user_sectors = user.get_sectors().all()

        project_sectors = project.sectors.all()
        is_user_regulator_sector = (
            user_in_group(user, "RegulatorAdmin") and project.author.regulators.first() == user.regulators.first()
        ) or (
            is_user_regulator(user)
            and project.author.regulators.first() == user.regulators.first()
            and any(sector in project_sectors for sector in user_sectors)
        )

        match action:
            case "delete":
                return is_user_regulator_sector
            case "copy":
                return is_user_regulator_sector
            case "edit":
                return is_user_regulator_sector
            case "log":
                return is_user_regulator_sector
            case "download":
                return is_user_regulator_sector
            case _:
                return False

    if not check_conditions():
        messages.error(request, _("Forbidden"))
        return False
    return True


@login_required
@otp_required
def reporting(request):
    user = request.user
    if user_in_group(user, "RegulatorAdmin"):
        project_queryset = Project.objects.filter(author__regulators=user.regulators.first()).order_by("-updated_at")
    elif user_in_group(user, "RegulatorUser"):
        project_queryset = (
            Project.objects.filter(
                sectors__in=user.get_sectors().all(),
                author__regulators=user.regulators.first(),
            )
            .order_by("-updated_at")
            .distinct()
        )
    else:
        project_queryset = Project.objects.none()

    search_value = request.GET.get("search", None)

    if "reset_sort" in request.GET:
        request.session.pop("reporting_sort_params", None)
        return redirect("reporting")

    if "reset" in request.GET or search_value == "":
        request.session.pop("reporting_filter_params", None)
        return redirect("reporting")

    current_params = request.session.get("reporting_filter_params", {}).copy()
    current_sort_params = request.session.get("reporting_sort_params", {}).copy()

    for key, values in request.GET.lists():
        current_params[key] = values if key == "sectors" else values[0]

    for key, value in request.GET.items():
        if key in ("sort_field", "sort_direction"):
            current_sort_params[key] = value

    reporting_filter_params = current_params
    reporting_sort_params = current_sort_params
    request.session["reporting_filter_params"] = reporting_filter_params
    request.session["reporting_sort_params"] = reporting_sort_params

    # Apply sorting
    sort_field = reporting_sort_params.get("sort_field", "updated_at")
    sort_direction = reporting_sort_params.get("sort_direction", "desc")

    project_queryset = sort_queryset_by_field(
        project_queryset,
        sort_field,
        sort_direction,
        "updated_at",
        ALLOWED_DASHBOARD_SORT_FIELDS,
    )

    project_filter = ProjectFilter(reporting_filter_params, queryset=project_queryset)

    project_filter_list = project_filter.qs

    per_page = reporting_filter_params.get("per_page", 10)
    page_number = reporting_filter_params.get("page")
    paginator = Paginator(project_filter_list, per_page)
    page_obj = paginator.get_page(page_number)
    projects_running = list(project_filter_list.filter(task_status=CELERY_TASK_STATUS[3][0]).values("id"))

    is_filtered = {k: v for k, v in reporting_filter_params.items() if k not in ["page", "per_page", "sort_field", "sort_direction"]}

    context = {
        "filter": project_filter,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "is_filtered": bool(is_filtered),
        "projects": page_obj,
        "projects_running": projects_running,
    }

    return render(request, "reporting/dashboard.html", context)


@login_required
@otp_required
def dashboard_report_project(request, report_project_id: int):
    project = get_object_or_404(Project, pk=report_project_id)
    if not has_change_permission(request, project, "edit"):
        return redirect("reporting")

    company_project_qs = project.companyproject_set.all()

    search_value = request.GET.get("search", None)

    if "reset_sort" in request.GET:
        request.session.pop("dashboard_project_sort_params", None)
        return redirect("dashboard_report_project", report_project_id=project.id)

    if "reset" in request.GET or search_value == "":
        request.session.pop("dashboard_project_filter_params", None)
        return redirect("dashboard_report_project", report_project_id=project.id)

    current_params = request.session.get("dashboard_project_filter_params", {}).copy()
    current_sort_params = request.session.get("dashboard_project_sort_params", {}).copy()

    for key, values in request.GET.lists():
        current_params[key] = values if key in ["sector", "year"] else values[0]

    for key, value in request.GET.items():
        if key in ("sort_field", "sort_direction"):
            current_sort_params[key] = value

    dashboard_project_filter_params = current_params
    dashboard_project_sort_params = current_sort_params
    request.session["dashboard_project_filter_params"] = dashboard_project_filter_params
    request.session["dashboard_project_sort_params"] = dashboard_project_sort_params

    # Apply sorting
    sort_field = dashboard_project_sort_params.get("sort_field", "company")
    sort_direction = dashboard_project_sort_params.get("sort_direction", "desc")

    company_project_qs = sort_queryset_by_field(
        company_project_qs,
        sort_field,
        sort_direction,
        "company",
        ALLOWED_PROJECT_DASHBOARD_SORT_FIELDS,
    )

    company_project_filter = CompanyProjectFilter(dashboard_project_filter_params, queryset=company_project_qs, project=project)

    company_project_filter_list = company_project_filter.qs

    input_select_fields = [
        "is_selected",
        "statistic_selected",
        "governance_report_selected",
    ]

    selected_status = {field: not company_project_filter_list.filter(**{field: False}).exists() for field in input_select_fields}

    per_page = dashboard_project_filter_params.get("per_page", 10)
    page_number = dashboard_project_filter_params.get("page")
    paginator = Paginator(company_project_filter_list, per_page)
    page_obj = paginator.get_page(page_number)

    for company_project in page_obj.object_list:
        company_project.formSelect = CompanyProjectDashboard(instance=company_project)

    is_filtered = {
        k: v for k, v in dashboard_project_filter_params.items() if k not in ["page", "per_page", "sort_field", "sort_direction"]
    }

    context = {
        "filter": company_project_filter,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "is_filtered": bool(is_filtered),
        "selected_status": selected_status,
        "project": project,
        "items": page_obj,
    }

    return render(request, "reporting/project_dashboard.html", context)


@login_required
@otp_required
def create_report_project(request):
    user = request.user
    regulator = user.regulators.first()

    regulation_qs = Regulation.objects.filter(regulators=regulator, standard__isnull=False).distinct()

    standard_qs = Standard.objects.filter(regulator=regulator, regulation__in=regulation_qs)

    sectors_queryset = user.get_sectors().all() if user_in_group(user, "RegulatorUser") else Sector.objects.all()

    sector_list = get_sectors_grouped(sectors_queryset)

    choices = {
        "regulations": regulation_qs,
        "sectors": sector_list,
        "standards": standard_qs,
    }

    if request.method == "POST":
        form = CreateProjectForm(
            request.POST,
            choices=choices,
        )

        if form.is_valid():
            user = request.user
            data = form.cleaned_data
            project = Project.objects.create(
                author=user,
                name=data["name"],
                standard=data["standard"],
                years=data["years"],
                reference_year=data["reference_year"],
                top_ranking=data["top_ranking"],
                selected_file_format=data["selected_file_format"],
                selected_languages=data["selected_languages"],
                threshold_for_high_risk=data["threshold_for_high_risk"],
            )
            if project and data["sectors"]:
                project.sectors.set(data["sectors"])

            create_entry_log(user, project, "CREATE PROJECT")
        return redirect("reporting")

    form = CreateProjectForm(choices=choices)
    context = {"form": form}
    return render(request, "modals/create_report_project.html", context=context)


@login_required
@otp_required
def edit_report_project(request, report_project_id: int):
    project = get_object_or_404(Project, pk=report_project_id)
    if not has_change_permission(request, project, "edit"):
        return redirect("reporting")

    user = request.user
    regulator = user.regulators.first()

    regulation_qs = Regulation.objects.filter(regulators=regulator, standard__isnull=False).distinct()

    standard_qs = Standard.objects.filter(regulator=regulator, regulation__in=regulation_qs)

    sectors_queryset = user.get_sectors().all() if user_in_group(user, "RegulatorUser") else Sector.objects.all()

    sector_list = get_sectors_grouped(sectors_queryset)

    choices = {
        "regulations": regulation_qs,
        "sectors": sector_list,
        "standards": standard_qs,
    }

    if request.method == "POST":
        form = CreateProjectForm(
            request.POST,
            instance=project,
            choices=choices,
        )
        if form.is_valid():
            form.save()
            create_entry_log(user, project, "EDIT PROJECT")
            return HttpResponseRedirect(request.headers.get("referer"))
    else:
        form = CreateProjectForm(instance=project, choices=choices)

    context = {"form": form, "is_edit": True}
    return render(request, "modals/create_report_project.html", context=context)


@login_required
@otp_required
def copy_report_project(request, report_project_id):
    project = get_object_or_404(Project, pk=report_project_id)
    if not has_change_permission(request, project, "copy"):
        return redirect("reporting")

    user = request.user

    if request.method == "POST":
        form = CreateProjectForm(request.POST, instance=project, is_copy=True)

        if form.is_valid():
            new_project = form.save(commit=False)
            new_project.pk = None
            new_project.task_id = None
            new_project.task_status = Project._meta.get_field("task_status").get_default()
            new_project.save()
            form.save_m2m()
            create_entry_log(user, project, "CREATE PROJECT")
        return redirect("reporting")

    form = CreateProjectForm(instance=project, is_copy=True)
    context = {"form": form, "is_copy": True}
    return render(request, "modals/create_report_project.html", context)


@login_required
@otp_required
@require_http_methods(["POST"])
def delete_report_project(request, report_project_id: int):
    try:
        project = Project.objects.get(pk=report_project_id)
        if not has_change_permission(request, project, "delete"):
            return redirect("reporting")

        if project.task_status == CELERY_TASK_STATUS[3][0]:
            messages.warning(
                request,
                _("Report generation is in progress for this project. Please cancel the report generation before deleting the project."),
            )
            return redirect("reporting")

        chain(
            cleanup_files.si(
                project_id=str(report_project_id),
                task_id=str(project.task_id) if project.task_id else None,
                all_files=True,
            ),
            delete_project_task.si(str(project.id)),
        ).apply_async()

        messages.success(request, _("The project has been deleted."))

    except Project.DoesNotExist:
        messages.error(request, _("Project not found"))
    return redirect("reporting")


@login_required
@otp_required
@require_http_methods(["POST"])
def generate_report_project(request, report_project_id: int):
    user = request.user
    try:
        project = Project.objects.get(id=report_project_id)
    except Project.DoesNotExist:
        messages.error(
            request,
            _("No project found"),
        )
        return redirect("reporting")

    if not reporting_health_check():
        project.task_status = CELERY_TASK_STATUS[0][0]
        messages.error(request, _("Failed to start report generation. Please try again."))
        return redirect("dashboard_report_project", report_project_id=project.id)

    if project.task_status == CELERY_TASK_STATUS[3][0]:
        messages.warning(
            request,
            _("Report generation is already in progress for this project."),
        )
        return redirect("dashboard_report_project", report_project_id=project.id)

    if not project.threshold_for_high_risk or not project.top_ranking:
        error_message = _("Missing high risk rate threshold or ranking value")
        messages.error(
            request,
            error_message,
        )
        return redirect("dashboard_report_project", report_project_id=project.id)

    project_id = project.id
    year = project.reference_year
    selected_companies_project = project.companyproject_set.filter(is_selected=True)

    if not selected_companies_project:
        error_message = _("Nothing selected")
        messages.error(
            request,
            error_message,
        )
        return redirect("dashboard_report_project", report_project_id=project.id)

    threshold_for_high_risk = project.threshold_for_high_risk
    top_ranking = project.top_ranking
    languages = project.selected_languages
    extention = project.selected_file_format
    user_sectors = user.get_sectors().all()

    selected_companies = [
        {
            "company": obj.company,
            "sector": obj.sector,
            "years": selected_companies_project.filter(company=obj.company).values_list("year", flat=True),
        }
        for obj in selected_companies_project.distinct("company", "sector")
    ]

    is_multiple_selected_companies = len(selected_companies) > 1 or len(languages) > 1
    error_messages = []
    errors = 0
    report_generation_tasks = []
    task_id = uuid.uuid4()

    for select_company in selected_companies:
        company = select_company.get("company")
        sector = select_company.get("sector")
        years = select_company.get("years")
        if sector not in user_sectors:
            if is_multiple_selected_companies:
                error_message = _("%(sector)s forbidden") % {"sector": sector}
                error_messages.append(error_message)
                continue
            messages.error(request, _("Forbidden"))
            return redirect("reporting")

        try:
            company_reporting = CompanyReporting.objects.get(company=company, year=year, sector=sector)
        except CompanyReporting.DoesNotExist:
            if is_multiple_selected_companies:
                error_message = f"[{company}][{sector}][{year}]: Missing risk analysis and security objectives data"
                error_messages.append(error_message)
                continue

            messages.error(
                request,
                _("No reporting data"),
            )
            return redirect("dashboard_report_project", report_project_id=project.id)

        security_objectives_declaration = StandardAnswer.objects.filter(
            submitter_company=company,
            sectors=sector,
            year_of_submission=year,
            status="PASSM",
        ).order_by("submit_date")

        risk_analysis_stats = company.risk_analysis_exists(year, sector)

        if not security_objectives_declaration:
            if is_multiple_selected_companies:
                error_message = f"[{company}][{sector}][{year}]: No security objective data found"
                error_messages.append(error_message)
                continue

            errors += 1
            messages.error(
                request,
                _("No data found for security objectives report"),
            )

        if not risk_analysis_stats:
            if is_multiple_selected_companies:
                error_message = f"[{company}][{sector}][{year}]: No risk data found"
                error_messages.append(error_message)
                continue

            errors += 1
            messages.error(
                request,
                _("No data found for risk report"),
            )

        if errors > 0:
            return redirect("reporting")

        report_recommendations = company.get_report_recommandations(year, sector)
        years_to_compare = [y for y in years if y <= year]
        years_list = sorted(set(years_to_compare + [year]))

        base_data = {
            "company": model_to_dict(company, exclude=["phone_number", "entity_categories", "sectors"]),
            "reference_year": year,
            "threshold_for_high_risk": threshold_for_high_risk,
            "top_ranking": top_ranking,
            "years": years_list,
            "report_recommendations": [rec.observation_recommendation.description for rec in report_recommendations],
            "company_reporting": model_to_dict(company_reporting),
            "project_id": project_id,
            "standard_id": project.standard.id,
        }

        for language in languages:
            try:
                template = Template.objects.select_related("configuration").get(
                    configuration__regulator=user.regulators.first(),
                    configuration__standard=project.standard,
                    language=language,
                )
            except Template.DoesNotExist:
                no_template_msg = _("No report template")
                messages.error(request, messages.error(request, f"{no_template_msg} [{language}]"))
                return redirect("dashboard_report_project", report_project_id=project.id)

            with override(language):
                sector.set_current_language(language)
                task_data = {
                    **base_data,
                    "language": language,
                    "template_id": template.pk,
                    "report_configuration_id": template.configuration.pk,
                    "sector": {**model_to_dict(sector), "name": str(sector)},
                }

                prefix = f"{language}_" if len(languages) > 1 else ""
                sector_name = sector.get_safe_translation()
                annual_report_label = _("annual_report")
                filename = urlquote(f"{prefix}{annual_report_label}_{year}_{company.name}_{sector_name}.{extention}")
                task = get_report(
                    request,
                    task_data,
                    filename,
                    extention,
                    project_id,
                    task_id,
                    is_multiple_selected_companies,
                )
                report_generation_tasks.append(task.on_error(on_chord_error.s(project_id, task_id)))

    if error_messages and not report_generation_tasks:
        for error_message in error_messages:
            messages.error(request, error_message)

        return redirect("dashboard_report_project", report_project_id=project.id)

    Project.objects.filter(id=project_id).update(task_status=CELERY_TASK_STATUS[3][0], task_id=task_id)

    try:
        if is_multiple_selected_companies:
            callback = (zip_files_task.si(user.id, project_id, task_id, error_messages) | cleanup_files.si(project_id, task_id)).on_error(
                on_chord_error.s(project_id, task_id)
            )
            chord(group(report_generation_tasks))(callback)
            if error_messages:
                warning_message = _(
                    "Reports are being generated with some issues. Please check the error log in the download zip file for more details."
                )
            else:
                success_message = _("Reports are being generated.")
        else:
            task.delay()
            success_message = _("Report is being generated.")
    except (ConnectionError, RuntimeError, CeleryError):
        Project.objects.filter(id=project_id).update(task_status=CELERY_TASK_STATUS[0][0])
        messages.error(request, _("Failed to start report generation. Please try again."))
        return redirect("dashboard_report_project", report_project_id=project.id)

    if is_multiple_selected_companies and error_messages:
        messages.warning(request, warning_message)
    elif success_message:
        messages.success(request, success_message)

    return redirect("reporting")


@login_required
@otp_required
@require_http_methods(["GET"])
def report_generation_status(request, report_project_id: int):
    project = Project.objects.get(id=report_project_id)
    failure_status = CELERY_TASK_STATUS[0][0]
    success_status = CELERY_TASK_STATUS[1][0]
    revoked_status = CELERY_TASK_STATUS[2][0]
    reponse = {
        "project_id": project.id,
        "status": project.task_status,
    }

    if not reporting_health_check():
        project.task_status = failure_status
        project.save()

    if project.task_status == failure_status:
        messages.error(request, _("Report generation failed."))

    if project.task_status == success_status:
        messages.success(request, _("The report has been generated successfully."))

    if project.task_status == revoked_status:
        messages.warning(request, _("Report generation was cancelled."))

    try:
        generated_report = GeneratedReport.objects.get(project=project)
        reponse["download_uuid"] = generated_report.file_uuid
    except GeneratedReport.DoesNotExist:
        pass

    if messages.get_messages(request):
        rendered_messages = render_error_messages(request)
        reponse["messages"] = rendered_messages

    return JsonResponse(reponse)


@login_required
@otp_required
@require_http_methods(["POST"])
def cancel_report_generation(request, report_project_id: int):
    user = request.user
    project = Project.objects.get(id=report_project_id)
    task_id = str(project.task_id)
    reponse = {"project_id": project.id, "status": project.task_status}

    if not task_id:
        project.task_status = "FAIL"
        project.save()
        create_entry_log(user, project, "CANCEL REPORT GENERATION")
        return JsonResponse(reponse)

    project.task_status = "ABORT"
    project.save()

    cleanup_files.apply_async(
        kwargs={"project_id": str(report_project_id), "task_id": task_id},
        countdown=5,
    )

    create_entry_log(user, project, "CANCEL REPORT GENERATION")

    return JsonResponse(reponse)


@login_required
@otp_required
@require_http_methods(["POST"])
def update_company_project(request, company_project_id: int):
    company_project = get_object_or_404(CompanyProject, pk=company_project_id)
    project = company_project.project
    if not has_change_permission(request, project, "edit"):
        return redirect("reporting")

    form = CompanyProjectDashboard(request.POST, instance=company_project)
    if form.is_valid():
        field = request.POST.get("field")
        value = request.POST.get("value") == "true"
        CompanyProject.objects.filter(pk=company_project_id).update(**{field: value})
        reponse = {"company_project_id": company_project_id, field: value}
        return JsonResponse(reponse)
    return redirect("dashboard_report_project", report_project_id=project.id)


@login_required
@otp_required
@require_http_methods(["POST"])
def bulk_update_company_project(request, report_project_id: int):
    project = get_object_or_404(Project, pk=report_project_id)
    if not has_change_permission(request, project, "edit"):
        return redirect("reporting")

    field = request.POST.get("field")
    value = request.POST.get("value") == "true"

    company_project_qs = project.companyproject_set.all()
    dashboard_project_filter_params = request.session.get("dashboard_project_filter_params", {}).copy()

    company_project_filter = CompanyProjectFilter(dashboard_project_filter_params, queryset=company_project_qs, project=project)

    company_project_filter.qs.filter(has_security_objectives=True, has_risk_assessment=True).update(**{field: value})
    reponse = {"project_id": project.id, field: value}

    return JsonResponse(reponse)


@login_required
@otp_required
def report_recommendations(request, company_id, sector_id, year):
    validate_result = validate_url_arguments(request, company_id, sector_id, year)
    if isinstance(validate_result, HttpResponseRedirect):
        return validate_result
    company, sector, year = validate_result
    report_recommendations = company.get_report_recommandations(year, sector)
    forms = []
    for recommendation in report_recommendations:
        forms.append(ObservationRecommendationOrderForm(instance=recommendation))

    context = {
        "recommendations": forms,
        "company": company,
        "sector": sector,
        "year": year,
    }

    return render(request, "reporting/recommendations.html", context=context)


@login_required
@otp_required
def add_report_recommendations(request, company_id, sector_id, year):
    user = request.user
    validate_result = validate_url_arguments(request, company_id, sector_id, year)
    if isinstance(validate_result, HttpResponseRedirect):
        return validate_result
    company, sector, year = validate_result

    redirect_url = reverse("add_report_recommendations", args=[company.id, sector.id, year])

    if "reset" in request.GET:
        request.session.pop("report_recommendations_filter_params", None)
        return redirect(redirect_url)

    current_params = request.session.get("report_recommendations_filter_params", {}).copy()

    for key, values in request.GET.lists():
        current_params[key] = values if key == "sectors" else values[0]

    filter_params = current_params
    request.session["report_recommendations_filter_params"] = current_params

    report_recommendations = company.get_report_recommandations(year, sector)
    recommendations_ids = [rec.observation_recommendation.id for rec in report_recommendations]

    recommendations_queryset = ObservationRecommendation.objects.exclude(id__in=recommendations_ids)

    recommendation_filter = RecommendationFilter(filter_params, queryset=recommendations_queryset)

    is_filtered = {k: v for k, v in filter_params.items()}

    if request.method == "POST":
        formset = RecommendationsSelectFormSet(request.POST)
        if formset.is_valid():
            selected_recommendations = [form.instance for form in formset if form.cleaned_data.get("selected")]

            add_new_report_recommendations(company, sector, year, selected_recommendations, user)
            messages.success(
                request,
                _("Recommendations have been added successfully"),
            )
            redirect_url = reverse("report_recommendations", args=[company.id, sector.id, year])

            return redirect(redirect_url)

    formset = RecommendationsSelectFormSet(queryset=recommendation_filter.qs)

    context = {
        "formset": formset,
        "filter": recommendation_filter,
        "is_filtered": bool(is_filtered),
        "company": company,
        "sector": sector,
        "year": year,
    }

    return render(request, "reporting/add_recommendations.html", context=context)


@login_required
@otp_required
def copy_report_recommendations(request, company_id, sector_id, year):
    user = request.user
    validate_result = validate_url_arguments(request, company_id, sector_id, year)
    if isinstance(validate_result, HttpResponseRedirect):
        return validate_result
    company, sector, year = validate_result
    last_year = year - 1
    report_recommendations = company.get_report_recommandations(last_year, sector)

    if not report_recommendations:
        messages.error(
            request,
            _("No recommendations from %s") % last_year,
        )
    else:
        add_new_report_recommendations(company, sector, year, report_recommendations, user, "COPY")
        messages.success(
            request,
            _("Recommendations have been copied from %s") % last_year,
        )

    redirect_url = reverse("report_recommendations", args=[company_id, sector_id, year])

    return redirect(redirect_url)


@login_required
@otp_required
def delete_report_recommendation(request, company_id, sector_id, year, report_rec_id):
    user = request.user
    validate_result = validate_url_arguments(request, company_id, sector_id, year)
    if isinstance(validate_result, HttpResponseRedirect):
        return validate_result
    company, sector, year = validate_result

    try:
        company_reporting = CompanyReporting.objects.get(company=company, year=year, sector=sector)
        observation = Observation.objects.get(
            company_reporting=company_reporting,
            observation_recommendations__in=[report_rec_id],
        )

        recommendation = ObservationRecommendation.objects.get(id=report_rec_id)

    except (
        Observation.DoesNotExist,
        CompanyReporting.DoesNotExist,
        ObservationRecommendation.DoesNotExist,
    ):
        messages.error(request, _("No report recommendation found"))
        return redirect("reporting")

    observation.observation_recommendations.remove(recommendation)
    messages.success(request, _("The report recommendation has been deleted."))
    redirect_url = reverse("report_recommendations", args=[company.id, sector.id, year])
    create_entry_log(user, company_reporting, "DELETE RECOMMENDATIONS")

    return redirect(redirect_url)


@login_required
@otp_required
def update_report_recommendation(request, report_rec_id):
    try:
        report_recommendation = ObservationRecommendationThrough.objects.get(id=report_rec_id)
    except ObservationRecommendationThrough.DoesNotExist:
        return JsonResponse({"error": "Observation not found."}, status=404)

    if request.method == "POST":
        form = ObservationRecommendationOrderForm(request.POST, instance=report_recommendation)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True})

    messages.error(request, _("Forbidden"))
    return redirect("reporting")


@login_required
@otp_required
def import_risk_analysis(request):
    user = request.user
    sectors_queryset = Sector.objects.all()

    sector_list = get_sectors_grouped(sectors_queryset)

    companies_queryset = (
        Company.objects.filter(sectors__in=user.get_sectors().values_list("id", flat=True)).distinct()
        if user_in_group(user, "RegulatorUser")
        else Company.objects.all()
    )

    company_list = [(company.id, str(company)) for company in companies_queryset]

    try:
        initial = {}
        if "company_id" in request.GET:
            company_id = int(request.GET.get("company_id"))
            if not companies_queryset.filter(id=company_id).exists():
                messages.error(request, _("Forbidden"))
                return HttpResponseRedirect(request.headers.get("referer"))
            initial["company"] = company_id

        if "sector_id" in request.GET:
            sector_id = int(request.GET.get("sector_id"))
            if not sectors_queryset.filter(id=sector_id).exists():
                messages.error(request, _("Forbidden"))
                return HttpResponseRedirect(request.headers.get("referer"))
            initial["sectors"] = sector_id

        if "year" in request.GET:
            initial["year"] = int(request.GET.get("year"))

    except (ValueError, TypeError):
        messages.error(request, _("Invalid request"))
        return HttpResponseRedirect(request.headers.get("referer"))

    choices = {
        "company": company_list,
        "sectors": sector_list,
    }

    if request.method == "POST":
        form = ImportRiskAnalysisForm(
            request.POST,
            request.FILES,
            initial=initial or {},
            choices=choices,
        )
        if form.is_valid():
            json_file = form.cleaned_data["import_file"]
            company_id = form.cleaned_data["company"]
            sector_ids = form.cleaned_data["sectors"]
            year = form.cleaned_data["year"]
            import_task = []

            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                for chunk in json_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            try:
                validate_json_file(json_file.name, tmp_path)
            except ValidationError as e:
                messages.error(request, f"Error: {str(e)}")
                return HttpResponseRedirect(request.headers.get("referer"))

            for sector_id in sector_ids:
                validate_result = validate_url_arguments(request, company_id, sector_id, year)
                if isinstance(validate_result, HttpResponseRedirect):
                    return HttpResponseRedirect(request.headers.get("referer"))

                company, sector, year = validate_result
                company_sectors = Sector.objects.all()
                if sector not in company_sectors:
                    messages.error(
                        request,
                        f"Sector error: {str(sector)} is not linked to the {str(company)}",
                    )
                    continue

                company_reporting_obj, created = CompanyReporting.objects.get_or_create(company=company, year=year, sector=sector)
                if not created:
                    report_recommendations = list(
                        ObservationRecommendationThrough.objects.filter(observation__company_reporting=company_reporting_obj)
                    )

                    comment = str(company_reporting_obj.comment) if company_reporting_obj.comment else ""

                    company_reporting_obj.delete()
                    company_reporting_obj = CompanyReporting.objects.create(company=company, year=year, sector=sector, comment=comment)

                    if report_recommendations:
                        add_new_report_recommendations(company, sector, year, report_recommendations, user, "COPY")

                try:
                    import_task.append(import_risk_analysis_task.s(tmp_path, company_reporting_obj.pk))
                except Exception as e:
                    os.unlink(tmp_path)
                    messages.error(request, f"Parsing error: {str(e)}")
                    return HttpResponseRedirect(request.headers.get("referer"))

                CompanyProject.objects.filter(company=company, year=year, sector=sector).update(has_risk_assessment=True)

            if import_task:
                task_group = group(import_task)
                group_result = task_group.apply_async()
                group_result.save()
                request.session["import_ra_tmp_path"] = tmp_path
                # Fallback cleanup after 1 hour — in case status view never gets called
                cleanup_ra_tmp_file_task.apply_async(args=[tmp_path], countdown=3600)

            return JsonResponse({"import_ra_group_id": group_result.id if import_task else None})

    form = ImportRiskAnalysisForm(
        initial=initial or {},
        choices=choices,
    )
    context = {"form": form}
    return render(request, "modals/risk_analysis_import.html", context=context)


@login_required
@otp_required
@require_http_methods(["GET"])
def import_risk_analysis_status(request, group_id):
    result = GroupResult.restore(group_id)

    if result is None:
        return JsonResponse({"state": "UNKNOWN"})

    total = len(result)
    completed = result.completed_count()
    is_ready = result.ready()
    is_failed = is_ready and not result.successful()

    if is_ready:
        # Clean up tmp file — stored in session before enqueuing
        tmp_path = request.session.pop("import_ra_tmp_path", None)
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return JsonResponse(
        {
            "state": "FAILURE" if is_failed else ("SUCCESS" if is_ready else "PROGRESS"),
            "current": completed,
            "total": total,
            "percent": int((completed / total) * 100) if total else 0,
        }
    )


@login_required
@otp_required
def access_log(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if not has_change_permission(request, project, "log"):
        return redirect("reporting")
    try:
        log = LogReporting.objects.filter(project=project).order_by("-timestamp")
    except Project.DoesNotExist:
        log = LogReporting.objects.none()

    context = {"log": log}
    return render(request, "modals/reporting_access_log.html", context=context)


@login_required
@otp_required
def review_comment_report(request, company_id, sector_id, year):
    user = request.user
    validate_result = validate_url_arguments(request, company_id, sector_id, year)
    if isinstance(validate_result, HttpResponseRedirect):
        return validate_result
    company, sector, year = validate_result
    try:
        company_reporting = CompanyReporting.objects.get(company=company, year=year, sector=sector)
    except CompanyReporting.DoesNotExist:
        return render(request, "reporting/dashboard.html", {})

    if request.method == "POST":
        form = ReviewCommentForm(request.POST, instance=company_reporting)
        if form.is_valid():
            form.save()
            create_entry_log(user, company_reporting, "ADD COMMENT")
            return redirect("reporting")
    else:
        form = ReviewCommentForm(instance=company_reporting)

    context = {
        "form": form,
        "company": company,
        "sector": sector,
        "year": year,
    }

    return render(request, "modals/review_comment_report.html", context=context)


@login_required
@otp_required
def download_report(request, report_project_id: int, file_uuid):
    report = get_object_or_404(GeneratedReport, file_uuid=file_uuid, project__id=report_project_id)
    user = request.user
    project = report.project
    if not has_change_permission(request, project, "download"):
        return redirect("reporting")

    file_path = report.get_file_path()
    create_entry_log(user, project, "DOWNLOAD REPORT")
    return FileResponse(open(file_path, "rb"), as_attachment=True, filename=report.filename)


@login_required
@otp_required
@permission_required("reporting.view_template")
def download_template(request, pk):
    template = Template.objects.get(pk=pk)
    response = HttpResponse(
        bytes(template.template_file),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="template_{template.language}.docx"'
    return response


def get_report(
    request: HttpRequest,
    cleaned_data: dict,
    filename,
    extention,
    project_id,
    task_id,
    is_multiple_files: bool,
):
    user = request.user

    steps = [
        generate_data.s(project_id, task_id, cleaned_data),
        generate_docx_task.si(project_id, task_id),
    ]

    if extention == "pdf":
        steps.append(generate_pdf_task.si(project_id, task_id))

    steps.append(
        save_file_task.si(
            project_id,
            task_id,
            user.id,
            filename,
            is_multiple_files,
        )
    )

    if not is_multiple_files:
        return chain(*steps, cleanup_files.si(project_id, task_id))
    return chain(*steps)


def validate_url_arguments(request, company_id, sector_id, year):
    user = request.user
    user_sectors = user.get_sectors().all()

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        messages.error(
            request,
            _("No company found"),
        )
        return redirect("reporting")

    try:
        sector = Sector.objects.get(id=sector_id)
    except Sector.DoesNotExist:
        messages.error(
            request,
            _("No sector found"),
        )
        return redirect("reporting")

    try:
        year = int(year)
    except ValueError:
        messages.error(
            request,
            _("Year value is not a valid number"),
        )
        return redirect("reporting")

    current_year = timezone.now().year
    if year < 2020 or year > current_year:
        messages.error(
            request,
            _("Invalid year. Please provide a valid year."),
        )
        return redirect("reporting")

    if sector not in user_sectors:
        messages.error(request, _("Forbidden"))
        return redirect("reporting")

    return company, sector, year


def add_new_report_recommendations(company, sector, year, report_recommendations, user, action="ADD"):
    company_reporting_obj, created = CompanyReporting.objects.get_or_create(company=company, year=year, sector=sector)
    observation_obj, created = Observation.objects.get_or_create(company_reporting=company_reporting_obj)
    if action == "ADD":
        observation_obj.observation_recommendations.add(*report_recommendations)

        create_entry_log(user, company_reporting_obj, "ADD RECOMMENDATIONS")
    elif action == "COPY":
        new_report_recommendations = [
            ObservationRecommendationThrough(
                observation=observation_obj,
                observation_recommendation=rec.observation_recommendation,
                order=rec.order,
            )
            for rec in report_recommendations
        ]

        ObservationRecommendationThrough.objects.bulk_create(new_report_recommendations)

    create_entry_log(user, company_reporting_obj, f"{action} RECOMMENDATIONS")


def render_error_messages(request):
    return render_to_string(
        "django_bootstrap5/messages.html",
        {"messages": messages.get_messages(request)},
        request=request,
    )


def is_celery_worker_alive():
    try:
        inspect = current_app.control.inspect()
        response = inspect.ping()
        return bool(response)
    except Exception:
        return False


def is_redis_available():
    try:
        r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        return True
    except redis.exceptions.RedisError:
        return False


def reporting_health_check():
    return is_celery_worker_alive() and is_redis_available()
