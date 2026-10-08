import tomllib
from pathlib import Path

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
