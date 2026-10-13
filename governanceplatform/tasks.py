#!/usr/bin/env python3

import os

from celery import shared_task

from governanceplatform.async_pdf import discard_pdf, get_pdf_file_path
from governanceplatform.scripts import (  # noqa: F401
    clean_incident_user,
    unactive_account_cleaning,
)


def store_async_pdf(task_id: str, pdf_report: bytes) -> None:
    file_path = get_pdf_file_path(task_id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as pdf_file:
        pdf_file.write(pdf_report)

    # The download removes the file; this only catches the ones nobody came back for.
    cleanup_async_pdf_file.apply_async(kwargs={"task_id": task_id}, countdown=3600)


@shared_task
def cleanup_async_pdf_file(task_id: str):
    discard_pdf(task_id)
