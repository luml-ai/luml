import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement


@pytest.mark.parametrize(
    ("package", "minimum_version", "next_major_version"),
    [
        ("pydantic", "2.12.4", "3.0.0"),
        ("pydantic-settings", "2.16.2", "3.0.0"),
        ("starlette", "1.3.1", "2.0.0"),
    ],
)
def test_direct_framework_dependencies_are_declared_once_with_compatible_ranges(
    package: str, minimum_version: str, next_major_version: str
) -> None:
    backend = Path(__file__).resolve().parents[3]
    project = tomllib.loads((backend / "pyproject.toml").read_text())
    requirements = [
        requirement
        for requirement in map(Requirement, project["project"]["dependencies"])
        if requirement.name == package
    ]
    assert len(requirements) == 1
    specifier = requirements[0].specifier
    lock = tomllib.loads((backend / "uv.lock").read_text())
    locked_version = next(
        item["version"] for item in lock["package"] if item["name"] == package
    )
    assert locked_version in specifier
    assert minimum_version in specifier
    assert next_major_version not in specifier
