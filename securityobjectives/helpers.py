import logging
import os

logger = logging.getLogger(__name__)


def delete_file_and_parents(file_field, label: str) -> None:
    """
    Delete a FileField file from storage and clean up empty parent directories
    up to (but not including) the storage root.
    """
    if not file_field:
        return
    try:
        # Resolve the absolute path before deleting the file
        storage = file_field.storage
        abs_path = os.path.realpath(storage.path(file_field.name))

        # Delete the file itself
        file_field.delete(save=False)

        # Walk up and remove empty directories until we hit the storage root
        storage_root = os.path.abspath(storage.location)
        current_dir = os.path.dirname(abs_path)

        while True:
            current_dir = os.path.realpath(current_dir)

            # Guard 1: never climb above storage root
            if not current_dir.startswith(storage_root + os.sep):
                break

            # Guard 2: universal filesystem root backstop
            if current_dir == os.path.dirname(current_dir):
                break
            try:
                os.rmdir(current_dir)  # only removes if empty
                current_dir = os.path.dirname(current_dir)
            except OSError:
                # Directory not empty or already gone — stop climbing
                break

    except Exception:
        logger.exception("Failed to delete %s: %s", label, file_field.name)
