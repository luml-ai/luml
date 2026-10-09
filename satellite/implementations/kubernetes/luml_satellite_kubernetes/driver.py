import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence, Set
from dataclasses import dataclass

from luml_satellite import (
    ArtifactDeliveryMode,
    Deployment,
    ListedWorkload,
    RemoveResult,
    StartContext,
    StartResult,
    StartStatus,
    TokenDeriver,
    WorkloadObservation,
    WorkloadState,
)
from luml_satellite.container import (
    KUBERNETES_ARTIFACT_LABEL,
    KUBERNETES_DEPLOYMENT_LABEL,
    KUBERNETES_DERIVATION_FINGERPRINT_LABEL,
    KUBERNETES_LAUNCHER_PROTOCOL_LABEL,
    KUBERNETES_MANAGED_BY_LABEL,
    KUBERNETES_SATELLITE_LABEL,
    KUBERNETES_SHARED_LABEL,
    KUBERNETES_SPEC_FINGERPRINT_LABEL,
)

from luml_satellite_kubernetes.api import KubernetesApiClient
from luml_satellite_kubernetes.configuration import KubernetesConfiguration
from luml_satellite_kubernetes.manifests import (
    deployment_object_name,
    render_cache_sweep_job,
    render_deployment_manifests,
)
from luml_satellite_kubernetes.settings import (
    KubernetesDeploymentSettings,
    build_settings_model,
)

type Sleep = Callable[[float], Awaitable[None]]

_MANAGED_SELECTOR = f"{KUBERNETES_MANAGED_BY_LABEL}=luml-satellite"
_REMOVAL_KINDS = ("Ingress", "Service", "Deployment", "Secret")
_POD_FAILURE_REASONS = frozenset({"ErrImagePull", "ImagePullBackOff", "CrashLoopBackOff"})


@dataclass(frozen=True)
class _PodFailure:
    pod_name: str
    container_name: str
    reason: str
    message: str


class KubernetesDriver:
    kind: str = "kubernetes"
    launcher_protocol: str = "1"
    supported_variants: Sequence[str] = ("pyfunc", "pipeline")
    supported_tag_combinations: Sequence[Sequence[str]] | None = None
    artifact_delivery: ArtifactDeliveryMode = ArtifactDeliveryMode.PRESIGNED_LINK

    def __init__(
        self,
        configuration: KubernetesConfiguration,
        api: KubernetesApiClient,
        *,
        token_deriver: TokenDeriver | None = None,
        sleep: Sleep = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        self.configuration = configuration
        self.api = api
        self.settings_type = build_settings_model(configuration)
        self.tokens = token_deriver or TokenDeriver(
            configuration.SATELLITE_TOKEN,
            configuration.DERIVATION_KEY,
        )
        self.platform_satellite_id: str | None = None
        self._sleep = sleep
        self._monotonic = monotonic
        self._logger = logger or logging.getLogger("luml_satellite_kubernetes.driver")
        self.removal_rechecks = 0

    def bind_satellite(self, satellite_id: str) -> None:
        if not satellite_id:
            raise ValueError("satellite_id must not be empty")
        self.platform_satellite_id = satellite_id

    async def start(self, deployment: Deployment, context: StartContext) -> StartResult:
        if (
            self.platform_satellite_id is not None
            and str(deployment.satellite_id) != self.platform_satellite_id
        ):
            return StartResult(
                StartStatus.FAILED,
                reason="Deployment belongs to another satellite",
                error="deployment belongs to another satellite",
            )
        settings = context.settings
        if not isinstance(settings, KubernetesDeploymentSettings):
            return StartResult(
                StartStatus.FAILED,
                reason="Invalid deployment settings",
                error="Kubernetes settings were not supplied",
            )
        if settings.artifact_cache == "shared" and not self.configuration.SHARED_CACHE_CLAIM_NAME:
            return StartResult(
                StartStatus.FAILED,
                reason="Shared cache unavailable",
                error="shared artifact cache requested but no shared cache claim is configured",
            )
        if not context.artifact.download_url:
            return StartResult(
                StartStatus.FAILED,
                reason="Artifact unavailable",
                error="presigned artifact delivery requires a download link",
            )

        manifests = render_deployment_manifests(
            self.configuration,
            deployment,
            context,
            self.tokens,
        )
        for manifest in manifests.objects():
            await self.api.apply(manifest)

        deployment_id = str(deployment.id)
        name = deployment_object_name(deployment_id)
        return StartResult(
            StartStatus.IN_PROGRESS,
            upstream_url=self._upstream_url(deployment_id),
            provider_ref=f"deployment/{name}",
            progress_note=f"0/{settings.replicas} pods ready",
        )

    async def observe(self, deployment_id: str) -> WorkloadObservation:
        name = deployment_object_name(deployment_id)
        workload = await self.api.get("Deployment", name)
        if workload is None:
            return WorkloadObservation(WorkloadState.MISSING)
        pods = await self.api.list("Pod", self._deployment_selector(deployment_id))
        return await self._observation(deployment_id, workload, pods)

    async def observe_all(self, deployment_ids: Set[str]) -> Mapping[str, WorkloadObservation]:
        selector = self._owned_selector()
        workloads, pods = await asyncio.gather(
            self.api.list("Deployment", selector),
            self.api.list("Pod", selector),
        )
        deployments_by_id = {
            deployment_id: item
            for item in workloads
            if (deployment_id := _labels(item).get(KUBERNETES_DEPLOYMENT_LABEL)) is not None
            and deployment_id in deployment_ids
        }
        pods_by_id: dict[str, list[dict[str, object]]] = defaultdict(list)
        for pod in pods:
            deployment_id = _labels(pod).get(KUBERNETES_DEPLOYMENT_LABEL)
            if deployment_id is not None and deployment_id in deployment_ids:
                pods_by_id[deployment_id].append(pod)

        observations: dict[str, WorkloadObservation] = {}
        for deployment_id in deployment_ids:
            workload = deployments_by_id.get(deployment_id)
            if workload is None:
                observations[deployment_id] = WorkloadObservation(WorkloadState.MISSING)
            else:
                observations[deployment_id] = await self._observation(
                    deployment_id,
                    workload,
                    pods_by_id.get(deployment_id, []),
                )
        return observations

    async def remove(self, deployment_id: str) -> RemoveResult:
        name = deployment_object_name(deployment_id)
        workload = await self.api.get("Deployment", name)
        artifact_id = (
            _labels(workload).get(KUBERNETES_ARTIFACT_LABEL) if workload is not None else None
        )
        results = await asyncio.gather(*(self.api.delete(kind, name) for kind in _REMOVAL_KINDS))
        removed = any(results)
        deadline = self._monotonic() + self.configuration.REMOVAL_TIMEOUT_SEC
        while True:
            self.removal_rechecks += 1
            remaining = await asyncio.gather(*(self.api.get(kind, name) for kind in _REMOVAL_KINDS))
            if all(item is None for item in remaining):
                return RemoveResult(removed=removed, verified=True, artifact_id=artifact_id)
            if self._monotonic() >= deadline:
                return RemoveResult(removed=removed, verified=False, artifact_id=artifact_id)
            await self._sleep(
                min(
                    self.configuration.REMOVAL_POLL_INTERVAL_SEC,
                    max(0.0, deadline - self._monotonic()),
                )
            )

    async def list_workloads(self) -> list[ListedWorkload]:
        workloads = await self.api.list("Deployment", _MANAGED_SELECTOR)
        listed: list[ListedWorkload] = []
        for workload in workloads:
            labels = _labels(workload)
            deployment_id = labels.get(KUBERNETES_DEPLOYMENT_LABEL)
            listed.append(
                ListedWorkload(
                    deployment_id=deployment_id,
                    provider_ref=(
                        f"deployment/{_name(workload)}" if _name(workload) is not None else None
                    ),
                    owned=(
                        labels.get(KUBERNETES_SATELLITE_LABEL) == self.configuration.SATELLITE_NAME
                    ),
                    shared=labels.get(KUBERNETES_SHARED_LABEL) == "true",
                )
            )
        return listed

    async def release_artifact(self, artifact_id: str, still_referenced: bool) -> None:
        del artifact_id, still_referenced

    async def sweep(self, artifact_ids: Set[str]) -> None:
        if self.configuration.SHARED_CACHE_CLAIM_NAME is None:
            return
        manifest = render_cache_sweep_job(self.configuration, set(artifact_ids))
        name = _name(manifest)
        if name is None:
            raise ValueError("cache sweep Job has no name")
        await self.api.delete("Job", name)
        await self.api.apply(manifest)

    async def aclose(self) -> None:
        await self.api.aclose()

    async def _observation(
        self,
        deployment_id: str,
        workload: Mapping[str, object],
        pods: Sequence[Mapping[str, object]],
    ) -> WorkloadObservation:
        labels = _labels(workload)
        replicas = _nested_int(workload, "spec", "replicas") or 1
        available = _nested_int(workload, "status", "availableReplicas") or 0
        ready = _nested_int(workload, "status", "readyReplicas") or 0
        upstream_url = self._upstream_url(deployment_id)
        provider_ref = f"deployment/{deployment_object_name(deployment_id)}"
        launcher_protocol = labels.get(KUBERNETES_LAUNCHER_PROTOCOL_LABEL)
        needs_reapply = (
            labels.get(KUBERNETES_DERIVATION_FINGERPRINT_LABEL) != self.tokens.fingerprint
            or labels.get(KUBERNETES_SPEC_FINGERPRINT_LABEL)
            != self.configuration.workload_spec_fingerprint
        )
        if available > 0:
            return WorkloadObservation(
                WorkloadState.READY,
                upstream_url=upstream_url,
                provider_ref=provider_ref,
                launcher_protocol=launcher_protocol,
                needs_reapply=needs_reapply,
            )

        failure = _pod_failure(pods)
        if failure is not None:
            logs = await self.api.pod_logs(
                failure.pod_name,
                failure.container_name,
                100,
            )
            detail = failure.reason
            if failure.message:
                detail = f"{detail}: {failure.message}"
            return WorkloadObservation(
                WorkloadState.FAILED,
                error=detail,
                recent_logs=logs,
                progress_note=f"{ready}/{replicas} pods ready",
                upstream_url=upstream_url,
                provider_ref=provider_ref,
                launcher_protocol=launcher_protocol,
                needs_reapply=needs_reapply,
            )

        pending_message = _pending_message(pods)
        note = f"{ready}/{replicas} pods ready"
        if pending_message:
            note = f"{note}: {pending_message}"
        return WorkloadObservation(
            WorkloadState.STARTING,
            progress_note=note,
            error=pending_message,
            upstream_url=upstream_url,
            provider_ref=provider_ref,
            launcher_protocol=launcher_protocol,
            needs_reapply=needs_reapply,
        )

    def _owned_selector(self) -> str:
        satellite = f"{KUBERNETES_SATELLITE_LABEL}={self.configuration.SATELLITE_NAME}"
        return f"{_MANAGED_SELECTOR},{satellite}"

    def _deployment_selector(self, deployment_id: str) -> str:
        return f"{self._owned_selector()},{KUBERNETES_DEPLOYMENT_LABEL}={deployment_id}"

    def _upstream_url(self, deployment_id: str) -> str:
        name = deployment_object_name(deployment_id)
        return f"http://{name}:{self.configuration.INTERNAL_PORT}"


def _pod_failure(pods: Sequence[Mapping[str, object]]) -> _PodFailure | None:
    for pod in pods:
        pod_name = _name(pod) or "unknown-pod"
        status = _mapping(pod.get("status"))
        for container_status in _mapping_sequence(status.get("containerStatuses")):
            waiting = _mapping(_mapping(container_status.get("state")).get("waiting"))
            reason = waiting.get("reason")
            if reason in _POD_FAILURE_REASONS:
                return _PodFailure(
                    pod_name,
                    str(container_status.get("name") or "model"),
                    str(reason),
                    str(waiting.get("message") or ""),
                )
        for container_status in _mapping_sequence(status.get("initContainerStatuses")):
            waiting = _mapping(_mapping(container_status.get("state")).get("waiting"))
            if waiting.get("reason") == "CrashLoopBackOff":
                return _PodFailure(
                    pod_name,
                    str(container_status.get("name") or "artifact-fetch"),
                    "CrashLoopBackOff",
                    str(waiting.get("message") or ""),
                )
        if status.get("phase") == "Failed":
            return _PodFailure(
                pod_name,
                _first_container_name(status),
                str(status.get("reason") or "PodFailed"),
                str(status.get("message") or ""),
            )
    return None


def _pending_message(pods: Sequence[Mapping[str, object]]) -> str | None:
    for pod in pods:
        status = _mapping(pod.get("status"))
        for condition in _mapping_sequence(status.get("conditions")):
            message = condition.get("message")
            if condition.get("status") in {False, "False"} and isinstance(message, str) and message:
                return message
    return None


def _first_container_name(status: Mapping[str, object]) -> str:
    for key in ("containerStatuses", "initContainerStatuses"):
        values = _mapping_sequence(status.get(key))
        if values:
            return str(values[0].get("name") or "model")
    return "model"


def _labels(item: Mapping[str, object] | None) -> dict[str, str]:
    if item is None:
        return {}
    raw = _mapping(_mapping(item.get("metadata")).get("labels"))
    return {str(key): str(value) for key, value in raw.items()}


def _name(item: Mapping[str, object]) -> str | None:
    value = _mapping(item.get("metadata")).get("name")
    return str(value) if value is not None else None


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _mapping_sequence(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _nested_int(item: Mapping[str, object], *keys: str) -> int | None:
    value: object = item
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, int) else None
