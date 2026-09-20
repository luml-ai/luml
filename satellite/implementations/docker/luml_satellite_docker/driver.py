import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence, Set
from contextlib import suppress
from types import TracebackType
from typing import Any, Self, cast

import aiodocker
import aiohttp
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError
from luml_satellite import (
    UNSUPPORTED,
    ArtifactDeliveryMode,
    Deployment,
    DriverError,
    ListedWorkload,
    RemoveResult,
    StartContext,
    StartResult,
    StartStatus,
    UnsupportedOperation,
    WorkloadObservation,
    WorkloadState,
    build_container_environment,
    docker_labels,
)
from luml_satellite.container import (
    DOCKER_ARTIFACT_LABEL,
    DOCKER_DEPLOYMENT_LABEL,
    DOCKER_LAUNCHER_PROTOCOL_LABEL,
    DOCKER_SATELLITE_LABEL,
)

from luml_satellite_docker.configuration import DockerConfiguration
from luml_satellite_docker.settings import DockerDeploymentSettings

MODEL_CACHE_MOUNT = "/app/models"
MODEL_CACHE_VOLUME_PREFIX = "satellite-model-cache-"
LEGACY_MODEL_CACHE_VOLUME = "satellite-models-cache"
AGENT_HOST = "satellite-agent"
STALE_STAGING_MINUTES = 180

type Sleep = Callable[[float], Awaitable[None]]


def model_cache_volume(artifact_id: str) -> str:
    return f"{MODEL_CACHE_VOLUME_PREFIX}{artifact_id}"


class DockerDriver:
    kind: str = "docker"
    launcher_protocol: str = "3"
    supported_variants: Sequence[str] = ("pyfunc", "pipeline")
    supported_tag_combinations: Sequence[Sequence[str]] | None = None
    settings_type: type[DockerDeploymentSettings] = DockerDeploymentSettings
    artifact_delivery: ArtifactDeliveryMode = ArtifactDeliveryMode.ON_DEMAND
    inspect_attempts: int = 3

    def __init__(
        self,
        configuration: DockerConfiguration,
        *,
        client: aiodocker.Docker | None = None,
        satellite_id: str | None = None,
        sleep: Sleep = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self.configuration = configuration
        self.client = client or aiodocker.Docker()
        self.satellite_id = satellite_id
        self._owns_client = client is None
        self._sleep = sleep
        self._logger = logger or logging.getLogger("luml_satellite_docker.driver")
        self.removal_rechecks = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.close()

    def bind_satellite(self, satellite_id: str) -> None:
        if not satellite_id:
            raise ValueError("satellite_id must not be empty")
        self.satellite_id = satellite_id

    async def start(self, deployment: Deployment, context: StartContext) -> StartResult:
        satellite_id = self._satellite_id_for(deployment)
        deployment_id = str(deployment.id)
        artifact_id = str(deployment.artifact_id)
        satellite_address = f"http://{AGENT_HOST}:{self.configuration.AGENT_PORT}"
        environment = build_container_environment(
            deployment,
            context.secrets,
            telemetry_endpoint=context.telemetry_endpoint,
            artifact_token=context.artifact.token,
            satellite_address=satellite_address,
            logger=self._logger,
        )
        container_config: dict[str, Any] = {
            "Image": self.configuration.MODEL_IMAGE,
            "Labels": docker_labels(
                deployment_id=deployment_id,
                artifact_id=artifact_id,
                satellite_id=satellite_id,
                launcher_protocol=self.launcher_protocol,
            ),
            "ExposedPorts": {f"{self.configuration.MODEL_SERVER_PORT}/tcp": {}},
            "Env": [f"{name}={value}" for name, value in environment.items()],
            "HostConfig": {
                "RestartPolicy": {"Name": "on-failure", "MaximumRetryCount": 3},
                "NetworkMode": self.configuration.DOCKER_NETWORK_NAME,
                "Binds": [f"{model_cache_volume(artifact_id)}:{MODEL_CACHE_MOUNT}"],
            },
        }
        try:
            container = await self.client.containers.create_or_replace(
                name=self._container_name(deployment_id),
                config=container_config,
            )
            information = await container.show()
            if not _container_is_running(information):
                await container.start()
        except DockerError as error:
            if error.status == 404:
                raise DriverError(
                    f"Image '{self.configuration.MODEL_IMAGE}' not found. "
                    "Please ensure the image is built or pulled on the satellite.",
                    reason="Docker image not found",
                ) from error
            raise

        return StartResult(
            StartStatus.IN_PROGRESS,
            upstream_url=self._upstream_url(deployment_id),
        )

    async def observe(self, deployment_id: str) -> WorkloadObservation:
        last_error: BaseException | None = None
        for attempt in range(1, self.inspect_attempts + 1):
            try:
                container = await self.client.containers.get(self._container_name(deployment_id))
                information = await container.show()
            except (DockerError, aiohttp.ClientError, TimeoutError, OSError) as error:
                if _docker_status(error) == 404:
                    return WorkloadObservation(WorkloadState.MISSING)
                last_error = error
                if attempt < self.inspect_attempts:
                    self._logger.warning(
                        "inspecting '%s' failed (attempt %d/%d): %s",
                        self._container_name(deployment_id),
                        attempt,
                        self.inspect_attempts,
                        error,
                    )
                    await self._sleep(1.0)
                    continue
                break

            state = str(_mapping(information.get("State")).get("Status", ""))
            labels = _string_mapping(_mapping(information.get("Config")).get("Labels"))
            upstream_url = self._upstream_url(deployment_id)
            launcher_protocol = labels.get(DOCKER_LAUNCHER_PROTOCOL_LABEL)
            if state == "running":
                return WorkloadObservation(
                    WorkloadState.READY,
                    upstream_url=upstream_url,
                    launcher_protocol=launcher_protocol,
                )
            if state in {"created", "restarting"}:
                return WorkloadObservation(
                    WorkloadState.STARTING,
                    upstream_url=upstream_url,
                    launcher_protocol=launcher_protocol,
                )
            logs = await self._recent_logs(container) if state == "exited" else ""
            return WorkloadObservation(
                WorkloadState.STOPPED,
                error=f"Container '{deployment_id}' is not running (status: {state or 'unknown'})",
                recent_logs=logs,
                upstream_url=upstream_url,
                launcher_protocol=launcher_protocol,
            )

        return WorkloadObservation(
            WorkloadState.UNKNOWN,
            error=f"Docker inspection failed: {last_error}",
        )

    async def observe_all(
        self,
        deployment_ids: Set[str],
    ) -> UnsupportedOperation:
        del deployment_ids
        return UNSUPPORTED

    async def remove(self, deployment_id: str) -> RemoveResult:
        artifact_id: str | None = None
        removed = False
        try:
            container = await self.client.containers.get(self._container_name(deployment_id))
            information = await container.show()
            labels = _string_mapping(_mapping(information.get("Config")).get("Labels"))
            artifact_id = labels.get(DOCKER_ARTIFACT_LABEL)
            await container.delete(force=True)
            removed = True
        except DockerError as error:
            if error.status != 404:
                raise

        self.removal_rechecks += 1
        observation = await self.observe(deployment_id)
        return RemoveResult(
            removed=removed,
            verified=observation.state is WorkloadState.MISSING,
            artifact_id=artifact_id,
        )

    async def list_workloads(self) -> list[ListedWorkload]:
        containers = await self.client.containers.list(all=True)
        workloads: list[ListedWorkload] = []
        for container in containers:
            try:
                information = await container.show()
            except DockerError as error:
                if error.status == 404:
                    continue
                raise
            name = _docker_container_name(information)
            if name is None or not name.startswith("sat-"):
                continue
            labels = _string_mapping(_mapping(information.get("Config")).get("Labels"))
            deployment_id = labels.get(DOCKER_DEPLOYMENT_LABEL)
            workloads.append(
                ListedWorkload(
                    deployment_id=deployment_id,
                    owned=(
                        deployment_id is not None
                        and self.satellite_id is not None
                        and labels.get(DOCKER_SATELLITE_LABEL) == self.satellite_id
                    ),
                    shared=False,
                )
            )
        return workloads

    async def release_artifact(self, artifact_id: str, still_referenced: bool) -> None:
        if still_referenced:
            return
        volume_name = model_cache_volume(artifact_id)
        try:
            volume = await cast(Any, self.client.volumes).get(volume_name)
            await volume.delete()
            self._logger.info("removed unused model cache volume '%s'", volume_name)
        except DockerError as error:
            if error.status == 409:
                self._logger.info("model cache volume '%s' is still in use", volume_name)
            elif error.status != 404:
                raise

    async def sweep(self, artifact_ids: Set[str]) -> None:
        try:
            listed = await cast(Any, self.client.volumes).list()
        except DockerError as error:
            self._logger.error("could not list cache volumes: %s", error)
            return

        names = [
            str(volume.get("Name", ""))
            for volume in listed.get("Volumes") or []
            if isinstance(volume, dict)
        ]
        candidates = [
            name
            for name in names
            if name.startswith(MODEL_CACHE_VOLUME_PREFIX) or name == LEGACY_MODEL_CACHE_VOLUME
        ]
        keep = {model_cache_volume(artifact_id) for artifact_id in artifact_ids if artifact_id}
        mounted: list[str] = []
        for name in candidates:
            if name in keep:
                mounted.append(name)
                continue
            try:
                volume = await cast(Any, self.client.volumes).get(name)
                await volume.delete()
                self._logger.info("removed unused model cache volume '%s'", name)
            except DockerError as error:
                if error.status == 409:
                    mounted.append(name)
                elif error.status != 404:
                    self._logger.error("could not remove volume '%s': %s", name, error)

        if not mounted:
            return
        await self._sweep_staging_directories(mounted)

    async def _sweep_staging_directories(self, volume_names: list[str]) -> None:
        sweep_script = (
            "for d in /sweep/*/.*.partial; do "
            '[ -d "$d" ] || continue; '
            f'if [ -z "$(find "$d" -mmin -{STALE_STAGING_MINUTES} -print -quit)" ]; '
            'then rm -rf "$d"; fi; '
            "done"
        )
        try:
            container = await self._run_cache_container(
                command=["sh", "-c", sweep_script],
                binds=[f"{name}:/sweep/{name}" for name in volume_names],
            )
            with suppress(DockerError):
                await container.delete(force=True)
        except Exception as error:
            self._logger.error("could not clean stale staging directories: %s", error)

    async def _run_cache_container(
        self,
        *,
        command: list[str],
        binds: list[str],
    ) -> DockerContainer:
        image = "alpine:latest"
        try:
            await self.client.images.get(image)
        except DockerError:
            await self.client.images.pull(image)
        container = await self.client.containers.create(
            config={
                "Image": image,
                "Cmd": command,
                "HostConfig": {"Binds": binds},
            }
        )
        await container.start()
        await container.wait()
        return container

    async def _recent_logs(self, container: DockerContainer) -> str:
        try:
            logs = await container.log(stdout=True, stderr=True, follow=False, tail=100)
        except Exception as error:
            self._logger.warning("could not read container logs: %s", error)
            return ""
        if isinstance(logs, list | tuple):
            return "".join(str(line) for line in logs)
        return str(logs or "")

    def _satellite_id_for(self, deployment: Deployment) -> str:
        if self.satellite_id is None:
            self.bind_satellite(str(deployment.satellite_id))
        if self.satellite_id != str(deployment.satellite_id):
            raise DriverError("deployment belongs to another satellite")
        return self.satellite_id

    @staticmethod
    def _container_name(deployment_id: str) -> str:
        return f"sat-{deployment_id}"

    def _upstream_url(self, deployment_id: str) -> str:
        return (
            f"http://{self._container_name(deployment_id)}:{self.configuration.MODEL_SERVER_PORT}"
        )


def _docker_status(error: BaseException) -> int | None:
    return error.status if isinstance(error, DockerError) else None


def _container_is_running(information: dict[str, Any]) -> bool:
    state = _mapping(information.get("State"))
    return state.get("Running") is True or state.get("Status") == "running"


def _docker_container_name(information: dict[str, Any]) -> str | None:
    raw_name = information.get("Name")
    if isinstance(raw_name, str) and raw_name:
        return raw_name.removeprefix("/")
    raw_names = information.get("Names")
    if isinstance(raw_names, list) and raw_names and isinstance(raw_names[0], str):
        return raw_names[0].removeprefix("/")
    return None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
