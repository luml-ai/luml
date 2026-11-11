import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement


@pytest.mark.parametrize(
    "package",
    [
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp-proto-http",
    ],
)
def test_direct_observability_dependencies_allow_locked_and_next_versions(
    package: str,
) -> None:
    backend = Path(__file__).resolve().parents[3]
    project = tomllib.loads((backend / "pyproject.toml").read_text())
    requirements = {
        requirement.name: requirement
        for requirement in map(Requirement, project["project"]["dependencies"])
    }
    assert package in requirements
    lock = tomllib.loads((backend / "uv.lock").read_text())
    locked = next(
        item["version"] for item in lock["package"] if item["name"] == package
    )
    assert locked in requirements[package].specifier
    assert "1.45.1" in requirements[package].specifier
