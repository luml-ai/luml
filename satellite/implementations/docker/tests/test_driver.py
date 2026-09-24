import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aiodocker.exceptions import DockerError
from luml_satellite import (
    DriverError,
    StartStatus,
    UnsupportedOperation,
    WorkloadState,
    settings_fields,
)
from luml_satellite.container import (
    DOCKER_ARTIFACT_LABEL,
    DOCKER_DEPLOYMENT_LABEL,
    DOCKER_LAUNCHER_PROTOCOL_LABEL,
    DOCKER_SATELLITE_LABEL,
)
from luml_satellite.testing import DriverConformanceSuite

from luml_satellite_docker import (
    DockerConfiguration,
    DockerDeploymentSettings,
    DockerDriver,
    model_cache_volume,
)
from tests.support import (
    ARTIFACT_ID,
    DEPLOYMENT_ID,
    OTHER_DEPLOYMENT_ID,
    OTHER_SATELLITE_ID,
    SATELLITE_ID,
    FakeContainer,
    FakeDocker,
    configuration,
    deployment,
    start_context,
)


def test_configuration_keeps_field_install_defaults_and_settings_hidden() -> None:
    config = DockerConfiguration.model_validate(
        {"SATELLITE_TOKEN": "configured", "MONITORING_ENABLED": False}
    )

    assert config.BASE_URL == "http://localhost"
    assert config.MODEL_IMAGE == "luml-random-svc:latest"
    assert config.MODEL_SERVER_PORT == 8080
    assert config.DOCKER_NETWORK_NAME == ""
    assert config.DERIVATION_KEY is None
    assert settings_fields(DockerDeploymentSettings) == []


@pytest.mark.asyncio
async def test_models_join_the_stack_their_satellite_belongs_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeDocker()
    fake.containers.containers["agent-host"] = FakeContainer(
        fake.containers,
        "agent-host",
        {"Labels": {"com.docker.compose.project": "sat-a"}},
    )
    monkeypatch.setenv("HOSTNAME", "agent-host")
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    await driver.start(deployment(), start_context())

    _, container_config = fake.containers.created_configs[-1]
    assert container_config["Labels"]["com.docker.compose.project"] == "sat-a"
    assert container_config["Labels"]["com.docker.compose.service"] == "model"
    assert container_config["Labels"][DOCKER_SATELLITE_LABEL] == SATELLITE_ID


@pytest.mark.asyncio
async def test_a_satellite_outside_a_stack_labels_nothing_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeDocker()
    monkeypatch.setenv("HOSTNAME", "not-a-container")
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    await driver.start(deployment(), start_context())

    _, container_config = fake.containers.created_configs[-1]
    assert set(container_config["Labels"]) == {
        DOCKER_DEPLOYMENT_LABEL,
        DOCKER_ARTIFACT_LABEL,
        DOCKER_SATELLITE_LABEL,
        DOCKER_LAUNCHER_PROTOCOL_LABEL,
    }


@pytest.mark.asyncio
async def test_start_creates_a_network_named_after_the_satellite() -> None:
    fake = FakeDocker()
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    await driver.start(deployment(), start_context())

    expected = f"luml-satellite-{SATELLITE_ID}"
    assert [config["Name"] for config in fake.networks.created_configs] == [expected]
    assert fake.networks.created_configs[0]["Labels"] == {DOCKER_SATELLITE_LABEL: SATELLITE_ID}
    _, container_config = fake.containers.created_configs[-1]
    assert container_config["HostConfig"]["NetworkMode"] == expected
    environment = dict(entry.split("=", 1) for entry in container_config["Env"])
    assert environment["SATELLITE_AGENT_URL"] == f"http://satellite-agent-{SATELLITE_ID}:8000"


@pytest.mark.asyncio
async def test_two_satellites_never_share_a_network_or_an_address() -> None:
    fake = FakeDocker()
    first = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)
    second = DockerDriver(configuration(), client=fake.as_client(), satellite_id=OTHER_SATELLITE_ID)

    await first.start(deployment(), start_context())
    await second.start(
        deployment(id=OTHER_DEPLOYMENT_ID, satellite_id=OTHER_SATELLITE_ID), start_context()
    )

    networks = [config["Name"] for config in fake.networks.created_configs]
    assert networks == [
        f"luml-satellite-{SATELLITE_ID}",
        f"luml-satellite-{OTHER_SATELLITE_ID}",
    ]
    addresses = {
        dict(entry.split("=", 1) for entry in container_config["Env"])["SATELLITE_AGENT_URL"]
        for _, container_config in fake.containers.created_configs
    }
    assert len(addresses) == 2


@pytest.mark.asyncio
async def test_an_existing_network_is_reused_and_created_once() -> None:
    fake = FakeDocker()
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)
    await fake.networks.create({"Name": f"luml-satellite-{SATELLITE_ID}"})
    fake.networks.created_configs.clear()

    await driver.start(deployment(), start_context())
    await driver.start(deployment(id=OTHER_DEPLOYMENT_ID), start_context())

    assert fake.networks.created_configs == []


@pytest.mark.asyncio
async def test_start_builds_the_protocol_three_container_on_the_configured_network() -> None:
    fake = FakeDocker()
    config = configuration(DOCKER_NETWORK_NAME="customer_satellite-network", AGENT_PORT=8123)
    driver = DockerDriver(config, client=fake.as_client(), satellite_id=SATELLITE_ID)
    record = deployment(
        env_variables={"PLAIN": "value", "SHARED": "plain", "MODEL_NAME": "ignored"}
    )
    context = start_context(secrets={"SECRET": "resolved", "SHARED": "secret"})

    result = await driver.start(record, context)

    assert result.status is StartStatus.IN_PROGRESS
    assert result.upstream_url == f"http://sat-{DEPLOYMENT_ID}:8080"
    name, container_config = fake.containers.created_configs[-1]
    assert name == f"sat-{DEPLOYMENT_ID}"
    assert container_config["HostConfig"] == {
        "RestartPolicy": {"Name": "on-failure", "MaximumRetryCount": 3},
        "NetworkMode": "customer_satellite-network",
        "Binds": [f"{model_cache_volume(ARTIFACT_ID)}:/app/models"],
    }
    assert container_config["Labels"] == {
        DOCKER_DEPLOYMENT_LABEL: DEPLOYMENT_ID,
        DOCKER_ARTIFACT_LABEL: ARTIFACT_ID,
        DOCKER_SATELLITE_LABEL: SATELLITE_ID,
        DOCKER_LAUNCHER_PROTOCOL_LABEL: "3",
    }
    environment = dict(entry.split("=", 1) for entry in container_config["Env"])
    assert environment == {
        "SECRET": "resolved",
        "SHARED": "plain",
        "PLAIN": "value",
        "MODEL_NAME": "model.tar.gz",
        "MODEL_ARTIFACT_ID": ARTIFACT_ID,
        "DEPLOYMENT_ID": DEPLOYMENT_ID,
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4317",
        "MODEL_ARTIFACT_TOKEN": "artifact-token",
        "SATELLITE_AGENT_URL": f"http://satellite-agent-{SATELLITE_ID}:8123",
    }


@pytest.mark.asyncio
async def test_start_names_a_missing_image_and_refuses_a_foreign_deployment() -> None:
    fake = FakeDocker()
    create = AsyncMock(side_effect=DockerError(404, "No such image"))
    cast(Any, fake.containers).create_or_replace = create
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    with pytest.raises(DriverError, match="not found") as missing:
        await driver.start(deployment(), start_context())

    assert missing.value.reason == "Docker image not found"

    with pytest.raises(DriverError, match="another satellite"):
        await driver.start(
            deployment(satellite_id=OTHER_SATELLITE_ID),
            start_context(),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("docker_state", "expected"),
    [
        ("running", WorkloadState.READY),
        ("created", WorkloadState.STARTING),
        ("restarting", WorkloadState.STARTING),
        ("exited", WorkloadState.STOPPED),
        ("paused", WorkloadState.STOPPED),
        ("dead", WorkloadState.STOPPED),
        ("removing", WorkloadState.STOPPED),
    ],
)
async def test_observe_maps_every_docker_state_and_the_catch_all(
    docker_state: str,
    expected: WorkloadState,
) -> None:
    fake = FakeDocker()
    logs = [f"line-{index}\n" for index in range(120)]
    fake.containers.add(
        f"sat-{DEPLOYMENT_ID}",
        status=docker_state,
        labels={DOCKER_LAUNCHER_PROTOCOL_LABEL: "old"},
        logs=logs,
    )
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is expected
    assert observation.launcher_protocol == "old"
    assert observation.upstream_url == f"http://sat-{DEPLOYMENT_ID}:8080"
    assert observation.recent_logs == ("".join(logs[-100:]) if docker_state == "exited" else "")


@pytest.mark.asyncio
async def test_observe_distinguishes_missing_from_an_unknown_daemon_answer() -> None:
    fake = FakeDocker()
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    driver = DockerDriver(
        configuration(),
        client=fake.as_client(),
        satellite_id=SATELLITE_ID,
        sleep=sleep,
    )

    missing = await driver.observe(DEPLOYMENT_ID)
    for _ in range(3):
        fake.containers.get_effects[f"sat-{DEPLOYMENT_ID}"].append(DockerError(500, "daemon busy"))
    unknown = await driver.observe(DEPLOYMENT_ID)

    assert missing.state is WorkloadState.MISSING
    assert unknown.state is WorkloadState.UNKNOWN
    assert "daemon busy" in (unknown.error or "")
    assert sleeps == [1.0, 1.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transient_error",
    [
        DockerError(500, "daemon busy"),
        TimeoutError("daemon timed out"),
        aiohttp.ClientConnectionError("socket closed"),
        OSError("connection reset"),
    ],
)
async def test_observe_retries_transient_lookup_and_status_errors(
    transient_error: BaseException,
) -> None:
    fake = FakeDocker()
    container = fake.containers.add(f"sat-{DEPLOYMENT_ID}")
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    fake.containers.get_effects[f"sat-{DEPLOYMENT_ID}"].append(transient_error)
    container.show_errors.append(transient_error)
    driver = DockerDriver(
        configuration(),
        client=fake.as_client(),
        satellite_id=SATELLITE_ID,
        sleep=sleep,
    )

    after_lookup_error = await driver.observe(DEPLOYMENT_ID)
    after_status_error = await driver.observe(DEPLOYMENT_ID)

    assert after_lookup_error.state is WorkloadState.READY
    assert after_status_error.state is WorkloadState.READY
    assert sleeps == [1.0, 1.0]


@pytest.mark.asyncio
async def test_observe_treats_a_container_removed_during_status_read_as_missing() -> None:
    fake = FakeDocker()
    container = fake.containers.add(f"sat-{DEPLOYMENT_ID}")
    container.show_errors.append(DockerError(404, "No such container"))
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    observation = await driver.observe(DEPLOYMENT_ID)

    assert observation.state is WorkloadState.MISSING


@pytest.mark.asyncio
async def test_listing_marks_only_this_satellites_labelled_containers_as_owned() -> None:
    fake = FakeDocker()
    own_labels = {
        DOCKER_DEPLOYMENT_LABEL: DEPLOYMENT_ID,
        DOCKER_SATELLITE_LABEL: SATELLITE_ID,
    }
    other_labels = {
        DOCKER_DEPLOYMENT_LABEL: OTHER_DEPLOYMENT_ID,
        DOCKER_SATELLITE_LABEL: OTHER_SATELLITE_ID,
    }
    old_labels = {DOCKER_DEPLOYMENT_LABEL: "legacy-deployment"}
    fake.containers.add(f"sat-{DEPLOYMENT_ID}", labels=own_labels)
    fake.containers.add(f"sat-{OTHER_DEPLOYMENT_ID}", labels=other_labels)
    fake.containers.add("sat-legacy-deployment", labels=old_labels)
    fake.containers.add("unrelated", labels=own_labels)
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    workloads = await driver.list_workloads()

    assert [(item.deployment_id, item.owned, item.shared) for item in workloads] == [
        (DEPLOYMENT_ID, True, False),
        (OTHER_DEPLOYMENT_ID, False, False),
        ("legacy-deployment", False, False),
    ]


@pytest.mark.asyncio
async def test_remove_captures_the_artifact_and_verifies_the_container_is_gone() -> None:
    fake = FakeDocker()
    fake.containers.add(
        f"sat-{DEPLOYMENT_ID}",
        labels={DOCKER_ARTIFACT_LABEL: ARTIFACT_ID},
    )
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    result = await driver.remove(DEPLOYMENT_ID)
    second = await driver.remove(DEPLOYMENT_ID)

    assert result.removed is True
    assert result.verified is True
    assert result.artifact_id == ARTIFACT_ID
    assert second.removed is False
    assert second.verified is True
    assert driver.removal_rechecks == 2


@pytest.mark.asyncio
async def test_release_and_sweep_preserve_referenced_or_mounted_cache_volumes() -> None:
    fake = FakeDocker()
    kept = model_cache_volume(ARTIFACT_ID)
    mounted = model_cache_volume("mounted")
    stale = model_cache_volume("stale")
    fake.volumes.add(kept)
    fake.volumes.add(mounted, in_use=True)
    fake.volumes.add(stale)
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    await driver.release_artifact(ARTIFACT_ID, still_referenced=True)
    await driver.sweep({ARTIFACT_ID})

    assert set(fake.volumes.volumes) == {kept, mounted}
    assert fake.volumes.deleted == [stale]
    cache_containers = [
        config for name, config in fake.containers.created_configs if name.startswith("cache-")
    ]
    assert len(cache_containers) == 1
    assert cache_containers[0]["Image"] == "alpine:latest"
    assert cache_containers[0]["Cmd"][:2] == ["sh", "-c"]
    assert cache_containers[0]["HostConfig"] == {
        "Binds": [
            f"{kept}:/sweep/{kept}",
            f"{mounted}:/sweep/{mounted}",
        ]
    }
    sweep = fake.containers.containers.get("cache-1")
    assert sweep is None


@pytest.mark.asyncio
async def test_release_deletes_only_an_unreferenced_existing_cache_volume() -> None:
    fake = FakeDocker()
    referenced = model_cache_volume("referenced")
    unused = model_cache_volume("unused")
    mounted = model_cache_volume("mounted")
    fake.volumes.add(referenced)
    fake.volumes.add(unused)
    fake.volumes.add(mounted, in_use=True)
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    await driver.release_artifact("referenced", still_referenced=True)
    await driver.release_artifact("unused", still_referenced=False)
    await driver.release_artifact("mounted", still_referenced=False)
    await driver.release_artifact("missing", still_referenced=False)

    assert set(fake.volumes.volumes) == {referenced, mounted}
    assert fake.volumes.deleted == [unused]


@pytest.mark.asyncio
async def test_driver_passes_the_conformance_suite() -> None:
    fake = FakeDocker()
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)
    suite = DriverConformanceSuite(
        driver,
        removal_recheck_count=lambda: driver.removal_rechecks,
    )

    await suite.run(deployment(), start_context())

    assert driver.removal_rechecks == 1


@pytest.mark.asyncio
async def test_independent_deployments_can_start_in_parallel() -> None:
    fake = FakeDocker()
    driver = DockerDriver(configuration(), client=fake.as_client(), satellite_id=SATELLITE_ID)

    await asyncio.gather(
        driver.start(deployment(), start_context()),
        driver.start(
            deployment(id=OTHER_DEPLOYMENT_ID, artifact_id="artifact-two"),
            start_context(),
        ),
    )

    assert fake.containers.max_active_creates == 2
    assert set(fake.containers.containers) == {
        f"sat-{DEPLOYMENT_ID}",
        f"sat-{OTHER_DEPLOYMENT_ID}",
    }


@pytest.mark.asyncio
async def test_bulk_observe_is_explicitly_unsupported() -> None:
    driver = DockerDriver(
        configuration(),
        client=FakeDocker().as_client(),
        satellite_id=SATELLITE_ID,
    )

    result = await driver.observe_all({DEPLOYMENT_ID})

    assert isinstance(result, UnsupportedOperation)
