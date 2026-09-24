#!/usr/bin/env python3

import csv
import io
import os
import zipfile
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.template.defaultfilters import floatformat
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from import_export_extensions.models import ExportJob, ImportJob
from openpyxl import Workbook

from governanceplatform.globals import EXPORT
from governanceplatform.helpers import delete_file_and_parents
from governanceplatform.models import Regulation, Sector, User
from incidents.helpers import sanitize_spreadsheet_cell
from securityobjectives.scripts import so_declarations_cleaning  # noqa: F401

from .email import send_export_notification
from .globals import SO_EXPORT_COLUMNS, STANDARD_ANSWER_REVIEW_STATUS
from .helpers import get_export_sector_ids, get_exportable_standard_answers
from .models import SecurityObjectiveExport, Standard


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


def format_export_datetime(value) -> str:
    """Render a timestamp the way the dashboard does, so the two can be compared."""
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d/%m/%y %H:%M")


def get_export_rows(queryset) -> list[list]:
    return [
        [
            declaration.get_status_display(),
            format_export_datetime(declaration.last_update),
            format_export_datetime(declaration.submit_date),
            declaration.group.group_id if declaration.group else "",
            declaration.standard.label if declaration.standard else "",
            declaration.creator_company_name,
            ", ".join(sector.get_safe_translation() for sector in declaration.sectors.all()),
            declaration.year_of_submission,
            # floatformat rather than an f-string, because the dashboard rounds halves up
            # and Python rounds them to even.
            f"{floatformat(declaration.reviewed_percentage, 0)}%",
        ]
        for declaration in queryset
    ]


def get_export_metadata(user, filters, sector_ids, row_count) -> list[list[str]]:
    """Record what produced the file, so it stays interpretable once it leaves the platform."""
    regulation = Regulation.objects.filter(id=filters["regulation"]).first()
    statuses = dict(STANDARD_ANSWER_REVIEW_STATUS)
    sectors = Sector.objects.filter(id__in=sector_ids)
    standards = Standard.objects.filter(id__in=filters["standards"])

    return [
        [str(_("Author")), f"{user.get_full_name()} ({user.email})"],
        [str(_("Export date")), format_export_datetime(timezone.now())],
        [str(_("Regulation")), str(regulation) if regulation else ""],
        [
            str(_("Evaluation Framework")),
            ", ".join(standard.label for standard in standards),
        ],
        [str(_("Year")), ", ".join(str(year) for year in filters["years"])],
        [str(_("Sectors")), ", ".join(sector.get_safe_translation() for sector in sectors)],
        [str(_("Status")), ", ".join(str(statuses.get(status, status)) for status in filters["statuses"])],
        [str(_("File format")), filters["file_format"]],
        [str(_("Number of rows")), str(row_count)],
    ]


def write_csv(rows) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    for row in rows:
        writer.writerow([sanitize_spreadsheet_cell(value) for value in row])
    return buffer.getvalue()


def set_column_widths(worksheet):
    for column_cells in worksheet.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 60)


def write_export_xlsx(file_path, headers, rows, metadata):
    workbook = Workbook()
    declarations_sheet = workbook.active
    declarations_sheet.title = str(_("Declarations"))
    declarations_sheet.append([sanitize_spreadsheet_cell(header) for header in headers])
    for row in rows:
        declarations_sheet.append([sanitize_spreadsheet_cell(value) for value in row])
    set_column_widths(declarations_sheet)

    metadata_sheet = workbook.create_sheet(str(_("Metadata")))
    for row in metadata:
        metadata_sheet.append([sanitize_spreadsheet_cell(value) for value in row])
    set_column_widths(metadata_sheet)

    workbook.save(file_path)


def write_export_zip(file_path, headers, rows, metadata):
    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("declarations.csv", write_csv([headers, *rows]))
        archive.writestr("metadata.csv", write_csv(metadata))


def log_so_export(user, declarations, regulation, filters, sector_ids, row_count):
    """One entry per exported declaration, each holding the parameters of the export.

    Anchoring on the declarations rather than on the regulation is what makes the admin log
    say which declarations left the platform, at the cost of one row per exported line.
    """
    statuses = dict(STANDARD_ANSWER_REVIEW_STATUS)

    with translation.override(settings.LANGUAGE_CODE):
        change_message = _(
            "A total of {count} security objective declarations were exported from regulation {regulation} "
            "[frameworks: {frameworks}] for year(s) {years}, sector(s) {sectors}, status(es) {statuses}, "
            "in {file_format} format."
        ).format(
            count=row_count,
            regulation=regulation,
            frameworks=", ".join(standard.label for standard in Standard.objects.filter(id__in=filters["standards"])),
            years=", ".join(str(year) for year in filters["years"]),
            sectors=", ".join(sector.get_safe_translation() for sector in Sector.objects.filter(id__in=sector_ids)),
            statuses=", ".join(str(statuses.get(status, status)) for status in filters["statuses"]),
            file_format=filters["file_format"],
        )

    LogEntry.objects.log_actions(
        user_id=user.id,
        queryset=declarations,
        action_flag=EXPORT,
        change_message=change_message,
    )


@shared_task
def generate_so_export_task(export_id: int, user_id: int, filters: dict, language: str):
    """Build the export file, then log it once and warn the regulator's contacts once.

    No autoretry: a retry would write a second log entry and send a second e-mail for the
    same export.
    """
    export = SecurityObjectiveExport.objects.get(pk=export_id)
    user = User.objects.get(pk=user_id)

    try:
        with translation.override(language):
            queryset = get_exportable_standard_answers(user, filters)
            rows = get_export_rows(queryset)
            sector_ids = get_export_sector_ids(user, filters["sectors"])
            metadata = get_export_metadata(user, filters, sector_ids, len(rows))
            headers = [str(column) for column in SO_EXPORT_COLUMNS]

            file_path = export.get_file_path()
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            if filters["file_format"] == "xlsx":
                write_export_xlsx(file_path, headers, rows, metadata)
            else:
                write_export_zip(file_path, headers, rows, metadata)
    except Exception:
        export.task_status = "FAIL"
        export.save()
        raise

    export.task_status = "DONE"
    export.save()

    log_so_export(user, queryset, export.regulation, filters, sector_ids, len(rows))

    send_export_notification(
        regulator=user.regulators.first(),
        regulation=export.regulation,
        sector_ids=sector_ids,
    )

    cleanup_so_export_file.apply_async(kwargs={"export_id": export.id}, countdown=3600)


@shared_task
def cleanup_so_export_file(export_id: int):
    try:
        export = SecurityObjectiveExport.objects.get(pk=export_id)
    except SecurityObjectiveExport.DoesNotExist:
        return

    # A plain path, not a FileField, so delete_file_and_parents does not apply here. The
    # export directory is shared by every export and stays in place.
    Path(export.get_file_path()).unlink(missing_ok=True)
    export.delete()


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
