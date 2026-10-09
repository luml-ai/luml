from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SATELLITE_ROOT = REPOSITORY_ROOT / "satellite"
WORKFLOWS_ROOT = REPOSITORY_ROOT / ".github" / "workflows"


def test_compose_builds_the_kit_implementation_with_field_install_names() -> None:
    compose = (SATELLITE_ROOT / "docker-compose.yml").read_text()
    agent_service = compose.split("\n  agent:\n", maxsplit=1)[1]

    assert "    image: luml-satellite-agent:latest\n" in agent_service
    assert "      context: .\n" in agent_service
    assert "      dockerfile: implementations/docker/Dockerfile\n" in agent_service
    assert '      - "80:8000"\n' in agent_service
    assert "          - satellite-agent\n" in agent_service

    dockerfile = (SATELLITE_ROOT / "implementations" / "docker" / "Dockerfile").read_text()
    assert "COPY kit /app/satellite/kit" in dockerfile
    assert "COPY implementations/docker /app/satellite/implementations/docker" in dockerfile


def test_publish_workflow_builds_the_kit_implementation_under_the_existing_contract() -> None:
    workflow = (WORKFLOWS_ROOT / "publish-satellite-agent-image.yml").read_text()

    assert '      - "satellite/agent/v*"' in workflow
    assert "IMAGE_NAME: ghcr.io/${{ github.repository_owner }}/luml-satellite-agent" in workflow
    assert "      - satellite/implementations/docker/**" in workflow
    assert "      - satellite/kit/**" in workflow
    assert "          context: satellite" in workflow
    assert "          file: satellite/implementations/docker/Dockerfile" in workflow
    assert "satellite/agent/**" not in workflow


def test_legacy_workflow_is_replaced_by_the_package_workflows() -> None:
    assert not (WORKFLOWS_ROOT / "[satellite] tests-and-linters.yml").exists()
    assert (WORKFLOWS_ROOT / "[satellite-kit] tests-and-linters.yml").is_file()
    assert (WORKFLOWS_ROOT / "[satellite-docker] tests-and-linters.yml").is_file()
