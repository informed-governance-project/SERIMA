import os
import re

import kaleido
import plotly.io as pio
import psutil
from celery.signals import worker_process_init, worker_process_shutdown
from celery.utils.log import get_task_logger
from choreographer.browsers.chromium import Chromium
from django.apps import apps
from django.conf import settings
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import Signal, receiver

from governanceplatform.models import Company
from securityobjectives.helpers import security_objective_exists

from .helpers import risk_analysis_exists
from .models import CompanyProject, Project, RiskData

logger = get_task_logger(__name__)

# define a signal to update project
project_needs_update = Signal()

SOFFICE_PIPE_OWNER = re.compile(r"name=update_toc_(\d+)")


# Update project when a company is changed
@receiver(m2m_changed, sender=Company.sectors.through)
def update_project_on_company_sectors_changed(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        for project in Project.objects.all():
            intersection = list(set(project.sectors.all()) & set(instance.sectors.all()))
            if intersection:
                project_needs_update.send(
                    sender=Project.sectors.through,
                    instance=project,
                    action="post_add",
                    pk_set=None,
                )
    if action == "post_remove":
        cc = CompanyProject.objects.filter(company=instance).exclude(
            sector__in=instance.sectors.all(),
        )
        cc.delete()


# Automatically create the link between company and project
# when a project is saved and link with sectors is changed
@receiver(project_needs_update)
@receiver(m2m_changed, sender=Project.sectors.through)
def create_company_projects_on_sectors_change(sender, instance, action, pk_set, **kwargs):
    if action not in ("post_add", "post_remove"):
        return
    Company = apps.get_model("governanceplatform", "Company")
    companies = Company.objects.all()
    sectors = instance.sectors.all()
    years = instance.years or []
    if instance.reference_year not in instance.years:
        years.append(instance.reference_year)

    company_projects = [
        CompanyProject(
            company=company,
            project=instance,
            sector=sector,
            year=year,
            has_security_objectives=security_objective_exists(company, year, sector),
            has_risk_assessment=risk_analysis_exists(company, year, sector),
        )
        for company in companies
        for sector in sectors & company.sectors.all()
        for year in years
    ]
    if action == "post_add":
        CompanyProject.objects.bulk_create(
            company_projects,
            ignore_conflicts=True,
        )
    if action == "post_remove":
        cc = CompanyProject.objects.all().exclude(
            sector__in=sectors,
            year__in=years,
            company__in=companies,
        )
        cc.delete()


# function to help to manage company project when changing
# years or reference_years
@receiver(pre_save, sender=Project)
def track_years_changes(sender, instance, **kwargs):
    # Store old years values before save to detect changes
    if instance.pk:
        try:
            old = Project.objects.get(pk=instance.pk)
            instance._old_years = old.years or []
            instance._old_reference_year = old.reference_year
        except Project.DoesNotExist:
            instance._old_years = []
            instance._old_reference_year = None
    else:
        instance._old_years = []
        instance._old_reference_year = None


# update company project when changing years or reference_year
@receiver(post_save, sender=Project)
def update_company_project(sender, instance, **kwargs):
    old_years = getattr(instance, "_old_years", [])
    old_reference_year = getattr(instance, "_old_reference_year", None)

    new_years = set(instance.years or [])
    new_years.add(instance.reference_year)

    old_years_set = set(old_years or [])
    if old_reference_year:
        old_years_set.add(old_reference_year)

    if new_years == old_years_set:
        return

    Company = apps.get_model("governanceplatform", "Company")
    companies = Company.objects.all()
    sectors = instance.sectors.all()

    added_years = new_years - old_years_set
    removed_years = old_years_set - new_years

    # Create new company project
    if added_years:
        company_projects = [
            CompanyProject(
                company=company,
                project=instance,
                sector=sector,
                year=year,
                has_security_objectives=security_objective_exists(company, year, sector),
                has_risk_assessment=risk_analysis_exists(company, year, sector),
            )
            for company in companies
            for sector in sectors & company.sectors.all()
            for year in added_years
        ]
        CompanyProject.objects.bulk_create(
            company_projects,
            ignore_conflicts=True,
        )

    # delete companyproject if the year is changed
    if removed_years:
        CompanyProject.objects.filter(
            project=instance,
            year__in=removed_years,
        ).delete()


@receiver(pre_delete, sender=RiskData)
def cache_related_recommendationdata(sender, instance, **kwargs):
    # Attach related RecommendationData instances to the instance for later use
    instance._cached_recommendation_data = list(instance.recommendations.all())


@receiver(post_delete, sender=RiskData)
def delete_orphaned_recommendationdata(sender, instance, **kwargs):
    # Retrieve cached recommendationdata instances
    related_bs = getattr(instance, "_cached_recommendation_data", [])

    # Check if reco are linked to another riskdata
    for b in related_bs:
        if b.riskdata_set.count() == 0:
            b.delete()


@worker_process_init.connect
def cleanup_orphaned_soffice(**kwargs):
    # soffice is reachable only through the pipe named after the child that started
    # it, so an instance whose owner is gone is unusable and must not be left behind.
    for proc in psutil.process_iter(["cmdline"]):
        try:
            owner = SOFFICE_PIPE_OWNER.search(" ".join(proc.info["cmdline"] or ()))
            if owner and not psutil.pid_exists(int(owner.group(1))):
                proc.kill()
                logger.info("Reclaimed orphaned soffice %d, owner %s is gone", proc.pid, owner.group(1))
        except psutil.NoSuchProcess, psutil.AccessDenied:
            continue


@worker_process_init.connect
def init_kaleido(**kwargs):
    original_get_cli = Chromium.get_cli

    def patched_get_cli(self):
        cli = list(original_get_cli(self))
        proxy = (
            os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        )
        if proxy:
            cli.append(f"--proxy-server={proxy}")
        cli.extend(
            [
                "--disable-background-networking",
            ]
        )
        return cli

    Chromium.get_cli = patched_get_cli

    try:
        kaleido.start_sync_server(
            n=settings.KALEIDO_CONCURRENCY_PER_WORKER,
            mathjax=False,
        )
        logger.info("Kaleido sync server started successfully. Concurrency: %d", settings.KALEIDO_CONCURRENCY_PER_WORKER)
        # plotly's non-empty default headers become per-call kopts, which a shared
        # server ignores with a warning on every figure
        pio.defaults.headers = {}
    except Exception as e:
        logger.critical("Kaleido failed to start: %s", e)


@worker_process_shutdown.connect
def shutdown_kaleido(**kwargs):
    kaleido.stop_sync_server()
