import tomllib
from pathlib import Path
from types import SimpleNamespace

from governanceplatform import tools


def test_get_version_reads_pyproject():
    """Report the version declared in pyproject.toml."""
    declared = tomllib.loads(tools.PYPROJECT_FILE.read_text())["project"]["version"]

    assert tools.get_version() == {"app_version": declared}


def test_get_version_without_pyproject(monkeypatch, tmp_path):
    """Fall back to "unknown" when pyproject.toml is not shipped alongside the code."""
    monkeypatch.setattr(tools, "PYPROJECT_FILE", Path(tmp_path) / "pyproject.toml")

    assert tools.get_version() == {"app_version": "unknown"}


def test_get_private_files_root_reads_the_new_name():
    config = SimpleNamespace(PRIVATE_FILES_ROOT="/srv/private", PATH_FOR_REPORTING_PDF="/srv/old")

    assert tools.get_private_files_root(config, default="/default") == "/srv/private"


def test_get_private_files_root_still_reads_the_former_name(caplog):
    """An upgraded config.py keeps pointing at the folder holding its existing reports."""
    config = SimpleNamespace(PATH_FOR_REPORTING_PDF="/srv/old")

    assert tools.get_private_files_root(config, default="/default") == "/srv/old"
    assert "PATH_FOR_REPORTING_PDF is deprecated" in caplog.text


def test_get_private_files_root_without_either_name():
    assert tools.get_private_files_root(SimpleNamespace(), default="/default") == "/default"
