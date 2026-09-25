import asyncio
from collections.abc import Callable, Iterable
from contextlib import suppress
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from luml_satellite.authorization import AuthorizationVerdict, Authorizer, PlatformAuthorizer
from luml_satellite.declaration import SatelliteConfiguration
from luml_satellite.monitoring.compute.health import HealthSnapshot, WorkerHealth
from luml_satellite.monitoring.compute.models import LocalDeployment
from luml_satellite.monitoring.compute.registry import (
    MetricRegistry,
    default_registry,
    monitoring_features,
)
from luml_satellite.monitoring.compute.worker import MonitoringWorker
from luml_satellite.monitoring.dashboard.api import DeploymentNotHostedError, build_machine_router
from luml_satellite.monitoring.dashboard.app import (
    install_machine_unknown_route,
    register_monitoring,
)
from luml_satellite.monitoring.dashboard.profile import deployment_descriptor
from luml_satellite.monitoring.dashboard.session import MonitoringSessionStore
from luml_satellite.monitoring.deployments import DeploymentSource, ServedDeploymentSource
from luml_satellite.monitoring.ingest.instrumentation import InferenceInstrumentation
from luml_satellite.monitoring.ingest.telemetry import TelemetrySetup, create_telemetry
from luml_satellite.monitoring.storage.greptime import GreptimeMonitoringStore
from luml_satellite.monitoring.storage.greptime_query import GreptimeQueryStore
from luml_satellite.monitoring.storage.query_store import (
    InMemoryMonitoringStore as InMemoryQueryStore,
    MonitoringStore as QueryStore,
)
from luml_satellite.monitoring.storage.store import MonitoringStore as WorkerStore
from luml_satellite.tokens import TokenDeriver, TokenPurpose
from luml_satellite.wire import Deployment, PlatformClient
from luml_satellite.workload import NoOpRecorder, Recorder

type DeploymentProvider = Callable[[], Iterable[LocalDeployment]]
type MonitoringLinkProvider = Callable[[Deployment], str | None]


class MonitoringRole(StrEnum):
    ALL = "all"
    SATELLITE = "satellite"
    WORKER = "worker"
    DASHBOARD = "dashboard"


@runtime_checkable
class _AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


class MonitoringBundle:
    def __init__(
        self,
        configuration: SatelliteConfiguration,
        platform: PlatformClient,
        deployments: DeploymentProvider | None = None,
        *,
        role: MonitoringRole | str = MonitoringRole.ALL,
        deployment_source: DeploymentSource | None = None,
        registry: MetricRegistry | None = None,
        worker_store: WorkerStore | None = None,
        query_store: QueryStore | None = None,
        telemetry: TelemetrySetup | None = None,
        authorizer: Authorizer | None = None,
        link_provider: MonitoringLinkProvider | None = None,
        shard_index: int | None = None,
        shard_count: int | None = None,
        heartbeat_file: Path | str | None = None,
    ) -> None:
        self.configuration = configuration
        self.platform = platform
        self.role = MonitoringRole(role)
        self.registry = registry or default_registry(
            latency_p95_threshold_ms=configuration.MONITORING_LATENCY_P95_THRESHOLD_MS
        )
        self.worker_health = WorkerHealth()
        self._deployments = deployments or (lambda: ())
        self._deployment_source = deployment_source
        if self._deployment_source is None and deployments is not None:
            self._deployment_source = ServedDeploymentSource(deployments)
        self._link_provider = link_provider
        self.authorizer = authorizer or PlatformAuthorizer(platform)

        worker_enabled = self.role in (MonitoringRole.ALL, MonitoringRole.WORKER)
        dashboard_enabled = self.role in (MonitoringRole.ALL, MonitoringRole.DASHBOARD)
        if worker_enabled and self._deployment_source is None:
            raise ValueError("a deployment source is required for the monitoring worker")

        self.worker_store = worker_store or (
            self._default_worker_store() if worker_enabled else None
        )
        self.query_store = query_store or (
            self._default_query_store() if dashboard_enabled else None
        )
        self.telemetry = telemetry or (
            create_telemetry(
                endpoint=configuration.OTEL_EXPORTER_OTLP_ENDPOINT,
                enabled=configuration.MONITORING_ENABLED,
            )
            if self.role is MonitoringRole.ALL
            else None
        )
        self.recorder: Recorder = (
            InferenceInstrumentation(self.telemetry)
            if self.telemetry is not None
            else NoOpRecorder()
        )
        self._worker: MonitoringWorker | None = None
        if worker_enabled:
            assert self.worker_store is not None
            assert self._deployment_source is not None
            resolved_heartbeat_file = (
                configuration.MONITORING_HEARTBEAT_FILE
                if heartbeat_file is None and self.role is MonitoringRole.WORKER
                else heartbeat_file
            )
            self._worker = MonitoringWorker(
                store=self.worker_store,
                registry=self.registry,
                provider=self._deployment_source.deployments,
                window_seconds=configuration.MONITORING_WINDOW_SEC,
                interval_seconds=configuration.MONITORING_INTERVAL_SEC,
                health=self.worker_health,
                max_backfill_windows=configuration.MONITORING_BACKFILL_MAX_WINDOWS,
                shard_index=(
                    configuration.MONITORING_WORKER_SHARD_INDEX
                    if shard_index is None
                    else shard_index
                ),
                shard_count=(
                    configuration.MONITORING_WORKER_SHARD_COUNT
                    if shard_count is None
                    else shard_count
                ),
                heartbeat_file=resolved_heartbeat_file,
            )
        self._worker_task: asyncio.Task[None] | None = None
        self._closed = False

    @property
    def monitoring_features(self) -> tuple[str, ...]:
        return monitoring_features(self.registry)

    @property
    def worker(self) -> MonitoringWorker:
        if self._worker is None:
            raise RuntimeError("this monitoring bundle has no worker")
        return self._worker

    def monitoring_link(self, deployment: Deployment) -> str | None:
        if deployment.monitoring_mode.strip().lower() != "full":
            return None
        if self._link_provider is not None:
            return self._link_provider(deployment)
        return f"/deployments/{deployment.id}/monitoring"

    def mount(self, application: FastAPI) -> None:
        if self.role is MonitoringRole.WORKER:
            raise RuntimeError("the monitoring worker role has no HTTP routes")

        @application.exception_handler(DeploymentNotHostedError)
        async def deployment_not_hosted(
            request: Request, error: DeploymentNotHostedError
        ) -> JSONResponse:
            return JSONResponse(
                status_code=404,
                content={"detail": error.detail, "code": error.code},
            )

        query_store = self.query_store or InMemoryQueryStore()
        register_monitoring(
            application,
            introspect=self.platform.introspect_monitoring_token,
            frame_ancestors=self.configuration.monitoring_frame_ancestors(),
            session_ttl_seconds=self.configuration.MONITORING_SESSION_TTL_SECONDS,
            session_store=MonitoringSessionStore(
                self._session_secret(),
                ttl_seconds=self.configuration.MONITORING_SESSION_TTL_SECONDS,
            ),
            data_store=query_store,
            health_source=(self._health_source if self.role is MonitoringRole.ALL else None),
        )
        security = HTTPBearer(auto_error=False)

        async def verify_token(
            credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
        ) -> None:
            if credentials is None:
                raise HTTPException(status_code=403, detail="Not authenticated")
            verdict = await self.authorizer.authorize(credentials.credentials)
            if verdict is AuthorizationVerdict.DENIED:
                raise HTTPException(status_code=401, detail="Invalid API key")
            if verdict is AuthorizationVerdict.UNAVAILABLE:
                raise HTTPException(status_code=502, detail="Authorization failed")

        application.include_router(
            build_machine_router(self._is_hosted),
            dependencies=[Depends(verify_token)],
        )
        if self.role is MonitoringRole.DASHBOARD:
            self._mount_dashboard_liveness(application)
            install_machine_unknown_route(application)

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("monitoring bundle is closed")
        if self._worker is None:
            return
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(
                self._worker.run_forever(),
                name="luml-monitoring-worker",
            )

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._worker is not None:
            self._worker.stop()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task
        closed: set[int] = set()
        for closeable in (self.worker_store, self.query_store, self._deployment_source):
            if closeable is None or id(closeable) in closed:
                continue
            closed.add(id(closeable))
            if isinstance(closeable, _AsyncCloseable):
                with suppress(Exception):
                    await closeable.aclose()
        if self.telemetry is not None:
            self.telemetry.shutdown()

    def _default_worker_store(self) -> GreptimeMonitoringStore:
        return GreptimeMonitoringStore(
            host=self.configuration.GREPTIMEDB_HOST,
            port=self.configuration.GREPTIMEDB_HTTP_PORT,
            database=self.configuration.GREPTIMEDB_DATABASE,
            username=self.configuration.GREPTIMEDB_USERNAME,
            password=self.configuration.GREPTIMEDB_PASSWORD,
            events_ttl=self.configuration.MONITORING_EVENTS_TTL,
            results_ttl=self.configuration.MONITORING_RESULTS_TTL,
            alerts_ttl=self.configuration.MONITORING_ALERTS_TTL,
            traces_ttl=self.configuration.MONITORING_TRACES_TTL,
            metrics_ttl=self.configuration.MONITORING_METRICS_TTL,
        )

    def _default_query_store(self) -> GreptimeQueryStore:
        return GreptimeQueryStore(
            host=self.configuration.GREPTIMEDB_HOST,
            port=self.configuration.GREPTIMEDB_HTTP_PORT,
            database=self.configuration.GREPTIMEDB_DATABASE,
            username=self.configuration.GREPTIMEDB_USERNAME,
            password=self.configuration.GREPTIMEDB_PASSWORD,
            profile_source=self._profile,
            profile_status_source=self._profile_status,
            deployment_source=self._descriptor,
        )

    def _find_deployment(self, deployment_id: UUID) -> LocalDeployment | None:
        expected = str(deployment_id)
        return next(
            (
                deployment
                for deployment in self._deployments()
                if deployment.deployment_id == expected
            ),
            None,
        )

    async def _is_hosted(self, deployment_id: UUID) -> bool:
        if self._deployment_source is not None:
            return await self._deployment_source.is_hosted(deployment_id)
        return self.role is MonitoringRole.DASHBOARD

    async def _profile(self, deployment_id: UUID) -> dict[str, Any] | None:
        deployment = await self._source_deployment(deployment_id)
        return deployment.reference_profile if deployment is not None else None

    async def _profile_status(self, deployment_id: UUID) -> str:
        deployment = await self._source_deployment(deployment_id)
        return str(deployment.profile_status) if deployment is not None else "absent"

    async def _descriptor(self, deployment_id: UUID) -> dict[str, Any] | None:
        deployment = await self._source_deployment(deployment_id)
        return deployment_descriptor(deployment) if deployment is not None else None

    async def _source_deployment(self, deployment_id: UUID) -> LocalDeployment | None:
        if self._deployment_source is not None:
            return await self._deployment_source.local_deployment(deployment_id)
        return self._find_deployment(deployment_id)

    def _health_source(self, deployment_id: UUID) -> tuple[HealthSnapshot, tuple[float, float]]:
        return (
            self.worker_health.snapshot(str(deployment_id)),
            (
                self.configuration.MONITORING_WINDOW_SEC,
                self.configuration.MONITORING_INTERVAL_SEC,
            ),
        )

    def _session_secret(self) -> str:
        if self.configuration.MONITORING_SESSION_SECRET is not None:
            return self.configuration.MONITORING_SESSION_SECRET
        deriver = TokenDeriver(
            self.configuration.SATELLITE_TOKEN,
            self.configuration.DERIVATION_KEY,
        )
        return deriver.derive(TokenPurpose.MONITORING_SESSION, "dashboard")

    @staticmethod
    def _mount_dashboard_liveness(application: FastAPI) -> None:
        @application.get("/livez", include_in_schema=False)
        async def livez() -> dict[str, str]:
            return {"status": "healthy"}
