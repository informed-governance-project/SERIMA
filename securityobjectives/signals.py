from django.db.models.signals import post_save
from django.dispatch import receiver

from .helpers import delete_file_and_parents


@receiver(post_save, sender="import_export_extensions.ImportJob")
def cleanup_import_job_files(sender, instance, **kwargs):
    TERMINAL_STATUSES = {
        sender.ImportStatus.IMPORTED,
        sender.ImportStatus.IMPORT_ERROR,
        sender.ImportStatus.PARSE_ERROR,
        sender.ImportStatus.INPUT_ERROR,
        sender.ImportStatus.CANCELLED,
        sender.ImportStatus.PARSED,
    }

    if instance.import_status == sender.ImportStatus.PARSED:
        from .tasks import cleanup_unconfirmed_import_file

        cleanup_unconfirmed_import_file.apply_async(
            args=[instance.pk],
            countdown=3600,
        )
        return

    if instance.import_status not in TERMINAL_STATUSES:
        return

    delete_file_and_parents(instance.data_file, "data_file")
    delete_file_and_parents(instance.input_errors_file, "input_errors_file")


@receiver(post_save, sender="import_export_extensions.ExportJob")
def cleanup_export_job_files(sender, instance, **kwargs):
    # Immediate cleanup for error/cancelled — file is useless
    TERMINAL_ERROR_STATUSES = {
        sender.ExportStatus.EXPORT_ERROR,
        sender.ExportStatus.CANCELLED,
    }
    if instance.export_status in TERMINAL_ERROR_STATUSES:
        delete_file_and_parents(instance.data_file, "export data_file")
        return

    # Deferred cleanup for successful exports — keep the file available for a while
    if instance.export_status == sender.ExportStatus.EXPORTED:
        from .tasks import cleanup_old_export_files

        cleanup_old_export_files.apply_async(
            args=[instance.pk],
            countdown=3600,  # seconds — file stays available for 1 hour
        )
