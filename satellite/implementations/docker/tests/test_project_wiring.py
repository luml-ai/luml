from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SATELLITE_ROOT = REPOSITORY_ROOT / "satellite"
WORKFLOWS_ROOT = REPOSITORY_ROOT / ".github" / "workflows"


def test_compose_store_has_no_published_ports_and_an_isolated_network() -> None:
    compose = (SATELLITE_ROOT / "docker-compose.yml").read_text()
    store = compose.split("\n  greptimedb:\n", maxsplit=1)[1].split("\n  otel-collector:\n")[0]
    collector = compose.split("\n  otel-collector:\n", maxsplit=1)[1].split("\n  model-image:\n")[0]
    agent = compose.split("\n  agent:\n", maxsplit=1)[1]
    model = compose.split("\n  model-image:\n", maxsplit=1)[1].split("\n  agent:\n")[0]

    assert "    ports:" not in store
    assert "      - store-network\n" in store
    assert "      - satellite-network\n" not in store
    assert "      - store-network\n" in collector
    assert "      store-network:" in agent
    assert "store-network" not in model
    assert '      df.model-access: "true"\n' in compose.split("\nvolumes:", maxsplit=1)[0]


def test_compose_store_requires_credentials_and_passes_them_to_consumers() -> None:
    compose = (SATELLITE_ROOT / "docker-compose.yml").read_text()
    store = compose.split("\n  greptimedb:\n", maxsplit=1)[1].split("\n  otel-collector:\n")[0]
    assert "--user-provider=static_user_provider:cmd:" in store
    for service in (
        store,
        compose.split("\n  otel-collector:\n")[1].split("\n  model-image:\n")[0],
        compose.split("\n  agent:\n")[1],
    ):
        assert "${GREPTIMEDB_USERNAME:?" in service
        assert "${GREPTIMEDB_PASSWORD:?" in service

    collector = (SATELLITE_ROOT / "otel-collector-config.yaml").read_text()
    assert "      username: ${env:GREPTIMEDB_USERNAME}\n" in collector
    assert "      password: ${env:GREPTIMEDB_PASSWORD}\n" in collector
    assert collector.count("      authenticator: basicauth/client\n") == 2
    assert "  extensions: [basicauth/client]\n" in collector


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
