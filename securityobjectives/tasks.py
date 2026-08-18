#!/usr/bin/env python3

import os

import django
from celery import shared_task
from import_export_extensions.models import ExportJob, ImportJob

from governanceplatform.helpers import delete_file_and_parents

# django init
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "governanceplatform.settings")
django.setup()

from securityobjectives.scripts import so_declarations_cleaning  # noqa: E402 F401


@shared_task
def cleanup_old_export_files(job_pk: int):
    try:
        job = ExportJob.objects.get(pk=job_pk)
    except ExportJob.DoesNotExist:
        return  # already deleted, nothing to do

    if job.export_status != ExportJob.ExportStatus.EXPORTED:
        return  # status changed (e.g. rerun), don't touch it

    delete_file_and_parents(job.data_file, f"export data_file (job {job_pk})")
    if job:
        job.delete()


@shared_task
def cleanup_unconfirmed_import_file(job_pk: int):
    try:
        job = ImportJob.objects.get(pk=job_pk)
    except ImportJob.DoesNotExist:
        return

    delete_file_and_parents(job.data_file, f"import data_file (unconfirmed job {job_pk})")
    delete_file_and_parents(job.input_errors_file, f"import input_errors_file (unconfirmed job {job_pk})")
    if job:
        job.delete()
