from pathlib import Path
from typing import cast

import pytest
import yaml

from luml_demo import platform, satellites
from luml_demo.config import DemoConfig


def _override(loader: yaml.SafeLoader, node: yaml.Node) -> list[object]:
    return loader.construct_sequence(cast(yaml.SequenceNode, node))


yaml.SafeLoader.add_constructor("!override", _override)


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> DemoConfig:
    monkeypatch.setenv("LUML_DEMO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LUML_DEMO_API_PORT", "18000")
    monkeypatch.setenv("LUML_DEMO_WEB_PORT", "15173")
    monkeypatch.setenv("LUML_DEMO_MINIO_PORT", "19000")
    monkeypatch.setenv("LUML_DEMO_DOCKER_HOST_IP", "172.17.0.1")
    return DemoConfig()


def test_platform_override_moves_ports_and_urls(config: DemoConfig) -> None:
    rendered = yaml.safe_load(platform.render_override(config))
    services = rendered["services"]
    assert services["backend"]["ports"] == ["18000:8000"]
    assert services["frontend"]["ports"] == ["15173:5173"]
    assert services["minio"]["ports"] == ["19000:9000", f"{config.minio_console_port}:9001"]
    assert services["frontend"]["environment"]["VITE_API_URL"] == "http://localhost:18000"
    assert "http://localhost:15173" in services["backend"]["environment"]["CORS_ORIGINS"]
    assert services["seed"]["environment"]["DEV_BUCKET_ENDPOINT"] == "localhost:19000"
    assert "!override" in platform.render_override(config)


def test_satellite_compose_points_at_platform_and_publishes_ports(config: DemoConfig) -> None:
    spec = config.satellite("prod")
    rendered = yaml.safe_load(satellites.render_compose(config, spec))
    agent = rendered["services"]["agent"]["environment"]
    assert agent["PLATFORM_URL"] == "http://host.docker.internal:18000"
    assert agent["BASE_URL"] == f"http://localhost:{spec.port}"
    assert agent["MONITORING_FRAME_ANCESTORS"] == "http://localhost:15173"
    assert agent["MONITORING_BACKFILL_MAX_WINDOWS"] == satellites.MONITORING_BACKFILL_MAX_WINDOWS
    assert rendered["services"]["agent"]["ports"] == [f"{spec.port}:8000"]
    assert rendered["services"]["greptimedb"]["ports"] == [f"{spec.greptime_port}:4000"]
    assert rendered["services"]["otel-collector"]["ports"] == [f"{spec.otlp_port}:4317"]
    assert rendered["name"] == "luml-demo-sat-prod"


def test_write_stack_copies_collector_config_and_token(config: DemoConfig) -> None:
    spec = config.satellite("staging")
    directory = satellites.write_stack(config, spec, "dfssat_secret")
    assert (directory / "docker-compose.yml").exists()
    assert "inference_events" in (directory / "otel-collector-config.yaml").read_text()
    assert (directory / ".env").read_text() == "SATELLITE_TOKEN=dfssat_secret\n"


def test_bucket_endpoint_uses_docker_reachable_host(config: DemoConfig) -> None:
    assert config.bucket_endpoint_for_docker == "172.17.0.1:19000"
