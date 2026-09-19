import asyncio
import time
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from luml_satellite.declaration import DeploymentSettings
from luml_satellite.wire import Deployment
from luml_satellite.workload.recording import RecordingPolicy


class ArtifactDeliveryMode(StrEnum):
    ON_DEMAND = "on_demand"
    PRESIGNED_LINK = "presigned_link"
    PUSH = "push"


class StartStatus(StrEnum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class WorkloadState(StrEnum):
    READY = "ready"
    STARTING = "starting"
    STOPPED = "stopped"
    MISSING = "missing"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArtifactHandle:
    artifact_id: str
    mode: ArtifactDeliveryMode
    download_url: str | None = None
    refresh_url: str | None = None
    token: str | None = None
    expires_at: datetime | None = None
    provider_ref: str | None = None


@dataclass(frozen=True)
class StartContext:
    settings: DeploymentSettings
    secrets: Mapping[str, str]
    artifact: ArtifactHandle
    telemetry_endpoint: str | None
    health_check_timeout: int
    recording_policy: RecordingPolicy


@dataclass(frozen=True)
class StartResult:
    status: StartStatus
    upstream_url: str | None = None
    provider_ref: str | None = None
    progress_note: str | None = None
    error: str | None = None
    reason: str | None = None
    serving_address: str | None = None
    monitoring_link: str | None = None


@dataclass(frozen=True)
class WorkloadObservation:
    state: WorkloadState
    upstream_url: str | None = None
    provider_ref: str | None = None
    progress_note: str | None = None
    error: str | None = None
    recent_logs: str = ""
    launcher_protocol: str | None = None
    needs_reapply: bool = False


@dataclass(frozen=True)
class RemoveResult:
    removed: bool
    verified: bool
    artifact_id: str | None = None


@dataclass(frozen=True)
class ListedWorkload:
    deployment_id: str | None
    provider_ref: str | None = None
    owned: bool = True
    shared: bool = False


@dataclass(frozen=True)
class UnsupportedOperation:
    name: str = "unsupported"


UNSUPPORTED = UnsupportedOperation()

type BulkObservation = Mapping[str, WorkloadObservation] | UnsupportedOperation
type WorkloadListing = Sequence[ListedWorkload] | UnsupportedOperation


class DriverError(RuntimeError):
    def __init__(self, message: str, *, reason: str | None = None) -> None:
        self.reason = reason
        super().__init__(message)


class WorkloadDriver(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def launcher_protocol(self) -> str: ...

    @property
    def supported_variants(self) -> Sequence[str]: ...

    @property
    def supported_tag_combinations(self) -> Sequence[Sequence[str]] | None: ...

    @property
    def settings_type(self) -> type[DeploymentSettings]: ...

    @property
    def artifact_delivery(self) -> ArtifactDeliveryMode: ...

    async def start(self, deployment: Deployment, context: StartContext) -> StartResult: ...

    async def observe(self, deployment_id: str) -> WorkloadObservation: ...

    async def observe_all(self, deployment_ids: Set[str]) -> BulkObservation: ...

    async def remove(self, deployment_id: str) -> RemoveResult: ...

    async def list_workloads(self) -> WorkloadListing: ...

    async def release_artifact(self, artifact_id: str, still_referenced: bool) -> None: ...

    async def sweep(self, artifact_ids: Set[str]) -> None: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...

    async def sleep(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


async def wait_until_not_starting(
    driver: WorkloadDriver,
    deployment_id: str,
    *,
    timeout: float,
    poll_interval: float = 1.0,
    clock: Clock | None = None,
) -> WorkloadObservation:
    if timeout < 0:
        raise ValueError("timeout must not be negative")
    if poll_interval <= 0:
        raise ValueError("poll_interval must be greater than zero")

    active_clock = clock or SystemClock()
    deadline = active_clock.monotonic() + timeout
    while True:
        observation = await driver.observe(deployment_id)
        if observation.state is not WorkloadState.STARTING:
            return observation
        remaining = deadline - active_clock.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"workload '{deployment_id}' stayed in the starting state")
        await active_clock.sleep(min(poll_interval, remaining))


wait_for_workload = wait_until_not_starting
