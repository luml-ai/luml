import asyncio
from collections import defaultdict, deque
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import aiodocker
import httpx
import pytest
from aiodocker.exceptions import DockerError
from luml_satellite import (
    ArtifactDeliveryMode,
    ArtifactHandle,
    Deployment,
    RecordingPolicy,
    SatelliteRuntime,
    StartContext,
)

from luml_satellite_docker import DockerConfiguration, DockerDeploymentSettings

SATELLITE_ID = "00000000-0000-0000-0000-000000000001"
OTHER_SATELLITE_ID = "00000000-0000-0000-0000-000000000002"
DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000001"
OTHER_DEPLOYMENT_ID = "10000000-0000-0000-0000-000000000002"
ARTIFACT_ID = "20000000-0000-0000-0000-000000000001"


class FakeContainer:
    def __init__(
        self,
        owner: FakeContainers,
        name: str,
        config: Mapping[str, Any],
        *,
        status: str = "created",
        status_after_start: str = "running",
        logs: list[str] | None = None,
    ) -> None:
        self.owner = owner
        self.name = name
        self.config = dict(config)
        self.status = status
        self.status_after_start = status_after_start
        self.logs = list(logs or [])
        self.show_errors: deque[BaseException] = deque()
        self.networks: dict[str, list[str]] = {}
        self.start_count = 0
        self.delete_count = 0

    async def show(self) -> dict[str, Any]:
        if self.show_errors:
            raise self.show_errors.popleft()
        return {
            "Id": self.name,
            "Name": f"/{self.name}",
            "State": {
                "Status": self.status,
                "Running": self.status == "running",
            },
            "Config": {
                "Labels": dict(self.config.get("Labels") or {}),
                "Env": list(self.config.get("Env") or []),
            },
            "NetworkSettings": {
                "Networks": {
                    name: {"Aliases": list(aliases)} for name, aliases in self.networks.items()
                }
            },
        }

    async def start(self) -> None:
        self.start_count += 1
        self.status = self.status_after_start

    async def stop(self) -> None:
        self.status = "exited"

    async def delete(self, *, force: bool = False) -> None:
        del force
        self.delete_count += 1
        self.owner.deleted_names.append(self.name)
        if self.owner.containers.get(self.name) is self:
            del self.owner.containers[self.name]

    async def log(
        self,
        *,
        stdout: bool = False,
        stderr: bool = False,
        follow: bool = False,
        tail: int | None = None,
    ) -> list[str]:
        del stdout, stderr, follow
        return self.logs if tail is None else self.logs[-tail:]

    async def wait(self) -> dict[str, int]:
        return {"StatusCode": 0}


class FakeContainers:
    def __init__(self) -> None:
        self.containers: dict[str, FakeContainer] = {}
        self.get_effects: dict[str, deque[BaseException]] = defaultdict(deque)
        self.created_configs: list[tuple[str, dict[str, Any]]] = []
        self.deleted_names: list[str] = []
        self.next_status_after_start = "running"
        self.next_logs: list[str] = []
        self.active_creates = 0
        self.max_active_creates = 0
        self._unnamed = 0

    def add(
        self,
        name: str,
        *,
        status: str = "running",
        labels: Mapping[str, str] | None = None,
        logs: list[str] | None = None,
    ) -> FakeContainer:
        container = FakeContainer(
            self,
            name,
            {"Labels": dict(labels or {})},
            status=status,
            status_after_start=status,
            logs=logs,
        )
        self.containers[name] = container
        return container

    async def create_or_replace(
        self,
        name: str,
        config: dict[str, Any],
    ) -> FakeContainer:
        self.active_creates += 1
        self.max_active_creates = max(self.max_active_creates, self.active_creates)
        try:
            await asyncio.sleep(0)
            current = self.containers.get(name)
            if current is not None and current.config == config:
                return current
            if current is not None:
                await current.delete(force=True)
            container = FakeContainer(
                self,
                name,
                config,
                status_after_start=self.next_status_after_start,
                logs=self.next_logs,
            )
            self.next_status_after_start = "running"
            self.next_logs = []
            self.containers[name] = container
            self.created_configs.append((name, dict(config)))
            return container
        finally:
            self.active_creates -= 1

    async def create(
        self,
        config: dict[str, Any],
        *,
        name: str | None = None,
    ) -> FakeContainer:
        self._unnamed += 1
        resolved_name = name or f"cache-{self._unnamed}"
        container = FakeContainer(self, resolved_name, config)
        self.containers[resolved_name] = container
        self.created_configs.append((resolved_name, dict(config)))
        return container

    async def get(self, name: str) -> FakeContainer:
        if self.get_effects[name]:
            raise self.get_effects[name].popleft()
        try:
            return self.containers[name]
        except KeyError as error:
            raise DockerError(404, "No such container") from error

    async def list(self, *, all: bool = False) -> list[FakeContainer]:
        del all
        return list(self.containers.values())


class FakeVolume:
    def __init__(self, owner: FakeVolumes, name: str, *, in_use: bool = False) -> None:
        self.owner = owner
        self.name = name
        self.in_use = in_use

    async def delete(self, force: bool = False) -> None:
        del force
        if self.in_use:
            raise DockerError(409, "volume is in use")
        self.owner.deleted.append(self.name)
        self.owner.volumes.pop(self.name, None)


class FakeVolumes:
    def __init__(self) -> None:
        self.volumes: dict[str, FakeVolume] = {}
        self.deleted: list[str] = []

    def add(self, name: str, *, in_use: bool = False) -> FakeVolume:
        volume = FakeVolume(self, name, in_use=in_use)
        self.volumes[name] = volume
        return volume

    async def get(self, name: str) -> FakeVolume:
        try:
            return self.volumes[name]
        except KeyError as error:
            raise DockerError(404, "No such volume") from error

    async def list(self) -> dict[str, list[dict[str, str]]]:
        return {"Volumes": [{"Name": name} for name in self.volumes]}


class FakeImages:
    def __init__(self) -> None:
        self.available: set[str] = {"alpine:latest"}
        self.pulled: list[str] = []

    async def get(self, name: str) -> dict[str, str]:
        if name not in self.available:
            raise DockerError(404, "No such image")
        return {"Id": name}

    async def pull(self, name: str) -> None:
        self.available.add(name)
        self.pulled.append(name)


class FakeNetwork:
    def __init__(self, owner: FakeNetworks, name: str, config: dict[str, Any]) -> None:
        self.owner = owner
        self.name = name
        self.config = config
        self.connected: list[dict[str, Any]] = []

    async def connect(self, config: dict[str, Any]) -> None:
        container = self.owner.containers.containers.get(str(config.get("Container") or ""))
        if container is not None and self.name in container.networks:
            raise DockerError(403, "endpoint already exists in network")
        self.connected.append(config)
        if container is None:
            return
        endpoint = config.get("EndpointConfig") or {}
        container.networks[self.name] = list(endpoint.get("Aliases") or [])


class FakeNetworks:
    def __init__(self, containers: FakeContainers) -> None:
        self.containers = containers
        self.networks: dict[str, FakeNetwork] = {}
        self.created_configs: list[dict[str, Any]] = []

    async def get(self, name: str) -> FakeNetwork:
        try:
            return self.networks[name]
        except KeyError as error:
            raise DockerError(404, "No such network") from error

    async def create(self, config: dict[str, Any]) -> FakeNetwork:
        name = str(config["Name"])
        self.created_configs.append(config)
        network = FakeNetwork(self, name, config)
        self.networks[name] = network
        return network


class FakeDocker:
    def __init__(self) -> None:
        self.containers = FakeContainers()
        self.volumes = FakeVolumes()
        self.images = FakeImages()
        self.networks = FakeNetworks(self.containers)
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    def as_client(self) -> aiodocker.Docker:
        return cast(aiodocker.Docker, self)


def agent_container(
    fake: FakeDocker,
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str = "agent-host",
    labels: dict[str, str] | None = None,
    networks: dict[str, list[str]] | None = None,
) -> FakeContainer:
    container = FakeContainer(fake.containers, name, {"Labels": labels or {}})
    container.networks = dict(networks or {})
    fake.containers.containers[name] = container
    monkeypatch.setenv("HOSTNAME", name)
    return container


def configuration(**overrides: object) -> DockerConfiguration:
    values: dict[str, object] = {
        "SATELLITE_TOKEN": "test-token",
        "PLATFORM_URL": "http://platform",
        "BASE_URL": "http://satellite",
        "MONITORING_ENABLED": False,
        "HEALTH_CHECK_TIMEOUT_SEC": 30,
    }
    values.update(overrides)
    return DockerConfiguration.model_validate(values)


def deployment_record(**overrides: object) -> dict[str, Any]:
    now = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    record: dict[str, Any] = {
        "id": DEPLOYMENT_ID,
        "orbit_id": "30000000-0000-0000-0000-000000000001",
        "satellite_id": SATELLITE_ID,
        "satellite_name": "Docker satellite",
        "orbit_name": "Test environment",
        "name": "classifier",
        "artifact_id": ARTIFACT_ID,
        "artifact_name": "model.tar.gz",
        "collection_id": "40000000-0000-0000-0000-000000000001",
        "status": "pending",
        "monitoring_mode": "off",
        "satellite_parameters": {},
        "dynamic_attributes_secrets": {},
        "env_variables_secrets": {},
        "env_variables": {},
        "created_at": now,
    }
    record.update(overrides)
    return record


def deployment(**overrides: object) -> Deployment:
    return Deployment.model_validate(deployment_record(**overrides))


def start_context(**overrides: object) -> StartContext:
    values: dict[str, object] = {
        "settings": DockerDeploymentSettings(health_check_timeout=30),
        "secrets": {},
        "artifact": ArtifactHandle(
            artifact_id=ARTIFACT_ID,
            mode=ArtifactDeliveryMode.ON_DEMAND,
            refresh_url=f"http://satellite/satellites/deployments/{DEPLOYMENT_ID}/artifact",
            token="artifact-token",
        ),
        "telemetry_endpoint": "http://collector:4317",
        "health_check_timeout": 30,
        "recording_policy": RecordingPolicy(),
    }
    values.update(overrides)
    return StartContext(**values)  # type: ignore[arg-type]


def upstream_transport(*, healthy: bool = True) -> httpx.MockTransport:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200 if healthy else 503, json={"status": "healthy"})
        if request.url.path == "/manifest":
            return httpx.Response(200, json={"name": "fixture", "version": "1"})
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json={"openapi": "3.1.0", "paths": {}})
        if request.url.path == "/reference_profile":
            return httpx.Response(404)
        if request.url.path.endswith("/compute"):
            return httpx.Response(200, json={"prediction": 42})
        return httpx.Response(404)

    return httpx.MockTransport(handle)


class AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


async def close_runtime(runtime: SatelliteRuntime) -> None:
    await cast(AsyncCloseable, runtime.serving).aclose()
    if runtime.monitoring is not None:
        await cast(AsyncCloseable, runtime.monitoring).aclose()
