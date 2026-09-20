import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import FastAPI

from luml_satellite.authorization import AuthorizationVerdict
from luml_satellite.declaration import (
    DeploymentSettings,
    SatelliteConfiguration,
    derive_capabilities,
    settings_fields,
)
from luml_satellite.monitoring import (
    LocalDeployment,
    MetricRegistry,
    MonitoringBundle,
    default_registry,
)
from luml_satellite.monitoring.compute.models import (
    Alert,
    InferenceEvent,
    MetricResult,
    TimeWindow,
)
from luml_satellite.monitoring.dashboard.schemas import ProfileStatus
from luml_satellite.monitoring.storage.query_store import (
    DeploymentDescriptor,
    EventStatus,
    InferenceEvent as QueryInferenceEvent,
    InMemoryMonitoringStore as QueryMemoryStore,
    StoredMetricResult,
    StoredMetricTransition,
)
from luml_satellite.monitoring.storage.store import InMemoryMonitoringStore as WorkerMemoryStore
from luml_satellite.wire import Deployment, PlatformClient
from tests.helpers import DEPLOYMENT_ID, deployment_record


class DockerSettings(DeploymentSettings):
    pass


class AllowingAuthorizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        self.calls.append(api_key)
        return AuthorizationVerdict.ALLOWED


class VendorStore(QueryMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.worker = WorkerMemoryStore()
        self.close_calls = 0

    async def read_events(self, deployment_id: str, window: TimeWindow) -> list[InferenceEvent]:
        return await self.worker.read_events(deployment_id, window)

    async def write_result(self, result: MetricResult) -> None:
        await self.worker.write_result(result)
        deployment_id = UUID(result.deployment_id)
        for window in ("1h", "6h", "24h", "7d", "30d", "custom"):
            self.add_result(
                StoredMetricResult(
                    deployment_id=deployment_id,
                    group=result.metric,
                    window=window,
                    values=result.values,
                    severity=str(result.severity),
                    computed_at=result.window_end,
                )
            )

    async def active_alerts(self, deployment_id: str) -> list[Alert]:
        return await self.worker.active_alerts(deployment_id)

    async def save_alert(self, alert: Alert) -> None:
        await self.worker.save_alert(alert)

    async def record_metric_transition(
        self,
        deployment_id: str,
        metric: str,
        *,
        kind: str,
        error: str,
        window_end: datetime,
        at: datetime,
    ) -> None:
        await self.worker.record_metric_transition(
            deployment_id,
            metric,
            kind=kind,
            error=error,
            window_end=window_end,
            at=at,
        )
        self.transitions.append(
            StoredMetricTransition(metric=metric, kind=kind, error=error, at=at)
        )

    async def last_materialized_window(self, deployment_id: str) -> datetime | None:
        return await self.worker.last_materialized_window(deployment_id)

    async def aclose(self) -> None:
        self.close_calls += 1


def _configuration() -> SatelliteConfiguration:
    return SatelliteConfiguration(
        SATELLITE_TOKEN="token",
        MONITORING_FRAME_ANCESTORS="https://app.luml.ai",
    )


def _platform() -> PlatformClient:
    return PlatformClient("http://platform", "token")


def _local_deployment() -> LocalDeployment:
    return LocalDeployment(
        deployment_id=DEPLOYMENT_ID,
        monitoring_enabled=True,
        profile_status=ProfileStatus.ABSENT,
    )


async def test_capabilities_are_derived_from_the_real_bundle_registry_and_settings() -> None:
    store = VendorStore()
    registry = MetricRegistry(
        [metric for metric in default_registry().metrics() if metric.metric != "multivariate"]
    )
    bundle = MonitoringBundle(
        _configuration(),
        _platform(),
        lambda: [],
        registry=registry,
        worker_store=store,
        query_store=store,
    )

    capabilities = derive_capabilities(
        supported_variants=["pyfunc", "pipeline"],
        supported_tags_combinations=None,
        settings_type=DockerSettings,
        monitoring_bundle=bundle,
    )

    assert capabilities["monitoring"]["features"] == [
        "runtime",
        "traces",
        "alerts",
        "data_quality",
        "feature_drift",
        "output_drift",
    ]
    assert capabilities["deploy"]["extra_fields_form_spec"] == settings_fields(DockerSettings)
    await bundle.aclose()


async def test_worker_health_belongs_to_each_bundle_instance() -> None:
    first_store = VendorStore()
    second_store = VendorStore()
    first = MonitoringBundle(
        _configuration(),
        _platform(),
        lambda: [],
        worker_store=first_store,
        query_store=first_store,
    )
    second = MonitoringBundle(
        _configuration(),
        _platform(),
        lambda: [],
        worker_store=second_store,
        query_store=second_store,
    )
    await first.start()
    await asyncio.sleep(0)

    assert first.worker_health.snapshot(DEPLOYMENT_ID).running is True
    assert second.worker_health.snapshot(DEPLOYMENT_ID).running is False
    await first.aclose()
    await second.aclose()


async def test_vendor_store_is_wired_to_worker_dashboard_and_absolute_links() -> None:
    now = datetime.now(UTC)
    local = _local_deployment()
    store = VendorStore()
    store.add_deployment(
        DeploymentDescriptor(deployment_id=UUID(DEPLOYMENT_ID), name="vendor deployment")
    )
    store.add_event(
        QueryInferenceEvent(
            event_id="query-event",
            deployment_id=UUID(DEPLOYMENT_ID),
            ts=now - timedelta(seconds=30),
            status=EventStatus.SUCCESS,
            status_code=200,
            latency_ms=12.0,
        )
    )
    authorizer = AllowingAuthorizer()
    bundle = MonitoringBundle(
        _configuration(),
        _platform(),
        lambda: [local],
        worker_store=store,
        query_store=store,
        authorizer=authorizer,
        link_provider=lambda deployment: f"https://monitoring.vendor.example/{deployment.id}",
    )
    worker_window = bundle.worker.latest_window(now)
    store.worker.add_events(
        DEPLOYMENT_ID,
        [
            InferenceEvent(
                event_id="worker-event",
                deployment_id=DEPLOYMENT_ID,
                status="success",
                status_code=200,
                latency_ms=10.0,
                timestamp=worker_window.start + timedelta(seconds=1),
            )
        ],
    )
    application = FastAPI()
    bundle.mount(application)

    await bundle.worker.tick(now=now)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://satellite",
    ) as client:
        response = await client.get(
            f"/deployments/{DEPLOYMENT_ID}/monitoring/runtime",
            headers={"Authorization": "Bearer api-key"},
        )

    deployment = Deployment.model_validate(
        deployment_record(id=DEPLOYMENT_ID, monitoring_mode="full")
    )
    monitoring_off = deployment.model_copy(update={"monitoring_mode": "off"})
    assert response.status_code == 200
    assert response.json()["request_count"] == 1
    assert store.worker.results
    assert bundle.monitoring_link(deployment) == (
        f"https://monitoring.vendor.example/{DEPLOYMENT_ID}"
    )
    assert bundle.monitoring_link(monitoring_off) is None
    assert authorizer.calls == ["api-key"]

    await bundle.aclose()
    assert store.close_calls == 1
