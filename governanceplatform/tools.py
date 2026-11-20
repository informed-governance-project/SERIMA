import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)

PYPROJECT_FILE = Path(__file__).resolve().parent.parent / "pyproject.toml"


def get_version() -> dict[str, str]:
    """
    Returns a dictionary containing the application version, read from pyproject.toml.
    """
    try:
        app_version = tomllib.loads(PYPROJECT_FILE.read_text())["project"]["version"]
    except FileNotFoundError:
        app_version = "unknown"

    return {"app_version": app_version}


def get_private_files_root(config: ModuleType, default: str) -> str:
    """
    Returns PRIVATE_FILES_ROOT from the configuration, still honouring its former name.

    An instance upgraded without renaming the key would otherwise fall back to the default
    folder without any error, and lose sight of the reports it already generated.
    """
    if hasattr(config, "PRIVATE_FILES_ROOT"):
        return config.PRIVATE_FILES_ROOT

    if hasattr(config, "PATH_FOR_REPORTING_PDF"):
        logger.warning("PATH_FOR_REPORTING_PDF is deprecated, rename it to PRIVATE_FILES_ROOT in config.py.")
        return config.PATH_FOR_REPORTING_PDF

    return default
