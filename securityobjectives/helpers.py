import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from governanceplatform.models import Company, Sector

logger = logging.getLogger(__name__)


def security_objective_exists(company: Company, year: int | None = None, sector: Sector | None = None) -> bool:
    """Whether the company has a submitted standard answer for that year and sector."""
    if not (year and sector):
        return False

    return company.standardanswer_set.filter(year_of_submission=year, sectors__in=[sector.id], status="PASSM").exists()


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
