import ast
import tomllib
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = Path(__file__).parents[4]
SOURCE_ROOT = PACKAGE_ROOT / "luml_satellite_kubernetes"


def test_project_uses_the_kit_and_async_kubernetes_client() -> None:
    project = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]

    assert any(item.startswith("luml-satellite[monitoring,serving]") for item in dependencies)
    assert any(item.startswith("kubernetes-asyncio") for item in dependencies)
    assert project["tool"]["uv"]["sources"]["luml-satellite"] == {
        "path": "../../kit",
        "editable": True,
    }
    assert project["tool"]["mypy"]["strict"] is True
    assert project["tool"]["ruff"]["target-version"] == "py314"


def test_package_reaches_the_platform_only_through_the_kit_client() -> None:
    forbidden_http_clients = {"aiohttp", "httpx", "requests", "urllib3"}
    platform_client_imports: list[Path] = []

    for path in SOURCE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text())
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        assert imported_roots.isdisjoint(forbidden_http_clients), path
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module == "luml_satellite"
            and any(alias.name == "PlatformClient" for alias in node.names)
            for node in ast.walk(tree)
        ):
            platform_client_imports.append(path)

    assert platform_client_imports == [SOURCE_ROOT / "main.py"]


def test_image_runs_as_a_non_root_group_zero_user() -> None:
    dockerfile = (PACKAGE_ROOT / "Dockerfile").read_text()

    assert dockerfile.startswith("FROM python:3.14-")
    assert "chgrp -R 0 /app" in dockerfile
    assert "chmod -R g=u /app" in dockerfile
    assert "USER 10001:0" in dockerfile
    assert 'CMD ["luml-satellite-kubernetes"]' in dockerfile


def test_frontend_uses_the_package_settings_snapshot() -> None:
    frontend_test = (
        REPOSITORY_ROOT
        / "frontend/src/components/deployments/form/DeploymentsFormSatelliteSettings.test.ts"
    ).read_text()

    assert "satellite/implementations/kubernetes/tests/snapshots/settings_fields.json" in (
        frontend_test
    )


def test_kubernetes_workflows_exist() -> None:
    workflows = REPOSITORY_ROOT / ".github/workflows"

    assert (workflows / "[satellite-kubernetes] tests-and-linters.yml").is_file()
    assert (workflows / "publish-kubernetes-satellite-image.yml").is_file()
    assert (workflows / "publish-kubernetes-satellite-chart.yml").is_file()
    kubernetes_workflow = (workflows / "[satellite-kubernetes] tests-and-linters.yml").read_text()
    assert "helm lint chart --strict" in kubernetes_workflow
    assert "helm unittest --strict chart" in kubernetes_workflow
    chart_workflow = (workflows / "publish-kubernetes-satellite-chart.yml").read_text()
    assert '"satellite/kubernetes/chart/v*"' in chart_workflow
    assert "helm package satellite/implementations/kubernetes/chart" in chart_workflow
    assert "helm push" in chart_workflow
    assert '"oci://ghcr.io/$OWNER_LOWER/charts"' in chart_workflow
    frontend_workflow = (workflows / "[frontend] tests-and-linters.yml").read_text()
    assert "kubernetes/tests/snapshots/settings_fields.json" in frontend_workflow
