import asyncio
import copy
import logging
from collections.abc import Awaitable, Callable, Mapping, Set
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from luml_satellite.declaration import SettingsValidationError, parse_settings
from luml_satellite.wire import (
    Deployment,
    DeploymentStatus,
    DeploymentUpdate,
    ErrorMessage,
    PlatformRefusal,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)
from luml_satellite.workload import (
    ArtifactResolutionError,
    ArtifactResolver,
    Clock,
    DriverError,
    RecordingPolicy,
    StartContext,
    StartStatus,
    SystemClock,
    UnsupportedOperation,
    WorkloadDriver,
    WorkloadObservation,
    WorkloadState,
    status_transition_allowed,
)

from .serving import ModelDescription, NoServingPlacement, ServingPlacement

FAILED_TO_GET_DEPLOYMENT_REASON = "failed to get deployment details"
INVALID_SETTINGS_REASON = "Invalid deployment settings"
SECRET_UNAVAILABLE_REASON = "Secret unavailable"
ARTIFACT_UNAVAILABLE_REASON = "Artifact unavailable"
START_FAILED_REASON = "Failed to create container"
FINALIZE_FAILED_REASON = "failed to finalize deployment"
SUPERSEDED_REASON = "superseded by undeploy"
RECORD_GONE_REASON = "deployment record gone"
REMOVE_FAILED_REASON = "Failed to remove container."
DELETE_FAILED_REASON = "Failed to delete deployment."
RECONCILE_FETCH_FAILED_REASON = "Failed to fetch deployment."
RECONCILE_FAILED_REASON = "Failed to reconcile deployment."
HEALTH_CHECK_TIMEOUT_REASON = "healthcheck timeout"
WORKLOAD_STOPPED_REASON = "Container stopped or not found"

_NOTE_LIMIT = 1000
_DEPLOY_LOG_LIMIT = 1000


class ConvergencePlatform(Protocol):
    async def get_deployment(self, deployment_id: str) -> Deployment: ...

    async def update_deployment(
        self,
        deployment_id: str,
        deployment: DeploymentUpdate,
    ) -> Deployment: ...

    async def update_task_status(
        self,
        task_id: str,
        status: SatelliteTaskStatus | str,
        result: ErrorMessage | dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def get_orbit_secret(self, secret_id: str) -> dict[str, Any]: ...

    async def delete_deployment(self, deployment_id: str) -> None: ...

    async def list_deployments(self) -> list[dict[str, Any]]: ...


class MonitoringLinks(Protocol):
    def monitoring_link(self, deployment: Deployment) -> str | None: ...


class InProgressKind(StrEnum):
    DEPLOY = "deploy"
    RELAUNCH = "relaunch"
    REAPPLY = "reapply"


@dataclass
class InProgressDeployment:
    deployment: Deployment
    task: SatelliteQueueTask | None
    deadline: float
    kind: InProgressKind
    upstream_url: str | None = None
    provider_ref: str | None = None
    serving_address: str | None = None
    monitoring_link: str | None = None
    reported_note: object = None
    reported_provider_ref: object = None
    recent_logs: str = ""
    start_called: bool = False


class DriverCallTimeout(TimeoutError):
    pass


class _TransitionResult(StrEnum):
    APPLIED = "applied"
    REFUSED = "refused"
    GONE = "gone"
    ERROR = "error"


@dataclass(frozen=True)
class _TransitionOutcome:
    result: _TransitionResult
    record: Deployment | None = None
    current_status: str | None = None
    error: Exception | None = None


_NOT_REPORTED = object()


class Convergence:
    def __init__(
        self,
        platform: ConvergencePlatform,
        driver: WorkloadDriver,
        artifact_resolver: ArtifactResolver,
        *,
        serving: ServingPlacement | None = None,
        monitoring: MonitoringLinks | None = None,
        clock: Clock | None = None,
        max_parallel: int = 8,
        driver_call_timeout: float = 300.0,
        health_probe_timeout: float = 5.0,
        default_health_check_timeout: int = 1800,
        telemetry_endpoint: str | None = None,
        recording_policy: RecordingPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if max_parallel <= 0:
            raise ValueError("max_parallel must be greater than zero")
        if driver_call_timeout <= 0:
            raise ValueError("driver_call_timeout must be greater than zero")
        if health_probe_timeout <= 0:
            raise ValueError("health_probe_timeout must be greater than zero")
        if default_health_check_timeout <= 0:
            raise ValueError("default_health_check_timeout must be greater than zero")

        self.platform = platform
        self.driver = driver
        self.artifact_resolver = artifact_resolver
        self.serving = serving or NoServingPlacement()
        self.monitoring = monitoring
        self.clock = clock or SystemClock()
        self.driver_call_timeout = driver_call_timeout
        self.health_probe_timeout = health_probe_timeout
        self.default_health_check_timeout = default_health_check_timeout
        self.telemetry_endpoint = telemetry_endpoint
        self.recording_policy = recording_policy or RecordingPolicy()
        self.logger = logger or logging.getLogger("luml_satellite.convergence")
        self._driver_slots = asyncio.Semaphore(max_parallel)
        self._deployment_locks: dict[str, asyncio.Lock] = {}
        self._in_progress: dict[str, InProgressDeployment] = {}

    @property
    def in_progress(self) -> Mapping[str, InProgressDeployment]:
        return dict(self._in_progress)

    def deployment_lock(self, deployment_id: str) -> asyncio.Lock:
        return self._deployment_locks.setdefault(deployment_id, asyncio.Lock())

    async def handle_task(self, task: SatelliteQueueTask, *, resume: bool = False) -> None:
        deployment_id = _deployment_id(task)
        if deployment_id is None:
            await self._fail_task(task, "invalid task payload", "missing deployment_id")
            return

        async with self.deployment_lock(deployment_id):
            if task.type == SatelliteTaskType.DEPLOY:
                await self._deploy(task, deployment_id, resume=resume)
            elif task.type == SatelliteTaskType.UNDEPLOY:
                await self._undeploy(task, deployment_id, resume=resume)
            elif task.type == SatelliteTaskType.RECONCILE:
                await self._reconcile(task, deployment_id, resume=resume)
            else:
                raise ValueError(f"unknown built-in task type: {task.type}")

    async def run_custom(
        self,
        task: SatelliteQueueTask,
        handler: Callable[[SatelliteQueueTask], Awaitable[None]],
    ) -> None:
        deployment_id = _deployment_id(task)
        if deployment_id is None:
            async with self._driver_slots:
                await handler(task)
            return
        async with self.deployment_lock(deployment_id), self._driver_slots:
            await handler(task)

    async def revisit_in_progress(
        self,
        *,
        skip_locked: bool = False,
        deployment_ids: Set[str] | None = None,
    ) -> None:
        candidates = deployment_ids if deployment_ids is not None else set(self._in_progress)
        selected_ids = [
            deployment_id
            for deployment_id in candidates
            if deployment_id in self._in_progress
            if not skip_locked or not self.deployment_lock(deployment_id).locked()
        ]
        if not selected_ids:
            return

        observations = await self._observe_many(set(selected_ids))
        for deployment_id in selected_ids:
            lock = self.deployment_lock(deployment_id)
            if skip_locked and lock.locked():
                continue
            async with lock:
                entry = self._in_progress.get(deployment_id)
                if entry is None:
                    continue
                observation = observations.get(
                    deployment_id,
                    WorkloadObservation(WorkloadState.UNKNOWN),
                )
                await self._apply_deploy_observation(entry, observation)

    async def _deploy(
        self,
        task: SatelliteQueueTask,
        deployment_id: str,
        *,
        resume: bool,
    ) -> None:
        if not resume:
            await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        try:
            deployment = await self.platform.get_deployment(deployment_id)
        except Exception as error:
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                FAILED_TO_GET_DEPLOYMENT_REASON,
                str(error),
                cleanup=False,
            )
            return

        try:
            context = await self._start_context(deployment)
        except SettingsValidationError as error:
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                INVALID_SETTINGS_REASON,
                str(error),
                cleanup=False,
            )
            return
        except _SecretResolutionError as error:
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                SECRET_UNAVAILABLE_REASON,
                str(error),
                cleanup=False,
            )
            return
        except ArtifactResolutionError as error:
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                ARTIFACT_UNAVAILABLE_REASON,
                str(error),
                cleanup=False,
            )
            return
        except Exception as error:
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                ARTIFACT_UNAVAILABLE_REASON,
                str(error),
                cleanup=False,
            )
            return

        try:
            result = await self._call_driver(
                "start",
                lambda: self.driver.start(deployment, context),
            )
        except Exception as error:
            reason = error.reason if isinstance(error, DriverError) and error.reason else None
            logs = await self._recent_logs(deployment_id)
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                reason or START_FAILED_REASON,
                _error_with_logs(str(error), logs, _DEPLOY_LOG_LIMIT),
                cleanup=True,
            )
            return

        if result.status is StartStatus.FAILED:
            logs = await self._recent_logs(deployment_id)
            await self._terminal_deploy_failure(
                task,
                deployment_id,
                result.reason or START_FAILED_REASON,
                _error_with_logs(result.error or "", logs, _DEPLOY_LOG_LIMIT),
                cleanup=True,
            )
            return

        entry = InProgressDeployment(
            deployment=deployment,
            task=task,
            deadline=self.clock.monotonic() + context.health_check_timeout,
            kind=InProgressKind.DEPLOY,
            upstream_url=result.upstream_url,
            provider_ref=result.provider_ref,
            serving_address=result.serving_address,
            monitoring_link=result.monitoring_link,
            reported_note=_NOT_REPORTED,
            reported_provider_ref=_NOT_REPORTED,
            start_called=True,
        )
        self._in_progress[deployment_id] = entry
        if result.status is StartStatus.IN_PROGRESS:
            await self._report_information(entry, result.provider_ref, result.progress_note)
            return

        await self._apply_deploy_observation(
            entry,
            WorkloadObservation(
                WorkloadState.READY,
                upstream_url=result.upstream_url,
                provider_ref=result.provider_ref,
                progress_note=result.progress_note,
            ),
        )

    async def _start_context(self, deployment: Deployment) -> StartContext:
        settings = parse_settings(
            self.driver.settings_type,
            deployment.satellite_parameters,
            default_health_check_timeout=self.default_health_check_timeout,
        )
        secrets = await self._resolve_secrets(deployment)
        artifact = await self.artifact_resolver.resolve(deployment, self.driver.artifact_delivery)
        return StartContext(
            settings=settings,
            secrets=secrets,
            artifact=artifact,
            telemetry_endpoint=self.telemetry_endpoint,
            health_check_timeout=settings.health_check_timeout,
            recording_policy=self.recording_policy,
        )

    async def _resolve_secrets(self, deployment: Deployment) -> dict[str, str]:
        resolved: dict[str, str] = {}
        unavailable: list[str] = []
        for variable, secret_id in (deployment.env_variables_secrets or {}).items():
            try:
                secret = await self.platform.get_orbit_secret(secret_id)
                if "value" not in secret:
                    raise ValueError("secret response has no value")
                resolved[variable] = str(secret["value"])
            except Exception:
                unavailable.append(variable)
        if unavailable:
            names = ", ".join(sorted(unavailable))
            raise _SecretResolutionError(f"unavailable variables: {names}")
        return resolved

    async def _apply_deploy_observation(
        self,
        entry: InProgressDeployment,
        observation: WorkloadObservation,
    ) -> None:
        deployment_id = str(entry.deployment.id)
        if observation.upstream_url is not None:
            entry.upstream_url = observation.upstream_url
        if observation.provider_ref is not None:
            entry.provider_ref = observation.provider_ref
        if observation.recent_logs:
            entry.recent_logs = observation.recent_logs
        await self._report_information(
            entry,
            observation.provider_ref,
            observation.progress_note,
        )

        if observation.state is WorkloadState.READY:
            healthy = await self._check_health(entry)
            if healthy:
                await self._finalize_deploy(entry)
                return
            await self._fail_at_deadline(entry, observation.error)
            return

        if observation.state in {WorkloadState.STARTING, WorkloadState.UNKNOWN}:
            await self._fail_at_deadline(entry, observation.error)
            return

        if observation.state in {
            WorkloadState.STOPPED,
            WorkloadState.MISSING,
            WorkloadState.FAILED,
        }:
            self._in_progress.pop(deployment_id, None)
            if entry.task is not None:
                await self._terminal_deploy_failure(
                    entry.task,
                    deployment_id,
                    WORKLOAD_STOPPED_REASON,
                    _error_with_logs(
                        observation.error or "",
                        entry.recent_logs,
                        _DEPLOY_LOG_LIMIT,
                    ),
                    cleanup=True,
                )

    async def _fail_at_deadline(
        self,
        entry: InProgressDeployment,
        error: str | None,
    ) -> None:
        if self.clock.monotonic() < entry.deadline:
            return
        deployment_id = str(entry.deployment.id)
        self._in_progress.pop(deployment_id, None)
        if entry.task is not None:
            await self._terminal_deploy_failure(
                entry.task,
                deployment_id,
                HEALTH_CHECK_TIMEOUT_REASON,
                _error_with_logs(error or "", entry.recent_logs, _DEPLOY_LOG_LIMIT),
                cleanup=True,
            )

    async def _check_health(self, entry: InProgressDeployment) -> bool:
        try:
            async with asyncio.timeout(self.health_probe_timeout):
                return await self.serving.check_health(
                    entry.deployment,
                    upstream_url=entry.upstream_url,
                )
        except Exception as error:
            self.logger.debug(
                "health probe failed for deployment '%s': %s",
                entry.deployment.id,
                error,
            )
            return False

    async def _finalize_deploy(self, entry: InProgressDeployment) -> None:
        deployment = entry.deployment
        deployment_id = str(deployment.id)
        description = await self._read_description(deployment, entry.upstream_url)
        description = _without_secret_attributes(description, deployment)

        try:
            await self.serving.register(
                deployment,
                upstream_url=entry.upstream_url,
                description=description,
            )
            serving_address = entry.serving_address or self.serving.address(
                deployment,
                upstream_url=entry.upstream_url,
            )
            if serving_address is None:
                serving_address = f"/deployments/{deployment_id}"
            monitoring_link = entry.monitoring_link
            if monitoring_link is None:
                monitoring_link = self._monitoring_link(deployment)
        except Exception as error:
            self._in_progress.pop(deployment_id, None)
            if entry.task is not None:
                await self._terminal_deploy_failure(
                    entry.task,
                    deployment_id,
                    FINALIZE_FAILED_REASON,
                    str(error),
                    cleanup=True,
                )
            return

        update = DeploymentUpdate(
            status=DeploymentStatus.ACTIVE,
            inference_url=serving_address,
            monitoring_url=monitoring_link,
            schemas=dict(description.schema) if description.schema is not None else None,
            error_message=None,
            provider_ref=entry.provider_ref,
            progress_note=None,
        )
        outcome = await self._transition(deployment_id, update)
        self._in_progress.pop(deployment_id, None)

        if outcome.result is _TransitionResult.GONE:
            await self._cleanup(deployment_id)
            if entry.task is not None:
                await self._fail_task(entry.task, RECORD_GONE_REASON, "deployment record is gone")
            return
        if outcome.result is _TransitionResult.REFUSED and outcome.current_status in {
            DeploymentStatus.DELETION_PENDING,
            DeploymentStatus.DELETION_FAILED,
        }:
            await self._unregister(deployment_id)
            if entry.task is not None:
                await self._fail_task(entry.task, SUPERSEDED_REASON, "deployment is being deleted")
            return
        if outcome.result is not _TransitionResult.APPLIED:
            if entry.task is not None:
                detail = str(outcome.error or "active transition was refused")
                await self._terminal_deploy_failure(
                    entry.task,
                    deployment_id,
                    FINALIZE_FAILED_REASON,
                    detail,
                    cleanup=True,
                )
            return

        active_record = outcome.record
        if active_record is None:
            return
        try:
            self.serving.note_platform_record(deployment_id, active_record)
            if entry.task is not None:
                await self.platform.update_task_status(
                    entry.task.id,
                    SatelliteTaskStatus.DONE,
                    {"inference_url": serving_address},
                )
        except Exception as error:
            self.logger.error(
                "deployment '%s' became active but final task bookkeeping failed: %s",
                deployment_id,
                error,
            )

    async def _read_description(
        self,
        deployment: Deployment,
        upstream_url: str | None,
    ) -> ModelDescription:
        try:
            return await self.serving.describe(deployment, upstream_url=upstream_url)
        except Exception as error:
            self.logger.warning(
                "could not read the model description for deployment '%s': %s",
                deployment.id,
                error,
            )
            return ModelDescription()

    async def _terminal_deploy_failure(
        self,
        task: SatelliteQueueTask,
        deployment_id: str,
        reason: str,
        error: str,
        *,
        cleanup: bool,
    ) -> None:
        self._in_progress.pop(deployment_id, None)
        await self._fail_task(task, reason, error)
        await self._transition(
            deployment_id,
            DeploymentUpdate(
                status=DeploymentStatus.FAILED,
                error_message=ErrorMessage(reason=reason, error=error),
                progress_note=None,
            ),
        )
        if cleanup:
            await self._cleanup(deployment_id)

    async def _undeploy(
        self,
        task: SatelliteQueueTask,
        deployment_id: str,
        *,
        resume: bool,
    ) -> None:
        if not resume:
            await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)

        entry = self._in_progress.pop(deployment_id, None)
        if entry is not None and entry.task is not None:
            await self._fail_task(
                entry.task,
                SUPERSEDED_REASON,
                "deployment was superseded by an undeploy task",
            )

        try:
            removal = await self._call_driver(
                "remove",
                lambda: self.driver.remove(deployment_id),
            )
        except Exception as error:
            await self._fail_undeploy(task, deployment_id, REMOVE_FAILED_REASON, str(error))
            return
        if not removal.verified:
            await self._fail_undeploy(
                task,
                deployment_id,
                REMOVE_FAILED_REASON,
                "workload removal could not be verified",
            )
            return

        try:
            await self.platform.delete_deployment(deployment_id)
        except PlatformRefusal as error:
            if error.status_code not in {404, 410}:
                await self._fail_undeploy(task, deployment_id, DELETE_FAILED_REASON, str(error))
                return
        except Exception as error:
            await self._fail_undeploy(task, deployment_id, DELETE_FAILED_REASON, str(error))
            return

        await self._unregister(deployment_id)
        if removal.artifact_id is not None:
            await self._release_artifact(removal.artifact_id)
        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {"container_removed": removal.removed},
        )

    async def _fail_undeploy(
        self,
        task: SatelliteQueueTask,
        deployment_id: str,
        reason: str,
        error: str,
    ) -> None:
        await self._fail_task(task, reason, error)
        await self._transition(
            deployment_id,
            DeploymentUpdate(
                status=DeploymentStatus.DELETION_FAILED,
                error_message=ErrorMessage(reason=reason, error=error),
            ),
        )

    async def _release_artifact(self, artifact_id: str) -> None:
        try:
            deployments = await self.platform.list_deployments()
            still_referenced = any(
                str(deployment.get("artifact_id", "")) == artifact_id for deployment in deployments
            )
            await self._call_driver(
                "release_artifact",
                lambda: self.driver.release_artifact(artifact_id, still_referenced),
            )
        except Exception as error:
            self.logger.error("failed to release artifact '%s': %s", artifact_id, error)

    async def _reconcile(
        self,
        task: SatelliteQueueTask,
        deployment_id: str,
        *,
        resume: bool,
    ) -> None:
        if not resume:
            await self.platform.update_task_status(task.id, SatelliteTaskStatus.RUNNING)
        try:
            deployment = await self.platform.get_deployment(deployment_id)
        except Exception as error:
            await self._fail_task(task, RECONCILE_FETCH_FAILED_REASON, str(error))
            return

        if deployment.status != DeploymentStatus.ACTIVE:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.DONE,
                {"reconciled": False, "reason": f"status={deployment.status}"},
            )
            return

        try:
            description = await self._read_description(deployment, None)
            description = _without_secret_attributes(description, deployment)
            await self.serving.register(
                deployment,
                upstream_url=None,
                description=description,
            )
            updated = await self.platform.update_deployment(
                deployment_id,
                DeploymentUpdate(
                    monitoring_url=self._monitoring_link(
                        deployment,
                        preserve_existing=True,
                    )
                ),
            )
            self.serving.note_platform_record(deployment_id, updated)
        except Exception as error:
            await self._fail_task(task, RECONCILE_FAILED_REASON, str(error))
            return

        await self.platform.update_task_status(
            task.id,
            SatelliteTaskStatus.DONE,
            {
                "reconciled": True,
                "monitoring_enabled": deployment.monitoring_mode.strip().lower() == "full",
            },
        )

    async def _report_information(
        self,
        entry: InProgressDeployment,
        provider_ref: str | None,
        progress_note: str | None,
    ) -> None:
        note = progress_note[:_NOTE_LIMIT] if progress_note is not None else None
        fields: dict[str, object] = {}
        if provider_ref is not None and provider_ref != entry.reported_provider_ref:
            fields["provider_ref"] = provider_ref
        if note is not None and note != entry.reported_note:
            fields["progress_note"] = note
        elif (
            note is None
            and entry.reported_note is not _NOT_REPORTED
            and entry.reported_note is not None
        ):
            fields["progress_note"] = None
        if not fields:
            return
        if "provider_ref" in fields and "progress_note" in fields:
            update = DeploymentUpdate(provider_ref=provider_ref, progress_note=note)
        elif "provider_ref" in fields:
            update = DeploymentUpdate(provider_ref=provider_ref)
        else:
            update = DeploymentUpdate(progress_note=note)
        try:
            await self.platform.update_deployment(
                str(entry.deployment.id),
                update,
            )
        except Exception as error:
            self.logger.warning(
                "could not report progress for deployment '%s': %s",
                entry.deployment.id,
                error,
            )
            return
        if "provider_ref" in fields:
            entry.reported_provider_ref = provider_ref
        if "progress_note" in fields:
            entry.reported_note = note

    def _monitoring_link(
        self,
        deployment: Deployment,
        *,
        preserve_existing: bool = False,
    ) -> str | None:
        if deployment.monitoring_mode.strip().lower() == "off":
            return None
        if self.monitoring is None:
            return deployment.monitoring_url if preserve_existing else None
        return self.monitoring.monitoring_link(deployment)

    async def _transition(
        self,
        deployment_id: str,
        update: DeploymentUpdate,
    ) -> _TransitionOutcome:
        target = update.status
        if target is None:
            raise ValueError("a status transition requires a target status")

        current: Deployment | None = None
        try:
            current = await self.platform.get_deployment(deployment_id)
        except PlatformRefusal as error:
            if error.status_code in {404, 410}:
                return _TransitionOutcome(_TransitionResult.GONE, error=error)
            self.logger.warning(
                "could not re-read deployment '%s' before transition: %s",
                deployment_id,
                error,
            )
        except Exception as error:
            self.logger.warning(
                "could not re-read deployment '%s' before transition: %s",
                deployment_id,
                error,
            )

        if current is not None and not status_transition_allowed(current.status, target):
            self.logger.warning(
                "refused deployment status transition for '%s': %s -> %s",
                deployment_id,
                current.status,
                target,
            )
            return _TransitionOutcome(
                _TransitionResult.REFUSED,
                current_status=current.status,
            )

        try:
            record = await self.platform.update_deployment(deployment_id, update)
        except PlatformRefusal as error:
            if error.status_code in {404, 410}:
                return _TransitionOutcome(_TransitionResult.GONE, error=error)
            self.logger.warning(
                "platform refused deployment status transition for '%s' to %s: %s",
                deployment_id,
                target,
                error,
            )
            return _TransitionOutcome(
                _TransitionResult.REFUSED,
                current_status=current.status if current is not None else None,
                error=error,
            )
        except Exception as error:
            self.logger.error(
                "deployment status transition failed for '%s' to %s: %s",
                deployment_id,
                target,
                error,
            )
            return _TransitionOutcome(_TransitionResult.ERROR, error=error)
        return _TransitionOutcome(
            _TransitionResult.APPLIED,
            record=record,
            current_status=current.status if current is not None else None,
        )

    async def _fail_task(
        self,
        task: SatelliteQueueTask,
        reason: str,
        error: str,
    ) -> None:
        try:
            await self.platform.update_task_status(
                task.id,
                SatelliteTaskStatus.FAILED,
                ErrorMessage(reason=reason, error=error),
            )
        except Exception as update_error:
            self.logger.error("could not fail task '%s': %s", task.id, update_error)

    async def _cleanup(self, deployment_id: str) -> None:
        try:
            await self._call_driver(
                "remove",
                lambda: self.driver.remove(deployment_id),
            )
        except Exception as error:
            self.logger.error("failed to clean up workload '%s': %s", deployment_id, error)
        await self._unregister(deployment_id)

    async def _unregister(self, deployment_id: str) -> None:
        try:
            await self.serving.unregister(deployment_id)
        except Exception as error:
            self.logger.error("failed to unregister deployment '%s': %s", deployment_id, error)

    async def _recent_logs(self, deployment_id: str) -> str:
        observation = await self._observe_one(deployment_id)
        return observation.recent_logs

    async def _observe_many(
        self,
        deployment_ids: Set[str],
    ) -> Mapping[str, WorkloadObservation]:
        try:
            bulk = await self._call_driver(
                "observe_all",
                lambda: self.driver.observe_all(deployment_ids),
            )
        except Exception as error:
            self.logger.warning("bulk workload observation failed: %s", error)
            return {
                deployment_id: WorkloadObservation(WorkloadState.UNKNOWN, error=str(error))
                for deployment_id in deployment_ids
            }
        if not isinstance(bulk, UnsupportedOperation):
            return bulk

        pairs = await asyncio.gather(
            *(self._observe_pair(deployment_id) for deployment_id in deployment_ids)
        )
        return dict(pairs)

    async def _observe_pair(self, deployment_id: str) -> tuple[str, WorkloadObservation]:
        return deployment_id, await self._observe_one(deployment_id)

    async def _observe_one(self, deployment_id: str) -> WorkloadObservation:
        try:
            return await self._call_driver(
                "observe",
                lambda: self.driver.observe(deployment_id),
            )
        except Exception as error:
            self.logger.warning("could not observe workload '%s': %s", deployment_id, error)
            return WorkloadObservation(WorkloadState.UNKNOWN, error=str(error))

    async def _call_driver[Result](
        self,
        operation: str,
        call: Callable[[], Awaitable[Result]],
    ) -> Result:
        async with self._driver_slots:
            try:
                async with asyncio.timeout(self.driver_call_timeout):
                    return await call()
            except TimeoutError as error:
                raise DriverCallTimeout(
                    f"driver {operation} timed out after {self.driver_call_timeout:g} seconds"
                ) from error


class _SecretResolutionError(RuntimeError):
    pass


def _deployment_id(task: SatelliteQueueTask) -> str | None:
    value = (task.payload or {}).get("deployment_id")
    return value if isinstance(value, str) and value else None


def _error_with_logs(error: str, logs: str, limit: int) -> str:
    recent = logs[-limit:]
    if error and recent:
        return f"{error}\n\nLogs:\n{recent}"
    if recent:
        return recent
    return error


def _without_secret_attributes(
    description: ModelDescription,
    deployment: Deployment,
) -> ModelDescription:
    if description.schema is None:
        return description
    schema = copy.deepcopy(dict(description.schema))
    components = schema.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    dynamic = schemas.get("DynamicAttributesModel") if isinstance(schemas, dict) else None
    properties = dynamic.get("properties") if isinstance(dynamic, dict) else None
    if isinstance(properties, dict):
        for attribute in deployment.dynamic_attributes_secrets or {}:
            properties.pop(attribute, None)
    return ModelDescription(
        manifest=description.manifest,
        schema=schema,
        reference_profile=description.reference_profile,
    )
