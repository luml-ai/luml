"""Check installed dependencies and MLflow's artifact entry point."""

import subprocess
import sys
from importlib.metadata import requires, version
from pathlib import Path

import pytest
from packaging.requirements import Requirement


@pytest.mark.parametrize("dependency", ["fnnx", "luml-api", "luml-sdk"])
def test_installed_dependencies_satisfy_plugin_requirements(dependency: str) -> None:
    requirements = requires("luml-mlflow")
    assert requirements is not None
    requirement = next(
        Requirement(value)
        for value in requirements
        if Requirement(value).name == dependency
    )
    installed = version(dependency)
    assert installed in requirement.specifier, (
        f"{dependency} {installed}: {requirement}"
    )


@pytest.mark.parametrize("first_import", ["mlflow", "luml_mlflow.store"])
def test_luml_artifact_repository_registers(
    first_import: str, temp_store: Path
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import warnings

warnings.filterwarnings(
    "error",
    message='Failure attempting to register artifact repository for scheme "luml"',
    category=UserWarning,
)
import {first_import}
from mlflow.store.artifact.artifact_repository_registry import get_artifact_repository
from luml_mlflow.artifact_repo import LumlArtifactRepository

repository = get_artifact_repository("luml://local/runs/test-run/artifacts")
assert isinstance(repository, LumlArtifactRepository)
assert repository.run_id == "test-run"
""",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
