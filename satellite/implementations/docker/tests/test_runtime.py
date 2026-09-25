import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest
from luml_satellite import PlatformClient, TokenDeriver
from luml_satellite.container import (
    DOCKER_ARTIFACT_LABEL,
    DOCKER_DEPLOYMENT_LABEL,
    DOCKER_LAUNCHER_PROTOCOL_LABEL,
    DOCKER_SATELLITE_LABEL,
)
from luml_satellite.monitoring import MonitoringBundle
from luml_satellite.serving import InProcessServingPlacement
from luml_satellite.testing import FakePlatform, ScriptedDeployCase

from luml_satellite_docker import DockerDriver
from luml_satellite_docker.main import SLUG, build_runtime, run_async
from tests.support import (
    ARTIFACT_ID,
    DEPLOYMENT_ID,
    OTHER_DEPLOYMENT_ID,
    OTHER_SATELLITE_ID,
    SATELLITE_ID,
    FakeDocker,
    close_runtime,
    configuration,
    deployment_record,
    upstream_transport,
)


@pytest.mark.asyncio
async def test_scripted_deploy_reaches_the_same_status_sequence() -> None:
    fake_platform = FakePlatform()
    case = ScriptedDeployCase()
    case.seed(fake_platform)
    fake_docker = FakeDocker()

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = DockerDriver(configuration(), client=fake_docker.as_client())
        runtime = build_runtime(
            configuration(),
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await case.run_and_assert(runtime.polling, fake_platform)
        finally:
            await close_runtime(runtime)

    container = fake_docker.containers.containers[f"sat-{case.deployment_id}"]
    labels = cast(dict[str, str], container.config["Labels"])
    assert labels[DOCKER_SATELLITE_LABEL] == fake_platform.satellite_id
    assert labels[DOCKER_LAUNCHER_PROTOCOL_LABEL] == "4"
    assert fake_platform.deployments[case.deployment_id]["inference_url"] == (
        f"/deployments/{case.deployment_id}"
    )


@pytest.mark.asyncio
async def test_failed_container_logs_are_recorded_before_it_is_removed() -> None:
    fake_platform = FakePlatform()
    case = ScriptedDeployCase.workload_dies_before_healthy()
    case.seed(fake_platform)
    fake_docker = FakeDocker()
    fake_docker.containers.next_status_after_start = "exited"
    fake_docker.containers.next_logs = ["discarded-prefix-" + "x" * 1100 + "-tail"]

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = DockerDriver(configuration(), client=fake_docker.as_client())
        runtime = build_runtime(
            configuration(),
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await case.run_and_assert(runtime.polling, fake_platform)
        finally:
            await close_runtime(runtime)

    result = cast(dict[str, str], fake_platform.tasks[case.task_id]["result"])
    assert result["reason"] == "Container stopped or not found"
    assert result["error"].endswith("-tail")
    assert "discarded-prefix" not in result["error"]
    assert f"sat-{case.deployment_id}" not in fake_docker.containers.containers
    assert fake_docker.containers.deleted_names == [f"sat-{case.deployment_id}"]


@pytest.mark.asyncio
async def test_old_agent_container_is_relaunched_once_then_plainly_adopted() -> None:
    fake_platform = FakePlatform()
    fake_platform.add_deployment(deployment_record(status="active"))
    fake_docker = FakeDocker()
    fake_docker.containers.add(
        f"sat-{DEPLOYMENT_ID}",
        labels={
            DOCKER_DEPLOYMENT_LABEL: DEPLOYMENT_ID,
            DOCKER_ARTIFACT_LABEL: ARTIFACT_ID,
            DOCKER_LAUNCHER_PROTOCOL_LABEL: "3",
        },
    )
    config = configuration()

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        first_driver = DockerDriver(config, client=fake_docker.as_client())
        first = build_runtime(
            config,
            platform,
            first_driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await first.pair()
            await first.reconcile()
            marker = fake_platform.deployments[DEPLOYMENT_ID]
            assert marker["status"] == "not_responding"
            assert cast(dict[str, str], marker["error_message"])["reason"] == "Recovering"
            await first.poll()
            assert fake_platform.deployments[DEPLOYMENT_ID]["status"] == "active"
        finally:
            await close_runtime(first)

        created_after_upgrade = len(fake_docker.containers.created_configs)
        updates_before_restart = len(fake_platform.deployment_updates)
        second_driver = DockerDriver(config, client=fake_docker.as_client())
        second = build_runtime(
            config,
            platform,
            second_driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await second.pair()
            await second.reconcile()
        finally:
            await close_runtime(second)

    assert created_after_upgrade == 1
    assert len(fake_docker.containers.created_configs) == created_after_upgrade
    assert fake_docker.containers.deleted_names == [f"sat-{DEPLOYMENT_ID}"]
    labels = cast(
        dict[str, str],
        fake_docker.containers.containers[f"sat-{DEPLOYMENT_ID}"].config["Labels"],
    )
    assert labels[DOCKER_SATELLITE_LABEL] == SATELLITE_ID
    assert labels[DOCKER_LAUNCHER_PROTOCOL_LABEL] == "4"
    assert fake_platform.deployment_updates[updates_before_restart:] == [
        (DEPLOYMENT_ID, {"monitoring_url": None})
    ]


@pytest.mark.asyncio
async def test_container_without_a_launcher_protocol_is_relaunched() -> None:
    fake_platform = FakePlatform()
    fake_platform.add_deployment(deployment_record(status="active"))
    fake_docker = FakeDocker()
    fake_docker.containers.add(
        f"sat-{DEPLOYMENT_ID}",
        labels={
            DOCKER_DEPLOYMENT_LABEL: DEPLOYMENT_ID,
            DOCKER_ARTIFACT_LABEL: ARTIFACT_ID,
        },
    )

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            configuration(),
            platform,
            DockerDriver(configuration(), client=fake_docker.as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await runtime.reconcile()
        finally:
            await close_runtime(runtime)

    assert len(fake_docker.containers.created_configs) == 1
    assert fake_platform.deployments[DEPLOYMENT_ID]["status"] == "not_responding"


@pytest.mark.asyncio
async def test_two_satellites_leave_each_others_and_an_old_unknown_container_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    first_platform = FakePlatform(satellite_id=SATELLITE_ID)
    second_platform = FakePlatform(satellite_id=OTHER_SATELLITE_ID)
    first_platform.add_deployment(deployment_record(status="active"))
    second_platform.add_deployment(
        deployment_record(
            id=OTHER_DEPLOYMENT_ID,
            satellite_id=OTHER_SATELLITE_ID,
            status="active",
        )
    )
    fake_docker = FakeDocker()
    fake_docker.containers.add(
        f"sat-{DEPLOYMENT_ID}",
        labels=_labels(DEPLOYMENT_ID, SATELLITE_ID),
    )
    fake_docker.containers.add(
        f"sat-{OTHER_DEPLOYMENT_ID}",
        labels=_labels(OTHER_DEPLOYMENT_ID, OTHER_SATELLITE_ID),
    )
    fake_docker.containers.add(
        "sat-unknown",
        labels={DOCKER_DEPLOYMENT_LABEL: "unknown", DOCKER_LAUNCHER_PROTOCOL_LABEL: "2"},
    )
    caplog.set_level(logging.INFO, logger="luml_satellite.runtime")

    async with (
        PlatformClient(
            "http://platform-one",
            "test-token",
            transport=first_platform.transport,
        ) as first_client,
        PlatformClient(
            "http://platform-two",
            "test-token",
            transport=second_platform.transport,
        ) as second_client,
    ):
        first = build_runtime(
            configuration(PLATFORM_URL="http://platform-one"),
            first_client,
            DockerDriver(configuration(), client=fake_docker.as_client()),
            upstream_transport=upstream_transport(),
        )
        second = build_runtime(
            configuration(PLATFORM_URL="http://platform-two"),
            second_client,
            DockerDriver(configuration(), client=fake_docker.as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            await first.pair()
            await second.pair()
            await first.reconcile()
            await second.reconcile()
        finally:
            await close_runtime(first)
            await close_runtime(second)

    assert set(fake_docker.containers.containers) == {
        f"sat-{DEPLOYMENT_ID}",
        f"sat-{OTHER_DEPLOYMENT_ID}",
        "sat-unknown",
    }
    assert fake_docker.containers.deleted_names == []
    assert fake_docker.containers.created_configs == []
    assert "leaving foreign or shared workload 'unknown' untouched" in caplog.text


@pytest.mark.asyncio
async def test_running_deploy_task_resumes_from_the_existing_container() -> None:
    fake_platform = FakePlatform()
    case = ScriptedDeployCase()
    case.seed(fake_platform)
    fake_platform.tasks[case.task_id]["status"] = "running"
    fake_platform.tasks[case.task_id]["started_at"] = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    fake_docker = FakeDocker()
    fake_docker.containers.add(
        f"sat-{case.deployment_id}",
        labels=_labels(case.deployment_id, SATELLITE_ID, artifact_id=case.artifact_id),
    )

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            configuration(),
            platform,
            DockerDriver(configuration(), client=fake_docker.as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await runtime.reconcile()
        finally:
            await close_runtime(runtime)

    assert fake_platform.tasks[case.task_id]["status"] == "done"
    assert fake_platform.deployments[case.deployment_id]["status"] == "active"
    assert fake_docker.containers.created_configs == []


@pytest.mark.asyncio
async def test_main_composition_pairs_reconciles_and_serves_against_the_fake_platform() -> None:
    fake_platform = FakePlatform()
    fake_platform.allowed_api_keys.add("access-key")
    fake_docker = FakeDocker()

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        driver = DockerDriver(configuration(), client=fake_docker.as_client())
        runtime = build_runtime(
            configuration(),
            platform,
            driver,
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            application = cast(Any, runtime.public_application)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://satellite",
            ) as client:
                gated = await client.get(
                    "/deployments",
                    headers={"Authorization": "Bearer access-key"},
                )
                live = await client.get("/livez")
                inference_access = await client.post(
                    "/satellites/deployments/inference-access",
                    json={"api_key": "access-key"},
                )
            await runtime.reconcile()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://satellite",
            ) as client:
                response = await client.get(
                    "/deployments",
                    headers={"Authorization": "Bearer access-key"},
                )
        finally:
            await close_runtime(runtime)

    pair_request = next(
        request for request in fake_platform.requests if request.path == "/satellites/v1/pair"
    )
    body = cast(dict[str, Any], pair_request.body)
    assert gated.status_code == 503
    assert live.status_code == 200
    assert inference_access.status_code == 403
    assert response.status_code == 200
    assert response.json() == []
    assert driver.satellite_id == fake_platform.satellite_id
    assert body["slug"] == SLUG
    assert body["kit"]["kind"] == "docker"
    assert body["base_url"] == "http://satellite"
    assert isinstance(body["openapi"], dict)


@pytest.mark.asyncio
async def test_main_returns_when_the_http_server_exits_before_the_runtime_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ImmediatelyStoppedServer:
        def __init__(self, config: object) -> None:
            del config
            self.started = False
            self.should_exit = False

        async def serve(self) -> None:
            self.started = True

    fake_platform = FakePlatform()
    monkeypatch.setattr("luml_satellite_docker.main.uvicorn.Server", ImmediatelyStoppedServer)

    async with asyncio.timeout(1):
        await run_async(
            configuration(),
            docker_client=FakeDocker().as_client(),
            platform_transport=fake_platform.transport,
        )


@pytest.mark.asyncio
async def test_main_pairs_and_reconciles_against_the_fake_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_platform = FakePlatform()

    class ReconciledServer:
        def __init__(self, config: object) -> None:
            del config
            self.started = False
            self.should_exit = False

        async def serve(self) -> None:
            self.started = True
            while not _has_request(fake_platform, "GET", "/satellites/v1/tasks", "running"):
                await asyncio.sleep(0)

    monkeypatch.setattr("luml_satellite_docker.main.uvicorn.Server", ReconciledServer)

    async with asyncio.timeout(1):
        await run_async(
            configuration(),
            docker_client=FakeDocker().as_client(),
            platform_transport=fake_platform.transport,
        )

    assert _has_request(fake_platform, "POST", "/satellites/v1/pair")
    assert _has_request(fake_platform, "GET", "/satellites/v1/deployments")


@pytest.mark.asyncio
async def test_composed_artifact_and_compute_routes_keep_the_existing_contract() -> None:
    fake_platform = FakePlatform()
    case = ScriptedDeployCase()
    case.seed(fake_platform, monitoring_mode="full")
    fake_platform.allowed_api_keys.add("access-key")
    fake_docker = FakeDocker()
    config = configuration(MONITORING_ENABLED=True)

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            config,
            platform,
            DockerDriver(config, client=fake_docker.as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await runtime.reconcile()
            await case.run_and_assert(runtime.polling, fake_platform)
            application = cast(Any, runtime.public_application)
            token = TokenDeriver(config.SATELLITE_TOKEN).artifact_token(case.deployment_id)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://satellite",
            ) as client:
                artifact = await client.get(
                    f"/satellites/deployments/{case.deployment_id}/artifact",
                    headers={"X-Artifact-Token": token},
                )
                compute = await client.post(
                    f"/deployments/{case.deployment_id}/compute",
                    headers={"Authorization": "Bearer access-key"},
                    json={"feature": 1},
                )
                schema = await client.get(
                    f"/deployments/{case.deployment_id}/openapi.json",
                    headers={"Authorization": "Bearer access-key"},
                )
        finally:
            await close_runtime(runtime)

    assert artifact.status_code == 200
    assert artifact.json()["artifact_id"] == case.artifact_id
    assert compute.status_code == 200
    assert compute.json() == {"prediction": 42}
    assert compute.headers["x-event-id"]
    assert schema.status_code == 200
    assert schema.json() == {"openapi": "3.1.0", "paths": {}}
    placement = cast(InProcessServingPlacement, runtime.serving)
    local = placement.get_deployment(case.deployment_id)
    assert local is not None
    assert local.metadata.name == "scripted-deployment"
    assert local.metadata.status == "active"


@pytest.mark.asyncio
async def test_listing_uses_the_all_in_one_monitoring_workers_last_window() -> None:
    fake_platform = FakePlatform()
    case = ScriptedDeployCase()
    case.seed(fake_platform, monitoring_mode="full")
    fake_platform.allowed_api_keys.add("access-key")
    fake_docker = FakeDocker()
    config = configuration(MONITORING_ENABLED=True)
    window_end = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)

    async with PlatformClient(
        "http://platform",
        "test-token",
        transport=fake_platform.transport,
    ) as platform:
        runtime = build_runtime(
            config,
            platform,
            DockerDriver(config, client=fake_docker.as_client()),
            upstream_transport=upstream_transport(),
        )
        try:
            await runtime.pair()
            await runtime.reconcile()
            await case.run_and_assert(runtime.polling, fake_platform)
            monitoring = cast(MonitoringBundle, runtime.monitoring)
            monitoring.worker_health.window_processed(
                case.deployment_id,
                window_end,
                window_end,
            )
            application = cast(Any, runtime.public_application)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://satellite",
            ) as client:
                response = await client.get(
                    "/deployments",
                    headers={"Authorization": "Bearer access-key"},
                )
        finally:
            await close_runtime(runtime)

    assert response.status_code == 200
    assert response.json() == [
        {
            "deployment_id": case.deployment_id,
            "name": "scripted-deployment",
            "status": "active",
            "monitoring_mode": "full",
            "last_monitored_at": window_end.isoformat().replace("+00:00", "Z"),
        }
    ]


def _labels(
    deployment_id: str,
    satellite_id: str,
    *,
    artifact_id: str = ARTIFACT_ID,
) -> dict[str, str]:
    return {
        DOCKER_DEPLOYMENT_LABEL: deployment_id,
        DOCKER_ARTIFACT_LABEL: artifact_id,
        DOCKER_SATELLITE_LABEL: satellite_id,
        DOCKER_LAUNCHER_PROTOCOL_LABEL: "4",
    }


def _has_request(
    platform: FakePlatform,
    method: str,
    path: str,
    status: str | None = None,
) -> bool:
    return any(
        request.method == method
        and request.path == path
        and (status is None or request.query == {"status": [status]})
        for request in platform.requests
    )
