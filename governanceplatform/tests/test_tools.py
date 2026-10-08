import tomllib
from pathlib import Path

from governanceplatform import tools


def test_get_version_reads_pyproject():
    """Report the version declared in pyproject.toml."""
    declared = tomllib.loads(tools.PYPROJECT_FILE.read_text())["project"]["version"]

    assert tools.get_version() == {"app_version": declared}


def test_get_version_without_pyproject(monkeypatch, tmp_path):
    """Fall back to "unknown" when pyproject.toml is not shipped alongside the code."""
    monkeypatch.setattr(tools, "PYPROJECT_FILE", Path(tmp_path) / "pyproject.toml")

    assert tools.get_version() == {"app_version": "unknown"}
