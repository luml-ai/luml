import asyncio
from collections.abc import Callable, Iterable
from contextlib import suppress
from typing import Protocol, runtime_checkable
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
from luml_satellite.monitoring.compute.worker import MonitoringWorker, monitored_deployments
from luml_satellite.monitoring.dashboard.api import DeploymentNotHostedError, build_machine_router
from luml_satellite.monitoring.dashboard.app import register_monitoring
from luml_satellite.monitoring.dashboard.profile import deployment_descriptor
from luml_satellite.monitoring.ingest.instrumentation import InferenceInstrumentation
from luml_satellite.monitoring.ingest.telemetry import TelemetrySetup, create_telemetry
from luml_satellite.monitoring.storage.greptime import GreptimeMonitoringStore
from luml_satellite.monitoring.storage.greptime_query import GreptimeQueryStore
from luml_satellite.monitoring.storage.query_store import MonitoringStore as QueryStore
from luml_satellite.monitoring.storage.store import MonitoringStore as WorkerStore
from luml_satellite.wire import Deployment, PlatformClient
from luml_satellite.workload import Recorder

type DeploymentProvider = Callable[[], Iterable[LocalDeployment]]
type MonitoringLinkProvider = Callable[[Deployment], str | None]


@runtime_checkable
class _AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


class MonitoringBundle:
    def __init__(
        self,
        configuration: SatelliteConfiguration,
        platform: PlatformClient,
        deployments: DeploymentProvider,
        *,
        registry: MetricRegistry | None = None,
        worker_store: WorkerStore | None = None,
        query_store: QueryStore | None = None,
        telemetry: TelemetrySetup | None = None,
        authorizer: Authorizer | None = None,
        link_provider: MonitoringLinkProvider | None = None,
    ) -> None:
        self.configuration = configuration
        self.platform = platform
        self.registry = registry or default_registry(
            latency_p95_threshold_ms=configuration.MONITORING_LATENCY_P95_THRESHOLD_MS
        )
        self.worker_health = WorkerHealth()
        self._deployments = deployments
        self._link_provider = link_provider
        self.worker_store = worker_store or self._default_worker_store()
        self.query_store = query_store or self._default_query_store()
        self.telemetry = telemetry or create_telemetry(
            endpoint=configuration.OTEL_EXPORTER_OTLP_ENDPOINT,
            enabled=configuration.MONITORING_ENABLED,
        )
        self.authorizer = authorizer or PlatformAuthorizer(platform)
        self.recorder: Recorder = InferenceInstrumentation(self.telemetry)
        self.worker = MonitoringWorker(
            store=self.worker_store,
            registry=self.registry,
            provider=lambda: monitored_deployments(self._deployments()),
            window_seconds=configuration.MONITORING_WINDOW_SEC,
            interval_seconds=configuration.MONITORING_INTERVAL_SEC,
            health=self.worker_health,
            max_backfill_windows=configuration.MONITORING_BACKFILL_MAX_WINDOWS,
        )
        self._worker_task: asyncio.Task[None] | None = None
        self._closed = False

    @property
    def monitoring_features(self) -> tuple[str, ...]:
        return monitoring_features(self.registry)

    def monitoring_link(self, deployment: Deployment) -> str | None:
        if deployment.monitoring_mode.strip().lower() != "full":
            return None
        if self._link_provider is not None:
            return self._link_provider(deployment)
        return f"/deployments/{deployment.id}/monitoring"

    def mount(self, application: FastAPI) -> None:
        @application.exception_handler(DeploymentNotHostedError)
        async def deployment_not_hosted(
            request: Request, error: DeploymentNotHostedError
        ) -> JSONResponse:
            return JSONResponse(
                status_code=404,
                content={"detail": error.detail, "code": error.code},
            )

        register_monitoring(
            application,
            introspect=self.platform.introspect_monitoring_token,
            frame_ancestors=self.configuration.monitoring_frame_ancestors(),
            session_ttl_seconds=self.configuration.MONITORING_SESSION_TTL_SECONDS,
            data_store=self.query_store,
            health_source=self._health_source,
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

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("monitoring bundle is closed")
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(
                self.worker.run_forever(),
                name="luml-monitoring-worker",
            )

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.worker.stop()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task
        closed: set[int] = set()
        for store in (self.worker_store, self.query_store):
            if id(store) in closed:
                continue
            closed.add(id(store))
            if isinstance(store, _AsyncCloseable):
                with suppress(Exception):
                    await store.aclose()
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
            profile_source=lambda deployment_id: self._profile(deployment_id),
            profile_status_source=lambda deployment_id: self._profile_status(deployment_id),
            deployment_source=lambda deployment_id: self._descriptor(deployment_id),
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

    def _is_hosted(self, deployment_id: UUID) -> bool:
        return self._find_deployment(deployment_id) is not None

    def _profile(self, deployment_id: UUID) -> dict[str, object] | None:
        deployment = self._find_deployment(deployment_id)
        return deployment.reference_profile if deployment is not None else None

    def _profile_status(self, deployment_id: UUID) -> str:
        deployment = self._find_deployment(deployment_id)
        return str(deployment.profile_status) if deployment is not None else "absent"

    def _descriptor(self, deployment_id: UUID) -> dict[str, object] | None:
        deployment = self._find_deployment(deployment_id)
        return deployment_descriptor(deployment) if deployment is not None else None

    def _health_source(self, deployment_id: UUID) -> tuple[HealthSnapshot, tuple[float, float]]:
        return (
            self.worker_health.snapshot(str(deployment_id)),
            (
                self.configuration.MONITORING_WINDOW_SEC,
                self.configuration.MONITORING_INTERVAL_SEC,
            ),
        )
