from collections import defaultdict, deque
from collections.abc import Callable, Sequence, Set
from dataclasses import dataclass, replace

from luml_satellite.declaration import DeploymentSettings
from luml_satellite.wire import ArtifactDownload, Deployment
from luml_satellite.workload import (
    UNSUPPORTED,
    ArtifactDeliveryMode,
    ArtifactHandle,
    BulkObservation,
    ListedWorkload,
    RemoveResult,
    StartContext,
    StartResult,
    StartStatus,
    UnsupportedOperation,
    WorkloadDriver,
    WorkloadListing,
    WorkloadObservation,
    WorkloadState,
)

type StartStep = StartResult | Exception
type ObservationStep = WorkloadObservation | Exception
type RemoveStep = RemoveResult | Exception


class FakeSettings(DeploymentSettings):
    pass


@dataclass(frozen=True)
class PushedArtifact:
    deployment_id: str
    artifact: ArtifactDownload
    provider_ref: str


class InMemoryArtifactPusher:
    def __init__(self, prefix: str = "memory://artifacts") -> None:
        self._prefix = prefix.rstrip("/")
        self.pushed: list[PushedArtifact] = []

    async def push(self, deployment: Deployment, artifact: ArtifactDownload) -> str:
        provider_ref = f"{self._prefix}/{artifact.artifact_id}"
        self.pushed.append(PushedArtifact(str(deployment.id), artifact, provider_ref))
        return provider_ref


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeDriver:
    kind: str = "fake"
    launcher_protocol: str = "fake-v1"
    supported_variants: Sequence[str] = ("default",)
    supported_tag_combinations: Sequence[Sequence[str]] | None = None
    settings_type: type[DeploymentSettings] = FakeSettings
    artifact_delivery: ArtifactDeliveryMode = ArtifactDeliveryMode.ON_DEMAND

    def __init__(
        self,
        *,
        bulk_observe: bool = True,
        workload_listing: bool = True,
    ) -> None:
        self.bulk_observe = bulk_observe
        self.workload_listing = workload_listing
        self.start_calls: list[tuple[Deployment, StartContext]] = []
        self.observe_calls: list[str] = []
        self.observe_all_calls: list[set[str]] = []
        self.remove_calls: list[str] = []
        self.release_calls: list[tuple[str, bool]] = []
        self.sweep_calls: list[set[str]] = []
        self.removal_rechecks = 0
        self._start_steps: dict[str, deque[StartStep]] = defaultdict(deque)
        self._observation_steps: dict[str, deque[ObservationStep]] = defaultdict(deque)
        self._remove_steps: dict[str, deque[RemoveStep]] = defaultdict(deque)
        self._observations: dict[str, WorkloadObservation] = {}
        self._artifacts: dict[str, str] = {}
        self._listed: dict[str, ListedWorkload] = {}

    def script_start(self, deployment_id: str, *steps: StartStep) -> None:
        self._start_steps[deployment_id].extend(steps)

    def script_observe(self, deployment_id: str, *steps: ObservationStep) -> None:
        self._observation_steps[deployment_id].extend(steps)

    def script_remove(self, deployment_id: str, *steps: RemoveStep) -> None:
        self._remove_steps[deployment_id].extend(steps)

    def add_workload(
        self,
        deployment_id: str,
        *,
        artifact_id: str | None = None,
        observation: WorkloadObservation | None = None,
        provider_ref: str | None = None,
        owned: bool = True,
        shared: bool = False,
    ) -> None:
        self._observations[deployment_id] = observation or WorkloadObservation(
            WorkloadState.READY,
            launcher_protocol=self.launcher_protocol,
        )
        if artifact_id is not None:
            self._artifacts[deployment_id] = artifact_id
        self._listed[deployment_id] = ListedWorkload(
            deployment_id=deployment_id,
            provider_ref=provider_ref,
            owned=owned,
            shared=shared,
        )

    def add_unidentified_workload(
        self,
        name: str,
        *,
        provider_ref: str | None = None,
        owned: bool = False,
        shared: bool = False,
    ) -> None:
        self._listed[name] = ListedWorkload(
            deployment_id=None,
            provider_ref=provider_ref,
            owned=owned,
            shared=shared,
        )

    async def start(self, deployment: Deployment, context: StartContext) -> StartResult:
        self.start_calls.append((deployment, context))
        deployment_id = str(deployment.id)
        step = _next(self._start_steps[deployment_id])
        if isinstance(step, Exception):
            raise step
        result = step or StartResult(
            StartStatus.READY,
            upstream_url=f"http://fake/{deployment_id}",
        )
        if result.status is not StartStatus.FAILED:
            state = (
                WorkloadState.READY
                if result.status is StartStatus.READY
                else WorkloadState.STARTING
            )
            self.add_workload(
                deployment_id,
                artifact_id=str(deployment.artifact_id),
                observation=WorkloadObservation(
                    state,
                    upstream_url=result.upstream_url,
                    provider_ref=result.provider_ref,
                    progress_note=result.progress_note,
                    launcher_protocol=self.launcher_protocol,
                ),
                provider_ref=result.provider_ref,
            )
        return result

    async def observe(self, deployment_id: str) -> WorkloadObservation:
        self.observe_calls.append(deployment_id)
        step = _next(self._observation_steps[deployment_id])
        if isinstance(step, Exception):
            raise step
        if step is not None:
            self._observations[deployment_id] = step
            return step
        return self._observations.get(
            deployment_id,
            WorkloadObservation(WorkloadState.MISSING),
        )

    async def observe_all(self, deployment_ids: Set[str]) -> BulkObservation:
        requested = set(deployment_ids)
        self.observe_all_calls.append(requested)
        if not self.bulk_observe:
            return UNSUPPORTED
        return {deployment_id: await self.observe(deployment_id) for deployment_id in requested}

    async def remove(self, deployment_id: str) -> RemoveResult:
        self.remove_calls.append(deployment_id)
        step = _next(self._remove_steps[deployment_id])
        if isinstance(step, Exception):
            raise step
        if step is not None:
            if step.removed:
                self._forget(deployment_id)
            if step.verified:
                observation = await self._recheck_removal(deployment_id)
                step = replace(
                    step,
                    verified=observation.state is WorkloadState.MISSING,
                )
            return step

        existed = deployment_id in self._observations
        artifact_id = self._artifacts.get(deployment_id)
        self._forget(deployment_id)
        verified = (await self._recheck_removal(deployment_id)).state is WorkloadState.MISSING
        return RemoveResult(removed=existed, verified=verified, artifact_id=artifact_id)

    async def list_workloads(self) -> WorkloadListing:
        if not self.workload_listing:
            return UNSUPPORTED
        return list(self._listed.values())

    async def release_artifact(self, artifact_id: str, still_referenced: bool) -> None:
        self.release_calls.append((artifact_id, still_referenced))

    async def sweep(self, artifact_ids: Set[str]) -> None:
        self.sweep_calls.append(set(artifact_ids))

    async def _recheck_removal(self, deployment_id: str) -> WorkloadObservation:
        self.removal_rechecks += 1
        return self._observations.get(
            deployment_id,
            WorkloadObservation(WorkloadState.MISSING),
        )

    def _forget(self, deployment_id: str) -> None:
        self._observations.pop(deployment_id, None)
        self._listed.pop(deployment_id, None)
        self._artifacts.pop(deployment_id, None)


class DriverConformanceSuite:
    def __init__(
        self,
        driver: WorkloadDriver,
        *,
        removal_recheck_count: Callable[[], int] | None = None,
    ) -> None:
        self._driver = driver
        self._removal_recheck_count = removal_recheck_count

    async def run(self, deployment: Deployment, context: StartContext) -> None:
        if not self._driver.kind or not self._driver.launcher_protocol:
            raise AssertionError("driver identity values must not be empty")

        first = await self._driver.start(deployment, context)
        second = await self._driver.start(deployment, context)
        if first.status is StartStatus.FAILED or second.status is StartStatus.FAILED:
            raise AssertionError("conformance deployment did not start")

        observation = await self._driver.observe(str(deployment.id))
        if observation.state is WorkloadState.MISSING:
            raise AssertionError("started workload could not be observed")

        bulk = await self._driver.observe_all({str(deployment.id)})
        if not isinstance(bulk, UnsupportedOperation) and str(deployment.id) not in bulk:
            raise AssertionError("bulk observation omitted the deployment")

        listing = await self._driver.list_workloads()
        if not isinstance(listing, UnsupportedOperation):
            matches = [item for item in listing if item.deployment_id == str(deployment.id)]
            if len(matches) != 1:
                raise AssertionError("repeated start duplicated the workload")

        recheck_count = self._removal_recheck_count
        checks_before = recheck_count() if recheck_count is not None else None
        removal = await self._driver.remove(str(deployment.id))
        if removal.verified and recheck_count is None:
            raise AssertionError("verified-removal conformance requires a re-check counter")
        if removal.verified and checks_before is not None and recheck_count is not None:
            checks_after = recheck_count()
            if checks_after <= checks_before:
                raise AssertionError("driver claimed verified removal without a re-check")
        if removal.verified:
            after_removal = await self._driver.observe(str(deployment.id))
            if after_removal.state is not WorkloadState.MISSING:
                raise AssertionError("verified removal left the workload observable")


async def assert_driver_conforms(
    driver: WorkloadDriver,
    deployment: Deployment,
    context: StartContext,
    *,
    removal_recheck_count: Callable[[], int] | None = None,
) -> None:
    suite = DriverConformanceSuite(
        driver,
        removal_recheck_count=removal_recheck_count,
    )
    await suite.run(deployment, context)


def fake_artifact_handle(artifact_id: str) -> ArtifactHandle:
    return ArtifactHandle(
        artifact_id=artifact_id,
        mode=ArtifactDeliveryMode.ON_DEMAND,
        refresh_url="http://fake/satellites/deployments/fake/artifact",
        token="fake-token",
    )


def _next[Step](steps: deque[Step]) -> Step | None:
    return steps.popleft() if steps else None
