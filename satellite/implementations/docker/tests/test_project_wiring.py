import re
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SATELLITE_ROOT = REPOSITORY_ROOT / "satellite"
WORKFLOWS_ROOT = REPOSITORY_ROOT / ".github" / "workflows"
GUIDE = REPOSITORY_ROOT / "docs" / "docs" / "guides" / "satellite.md"
GUIDE_AGENT_IMAGE = "ghcr.io/luml-ai/luml-satellite-agent:latest"
GUIDE_MODEL_IMAGE = "ghcr.io/luml-ai/luml-model-server:latest"
GUIDE_ENVIRONMENT_DEFAULTS = {
    "PLATFORM_URL": "${PLATFORM_URL:-https://api.luml.ai}",
    "MODEL_IMAGE": f"${{MODEL_IMAGE:-{GUIDE_MODEL_IMAGE}}}",
    "MONITORING_FRAME_ANCESTORS": "${MONITORING_FRAME_ANCESTORS:-https://app.luml.ai}",
}


def guide_file(name: str) -> str:
    match = re.search(
        rf"^\*\*\d+\. Create `{re.escape(name)}`\*\*.*?\n```\w*\n(.*?)^```",
        GUIDE.read_text(),
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, f"guide has no step creating {name}"
    return match.group(1)


def compose_as_published(compose: dict[str, Any]) -> dict[str, Any]:
    services = compose["services"]
    model_image = services.pop("model-image")
    services["model-server"] = {
        "image": GUIDE_MODEL_IMAGE,
        "platform": "linux/amd64",
        "command": model_image["command"],
        "restart": model_image["restart"],
    }
    agent = services["agent"]
    del agent["build"]
    agent["image"] = GUIDE_AGENT_IMAGE
    agent["environment"].update(GUIDE_ENVIRONMENT_DEFAULTS)
    agent["depends_on"] = [
        "model-server" if service == "model-image" else service for service in agent["depends_on"]
    ]
    return {"name": "satellite", **compose}


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
    assert "          - satellite-agent\n" in agent_service

    dockerfile = (SATELLITE_ROOT / "implementations" / "docker" / "Dockerfile").read_text()
    assert "COPY kit /app/satellite/kit" in dockerfile
    assert "COPY implementations/docker /app/satellite/implementations/docker" in dockerfile


def test_publish_workflow_builds_the_kit_implementation_under_the_existing_contract() -> None:
    workflow = (WORKFLOWS_ROOT / "publish-satellite-images.yml").read_text()

    assert '      - "satellite/agent/v*"' in workflow
    assert "      - satellite/implementations/docker/**" in workflow
    assert "      - satellite/kit/**" in workflow
    assert (
        '"name":"luml-satellite-agent","context":"satellite",'
        '"file":"satellite/implementations/docker/Dockerfile"'
    ) in workflow
    assert "satellite/agent/**" not in workflow


def test_legacy_workflow_is_replaced_by_the_package_workflows() -> None:
    assert not (WORKFLOWS_ROOT / "[satellite] tests-and-linters.yml").exists()
    assert (WORKFLOWS_ROOT / "[satellite-kit] tests-and-linters.yml").is_file()
    assert (WORKFLOWS_ROOT / "[satellite-docker] tests-and-linters.yml").is_file()


def test_agent_has_no_direct_host_privileges_or_public_port() -> None:
    compose = (SATELLITE_ROOT / "docker-compose.yml").read_text()
    agent = compose.split("\n  agent:\n", maxsplit=1)[1]

    assert "docker.sock" not in agent
    assert "    ports:" not in agent
    assert '    user: "10001:10001"' in agent
    assert "      DOCKER_HOST: tcp://docker-socket-proxy:2375" in agent
    assert "      - no-new-privileges:true" in agent
    assert "      - ALL" in agent

    dockerfile = (SATELLITE_ROOT / "implementations/docker/Dockerfile").read_text()
    assert "USER 10001:10001" in dockerfile
    assert 'CMD [".venv/bin/luml-satellite-docker"]' in dockerfile


def test_socket_proxy_is_private_and_allows_only_required_api_sections() -> None:
    compose = (SATELLITE_ROOT / "docker-compose.yml").read_text()
    proxy = compose.split("\n  docker-socket-proxy:\n", maxsplit=1)[1].split("\n  agent:\n")[0]

    assert "    ports:" not in proxy
    assert "      - /var/run/docker.sock:/var/run/docker.sock:ro" in proxy
    assert "      - docker-control" in proxy
    assert "satellite-network" not in proxy
    enabled = {
        line.strip().split(":")[0] for line in proxy.splitlines() if line.strip().endswith(': "1"')
    }
    assert enabled == {"CONTAINERS", "IMAGES", "NETWORKS", "VOLUMES", "POST", "PING", "VERSION"}
    assert '      EVENTS: "0"' in proxy
    networks = compose.split("\nvolumes:", maxsplit=1)[0]
    control = networks.split("\n  docker-control:\n", maxsplit=1)[1]
    assert "    internal: true" in control
    assert "df.model-access" not in control
    assert "      docker-control:" in compose.split("\n  agent:\n", maxsplit=1)[1]


def test_reverse_proxy_is_the_only_agent_http_host_binding() -> None:
    compose = (SATELLITE_ROOT / "docker-compose.yml").read_text()
    proxy = compose.split("\n  reverse-proxy:\n", maxsplit=1)[1].split(
        "\n  docker-socket-proxy:\n"
    )[0]

    assert "    image: caddy:2.10.2-alpine" in proxy
    assert '      - "${PROXY_BIND:-127.0.0.1}:80:80"' in proxy
    assert '      - "${PROXY_BIND:-127.0.0.1}:443:443"' in proxy
    assert "      SATELLITE_SITE: ${SATELLITE_DOMAIN:-:80}" in proxy
    assert "      - ./Caddyfile:/etc/caddy/Caddyfile:ro" in proxy
    assert "      - caddy-data:/data" in proxy
    assert not (SATELLITE_ROOT / "nginx.conf").exists()
    caddyfile = (SATELLITE_ROOT / "Caddyfile").read_text()
    assert "{$SATELLITE_SITE} {" in caddyfile
    assert "reverse_proxy agent:8000 {" in caddyfile
    assert "flush_interval -1" in caddyfile


def test_guide_compose_matches_the_repository_compose() -> None:
    repository = yaml.safe_load((SATELLITE_ROOT / "docker-compose.yml").read_text())
    guide = yaml.safe_load(guide_file("docker-compose.yml"))

    assert guide == compose_as_published(repository)


def test_guide_collector_and_proxy_configs_match_the_repository() -> None:
    assert (
        guide_file("otel-collector-config.yaml")
        == (SATELLITE_ROOT / "otel-collector-config.yaml").read_text()
    )
    assert guide_file("Caddyfile") == (SATELLITE_ROOT / "Caddyfile").read_text()


def test_guide_env_sets_every_required_compose_variable() -> None:
    required = set(re.findall(r"\$\{(\w+):\?", (SATELLITE_ROOT / "docker-compose.yml").read_text()))
    configured = set(re.findall(r"^(\w+)=\S", guide_file(".env"), flags=re.MULTILINE))

    assert required
    assert required <= configured
