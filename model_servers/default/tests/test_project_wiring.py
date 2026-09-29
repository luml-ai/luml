import json
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SATELLITE_ROOT = REPOSITORY_ROOT / "satellite"


@pytest.fixture(scope="module")
def docker_compose_cli() -> str:
    executable = shutil.which("docker")
    if executable is None:
        pytest.skip("Docker is not installed; Compose configuration was not verified")

    result = subprocess.run(
        [executable, "compose", "version"],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.skip("Docker Compose is unavailable; Compose configuration was not verified")
    return executable


def test_compose_keeps_field_install_names_and_uses_the_moved_context(
    docker_compose_cli: str,
) -> None:
    result = subprocess.run(
        [
            docker_compose_cli,
            "compose",
            "--env-file",
            str(SATELLITE_ROOT / ".env.example"),
            "--file",
            str(SATELLITE_ROOT / "docker-compose.yml"),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    configuration = cast(dict[str, object], json.loads(result.stdout))
    services = cast(dict[str, dict[str, object]], configuration["services"])
    model_service = services["model-image"]
    model_build = cast(dict[str, str], model_service["build"])
    agent_service = services["agent"]

    assert model_service["image"] == "luml-random-svc:latest"
    assert Path(model_build["context"]).resolve() == REPOSITORY_ROOT / "model_servers/default"
    assert agent_service["image"] == "luml-satellite-agent:latest"

    ports = cast(list[dict[str, object]], agent_service["ports"])
    assert any(port["target"] == 8000 and str(port["published"]) == "80" for port in ports)
    networks = cast(dict[str, dict[str, object]], agent_service["networks"])
    assert "satellite-agent" in cast(list[str], networks["satellite-network"]["aliases"])


def test_publish_workflow_keeps_the_image_and_release_tag_contract() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/publish-model-server-image.yml").read_text()

    assert '      - "satellite/model-server/v*"' in workflow
    assert "IMAGE_NAME: ghcr.io/${{ github.repository_owner }}/luml-model-server" in workflow
    assert "      - model_servers/default/**" in workflow
    assert "          context: model_servers/default" in workflow
    assert "          file: model_servers/default/Dockerfile" in workflow
    assert "satellite/model_server" not in workflow
