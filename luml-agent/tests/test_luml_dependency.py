import subprocess
from pathlib import Path
from unittest.mock import patch

from luml_agent.services.orchestrator.utils import (
    _has_luml_dependency,
    ensure_luml_dependency,
)

MINIMAL_PYPROJECT = """\
[project]
name = "test-project"
version = "0.1.0"
dependencies = []
"""

PYPROJECT_WITH_LUML = """\
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "luml",
    "numpy>=1.0",
]
"""

PYPROJECT_WITH_LUML_VERSIONED = """\
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "luml>=0.5.0",
]
"""

PYPROJECT_WITH_LUML_EXTRAS = """\
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "luml[tracking]",
]
"""


def test_has_luml_dependency_absent(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(MINIMAL_PYPROJECT)
    assert _has_luml_dependency(pyproject) is False


def test_has_luml_dependency_present(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT_WITH_LUML)
    assert _has_luml_dependency(pyproject) is True


def test_has_luml_dependency_versioned(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT_WITH_LUML_VERSIONED)
    assert _has_luml_dependency(pyproject) is True


def test_has_luml_dependency_extras(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT_WITH_LUML_EXTRAS)
    assert _has_luml_dependency(pyproject) is True


def test_has_luml_dependency_not_confused_by_similar_names(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "test"\ndependencies = ["luml-agent"]\n',
    )
    assert _has_luml_dependency(pyproject) is False


def test_ensure_luml_dependency_no_pyproject(tmp_path: Path) -> None:
    ensure_luml_dependency(str(tmp_path))


def test_ensure_luml_dependency_already_present(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_WITH_LUML)
    with patch("luml_agent.services.orchestrator.utils.subprocess.run") as mock_run:
        ensure_luml_dependency(str(tmp_path))
    mock_run.assert_not_called()


def test_ensure_luml_dependency_injects(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
    with patch("luml_agent.services.orchestrator.utils.subprocess.run") as mock_run:
        ensure_luml_dependency(str(tmp_path))
    mock_run.assert_called_once_with(
        ["uv", "add", "luml-sdk"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
        timeout=60,
    )


def test_ensure_luml_dependency_uv_not_available(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
    with patch(
        "luml_agent.services.orchestrator.utils.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        ensure_luml_dependency(str(tmp_path))


def test_ensure_luml_dependency_uv_failure(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
    with patch(
        "luml_agent.services.orchestrator.utils.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "uv", stderr=b"network error"),
    ):
        ensure_luml_dependency(str(tmp_path))


def test_ensure_luml_dependency_uv_timeout(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
    with patch(
        "luml_agent.services.orchestrator.utils.subprocess.run",
        side_effect=subprocess.TimeoutExpired("uv", 60),
    ):
        ensure_luml_dependency(str(tmp_path))
