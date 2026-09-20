import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from luml_satellite import PlatformClient
from luml_satellite.testing import FakePlatform

from luml_satellite_docker import DockerDriver
from luml_satellite_docker.main import build_runtime
from tests.support import (
    FakeDocker,
    close_runtime,
    configuration,
    upstream_transport,
)

INFERENCE_ACCESS_PATH = "/satellites/deployments/inference-access"
DEPLOYMENT_SCHEMA_PATH = "/deployments/{deployment_id}/openapi.json"


@pytest.mark.asyncio
async def test_docker_capabilities_remain_wire_identical() -> None:
    fake_platform = FakePlatform()
    config = configuration(MONITORING_ENABLED=True)

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            config,
            platform,
            DockerDriver(config, client=FakeDocker().as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            capabilities = runtime.capabilities
        finally:
            await close_runtime(runtime)

    assert capabilities == {
        "deploy": {
            "version": 1,
            "api_versions": [1],
            "facets": ["satellite", "deployment"],
            "supported_variants": ["pyfunc", "pipeline"],
            "supported_tags_combinations": None,
            "extra_fields_form_spec": [],
        },
        "monitoring": {
            "version": 1,
            "api_versions": [1],
            "facets": ["deployment:monitoring"],
            "features": [
                "runtime",
                "traces",
                "alerts",
                "data_quality",
                "feature_drift",
                "output_drift",
                "multivariate_drift",
            ],
        },
    }


@pytest.mark.asyncio
async def test_pairing_document_matches_snapshot_and_has_only_the_two_declared_changes() -> None:
    fake_platform = FakePlatform()
    config = configuration(MONITORING_ENABLED=True)
    driver = DockerDriver(config, client=FakeDocker().as_client())

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            config,
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
        finally:
            await close_runtime(runtime)

    request = next(item for item in fake_platform.requests if item.path == "/satellites/v1/pair")
    body = cast(dict[str, Any], request.body)
    document = cast(dict[str, Any], body["openapi"])
    snapshot = _read_json(Path(__file__).parent / "snapshots" / "static_openapi.json")
    old_document = _read_json(
        Path(__file__).parents[3] / "tests" / "snapshots" / "static_openapi.json"
    )
    expected = copy.deepcopy(old_document)
    expected["paths"][INFERENCE_ACCESS_PATH]["post"]["security"] = [{"HTTPBearer": []}]
    expected["paths"][DEPLOYMENT_SCHEMA_PATH] = document["paths"][DEPLOYMENT_SCHEMA_PATH]

    assert body["kit"] == {
        "name": "luml-satellite",
        "version": "0.1.0",
        "kind": "docker",
        "api_version": 1,
    }
    assert body["slug"] == "docker-2026.01-v2-debian12"
    assert body["base_url"] == "http://satellite"
    assert body["capabilities"] == runtime.capabilities
    assert document == snapshot
    assert document == expected
    assert driver.satellite_id == fake_platform.satellite_id
    compute = document["paths"]["/deployments/{deployment_id}/compute"]["post"]
    assert (
        compute["requestBody"]
        == old_document["paths"]["/deployments/{deployment_id}/compute"]["post"]["requestBody"]
    )
    assert (
        compute["responses"]
        == old_document["paths"]["/deployments/{deployment_id}/compute"]["post"]["responses"]
    )


@pytest.mark.asyncio
async def test_monitoring_disabled_advertises_only_deploy() -> None:
    fake_platform = FakePlatform()
    config = configuration(MONITORING_ENABLED=False)

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            config,
            platform,
            DockerDriver(config, client=FakeDocker().as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            assert set(runtime.capabilities) == {"deploy"}
        finally:
            await close_runtime(runtime)


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))
