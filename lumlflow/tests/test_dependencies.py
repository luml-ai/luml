import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_runtime_dependencies_include_frame_serialization_not_demo_packages() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file:
        dependencies = tomllib.load(file)["project"]["dependencies"]

    names = {
        dependency.split("[", 1)[0].split("<", 1)[0].split(">", 1)[0]
        for dependency in dependencies
    }

    assert "pyarrow" in names
    assert "scikit-learn" not in names
    assert "matplotlib" not in names
