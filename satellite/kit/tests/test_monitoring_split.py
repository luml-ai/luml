import os
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI

from luml_satellite.authorization import AuthorizationVerdict
from luml_satellite.declaration import SatelliteConfiguration
from luml_satellite.monitoring import (
    SESSION_COOKIE_NAME,
    Alert,
    MetricFailure,
    MetricRegistry,
    MetricResult,
    MonitoredDeployment,
    MonitoringBundle,
    MonitoringQueryService,
    MonitoringRole,
    MonitoringSessionStore,
    MonitoringWorker,
    PlatformDeploymentSource,
    TimeWindow,
    WorkerHeartbeat,
    default_registry,
    heartbeat_file_is_fresh,
    register_monitoring,
)
from luml_satellite.monitoring.compute.models import InferenceEvent as WorkerInferenceEvent
from luml_satellite.monitoring.dashboard.schemas import WorkerHealthResponse
from luml_satellite.monitoring.storage.query_store import (
    InMemoryMonitoringStore as QueryMemoryStore,
    StoredMetricResult,
)
from luml_satellite.monitoring.storage.store import (
    InMemoryMonitoringStore as WorkerMemoryStore,
)
from luml_satellite.monitoring.worker_main import probe_exit_code
from luml_satellite.testing import FakePlatform
from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import (
    MONITORING_READ_SCOPE,
    MonitoringIntrospection,
    MonitoringTokenClaims,
    PlatformClient,
)
from tests.helpers import DEPLOYMENT_ID, deployment_record


class AllowingAuthorizer:
    async def authorize(self, api_key: str) -> AuthorizationVerdict:
        return AuthorizationVerdict.ALLOWED


class SharedMemoryStore(QueryMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.worker_store = WorkerMemoryStore()

    async def read_events(
        self, deployment_id: str, window: TimeWindow
    ) -> list[WorkerInferenceEvent]:
        return await self.worker_store.read_events(deployment_id, window)

    async def write_result(self, result: MetricResult) -> None:
        await self.worker_store.write_result(result)
        for window in ("1h", "6h", "24h", "7d", "30d", "custom"):
            self.add_result(
                StoredMetricResult(
                    deployment_id=UUID(result.deployment_id),
                    group=result.metric,
                    window=window,
                    values=result.values,
                    severity=str(result.severity),
                    computed_at=result.window_end,
                )
            )

    async def active_alerts(self, deployment_id: str) -> list[Alert]:
        return await self.worker_store.active_alerts(deployment_id)

    async def save_alert(self, alert: Alert) -> None:
        await self.worker_store.save_alert(alert)

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
        await self.worker_store.record_metric_transition(
            deployment_id,
            metric,
            kind=kind,
            error=error,
            window_end=window_end,
            at=at,
        )

    async def last_materialized_window(self, deployment_id: str) -> datetime | None:
        return await self.worker_store.last_materialized_window(deployment_id)


def _configuration(**overrides: object) -> SatelliteConfiguration:
    values: dict[str, Any] = {
        "SATELLITE_TOKEN": "satellite-token",
        "MONITORING_SESSION_SECRET": "shared-session-secret",
        "MONITORING_INTERVAL_SEC": 10,
        "MONITORING_WINDOW_SEC": 60,
    }
    values.update(overrides)
    return SatelliteConfiguration(**values)


def _session_cookie(response: httpx.Response) -> str:
    cookie: SimpleCookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie[SESSION_COOKIE_NAME].value


async def test_dashboard_sessions_cross_replicas_slide_on_queries_and_stop_at_cap() -> None:
    now = [0.0]
    deployment_id = UUID(DEPLOYMENT_ID)
    claims = MonitoringTokenClaims(
        deployment_id=deployment_id,
        satellite_id=UUID(int=2),
        user_id=UUID(int=3),
        scope=MONITORING_READ_SCOPE,
        jti=UUID(int=4),
        exp=9999999999,
    )

    async def introspect(token: str) -> MonitoringIntrospection:
        return MonitoringIntrospection(active=True, claims=claims)

    applications = []
    for _ in range(2):
        application = FastAPI()
        register_monitoring(
            application,
            introspect=introspect,
            frame_ancestors=[],
            session_store=MonitoringSessionStore(
                "shared-secret",
                ttl_seconds=60,
                max_age_seconds=120,
                clock=lambda: now[0],
            ),
            data_store=QueryMemoryStore(),
            clock=lambda: now[0],
            cookie_secure=False,
        )
        applications.append(application)

    clients = [
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://dashboard"
        )
        for application in applications
    ]
    try:
        launch = await clients[0].get(
            "/monitoring/launch", params={"token": "launch"}, follow_redirects=False
        )
        cookie = _session_cookie(launch)
        replacement = "a" if cookie[-1] != "a" else "b"
        tampered = await clients[1].get(
            "/monitoring/api/session",
            headers={"cookie": f"{SESSION_COOKIE_NAME}={cookie[:-1]}{replacement}"},
        )

        now[0] = 40
        first_query = await clients[1].get(
            "/monitoring/api/runtime",
            headers={"cookie": f"{SESSION_COOKIE_NAME}={cookie}"},
        )
        cookie = _session_cookie(first_query)

        now[0] = 90
        second_query = await clients[0].get(
            "/monitoring/api/runtime",
            headers={"cookie": f"{SESSION_COOKIE_NAME}={cookie}"},
        )
        cookie = _session_cookie(second_query)

        now[0] = 140
        expired = await clients[1].get(
            "/monitoring/api/session",
            headers={"cookie": f"{SESSION_COOKIE_NAME}={cookie}"},
        )
    finally:
        for client in clients:
            await client.aclose()

    assert first_query.status_code == 200
    assert second_query.status_code == 200
    assert tampered.status_code == 401
    assert expired.status_code == 401


async def test_dashboard_unknown_machine_route_uses_contract_body() -> None:
    bundle = MonitoringBundle(
        _configuration(),
        PlatformClient("http://platform", "satellite-token"),
        role=MonitoringRole.DASHBOARD,
        query_store=QueryMemoryStore(),
        authorizer=AllowingAuthorizer(),
    )
    application = FastAPI()
    bundle.mount(application)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://dashboard"
    ) as client:
        machine = await client.get(
            f"/deployments/{DEPLOYMENT_ID}/monitoring/not-a-route",
            headers={"Authorization": "Bearer key"},
        )
        dashboard = await client.get("/monitoring/not-a-route")
        liveness = await client.get("/livez")

    assert machine.status_code == 404
    assert machine.json() == {"detail": "Not Found", "code": "unknown_route"}
    assert dashboard.status_code == 404
    assert dashboard.json() == {"detail": "Not Found"}
    assert liveness.status_code == 200
    await bundle.aclose()


async def test_split_worker_heartbeat_drives_dashboard_and_probe(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    store = SharedMemoryStore()
    heartbeat_file = tmp_path / "worker-heartbeat"
    profile = {
        "task_type": "regression",
        "feature_summaries": {
            "numerical_features": {"age": {"position": 0, "min": 18.0, "max": 75.0}}
        },
    }
    worker = MonitoringWorker(
        store=store,
        registry=default_registry(),
        provider=lambda: [MonitoredDeployment(DEPLOYMENT_ID, profile=profile)],
        window_seconds=60,
        interval_seconds=10,
        clock=lambda: now,
        heartbeat_file=heartbeat_file,
    )
    window = worker.latest_window(now)
    store.worker_store.add_events(
        DEPLOYMENT_ID,
        [
            WorkerInferenceEvent(
                event_id="event",
                deployment_id=DEPLOYMENT_ID,
                status="success",
                status_code=200,
                latency_ms=12,
                inputs={"age": 30},
                timestamp=window.start + timedelta(seconds=1),
            )
        ],
    )

    await worker.tick(now)

    bundle = MonitoringBundle(
        _configuration(),
        PlatformClient("http://platform", "satellite-token"),
        role=MonitoringRole.DASHBOARD,
        query_store=store,
        authorizer=AllowingAuthorizer(),
    )
    application = FastAPI()
    bundle.mount(application)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://dashboard"
    ) as client:
        response = await client.get(
            f"/deployments/{DEPLOYMENT_ID}/monitoring/worker",
            headers={"Authorization": "Bearer key"},
        )

    assert response.status_code == 200
    assert set(response.json()) == set(WorkerHealthResponse.model_fields)
    assert response.json()["running"] is True
    assert response.json()["last_tick_at"] == now.isoformat().replace("+00:00", "Z")
    assert {result.metric for result in store.worker_store.results} >= {
        "runtime",
        "data_quality",
    }
    assert heartbeat_file_is_fresh(heartbeat_file, interval_seconds=10)

    stale = datetime.now(UTC).timestamp() - 31
    os.utime(heartbeat_file, (stale, stale))
    assert not heartbeat_file_is_fresh(heartbeat_file, interval_seconds=10)
    probe_configuration = _configuration(
        MONITORING_HEARTBEAT_FILE=str(heartbeat_file),
        MONITORING_INTERVAL_SEC=10,
    )
    assert probe_exit_code(probe_configuration) == 1
    heartbeat_file.touch()
    assert probe_exit_code(probe_configuration) == 0
    await bundle.aclose()


async def test_worker_heartbeat_keeps_per_deployment_progress_and_failures() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SharedMemoryStore()
    worker = MonitoringWorker(
        store=store,
        registry=MetricRegistry([]),
        provider=lambda: [MonitoredDeployment(DEPLOYMENT_ID)],
        window_seconds=60,
        interval_seconds=10,
        clock=lambda: now,
    )
    worker.health.window_processed(DEPLOYMENT_ID, now - timedelta(seconds=4), now)
    worker.health.metric_failed(DEPLOYMENT_ID, "runtime", "broken", now)

    await worker.tick(now)

    heartbeat = (await store.read_worker_heartbeats())[0]
    deployment = heartbeat.deployments[DEPLOYMENT_ID]
    assert deployment.windows_processed == 2
    assert deployment.last_window_end == now
    assert deployment.last_lag_seconds == 0
    assert deployment.failures == (MetricFailure("runtime", "broken", now),)


async def test_shards_partition_deployments_and_dashboard_merges_heartbeats() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    deployment_ids = [str(UUID(int=index + 1)) for index in range(20)]
    deployments = [MonitoredDeployment(identifier) for identifier in deployment_ids]
    store = SharedMemoryStore()
    workers = [
        MonitoringWorker(
            store=store,
            registry=MetricRegistry([]),
            provider=lambda: deployments,
            window_seconds=60,
            interval_seconds=10,
            shard_index=index,
            shard_count=2,
        )
        for index in range(2)
    ]

    for worker in workers:
        await worker.tick(now)

    heartbeats = await store.read_worker_heartbeats()
    selected = [set(heartbeat.deployments) for heartbeat in heartbeats]
    assert selected[0].isdisjoint(selected[1])
    assert selected[0] | selected[1] == set(deployment_ids)

    expected = WorkerHeartbeat.merge(heartbeats, UUID(deployment_ids[-1]), now=now)
    assert expected is not None
    assert expected.running is True
    dashboard = MonitoringQueryService(store, clock=lambda: now.timestamp())
    for deployment_id in (next(iter(selected[0])), next(iter(selected[1]))):
        response = await dashboard.worker_health(UUID(deployment_id))
        assert response.running is True
        assert response.last_tick_at == now


async def test_platform_source_caches_active_deployments_and_uses_companion_token() -> None:
    fake = FakePlatform(token="satellite-token")
    fake.add_deployment(
        deployment_record(status="active", monitoring_mode="full", id=DEPLOYMENT_ID)
    )
    fake.add_deployment(
        deployment_record(
            id="10000000-0000-0000-0000-000000000002",
            status="pending",
            monitoring_mode="full",
        )
    )
    sidecar_requests: list[httpx.Request] = []

    def sidecar(request: httpx.Request) -> httpx.Response:
        sidecar_requests.append(request)
        if request.url.path.endswith("/manifest"):
            return httpx.Response(200, json={"producer_tags": []})
        return httpx.Response(
            200,
            json={
                "task_type": "classification",
                "feature_summaries": {"numerical_features": {"x": {}}},
            },
        )

    now = [0.0]
    deriver = TokenDeriver("satellite-token", "stable-key")
    async with (
        PlatformClient("http://platform", "satellite-token", transport=fake.transport) as platform,
        httpx.AsyncClient(transport=httpx.MockTransport(sidecar)) as sidecar_client,
    ):
        source = PlatformDeploymentSource(
            platform,
            "http://sidecar/{deployment_id}",
            deriver,
            client=sidecar_client,
            clock=lambda: now[0],
        )
        first = await source.deployments()
        second = await source.deployments()
        now[0] = 61
        third = await source.deployments()

    assert [deployment.deployment_id for deployment in first] == [DEPLOYMENT_ID]
    assert second == first
    assert third == first
    assert len([request for request in fake.requests if request.path.endswith("/deployments")]) == 2
    assert len(sidecar_requests) == 4
    assert sidecar_requests[0].url.path == f"/{DEPLOYMENT_ID}/reference_profile"
    assert {request.url.path for request in sidecar_requests[:2]} == {
        f"/{DEPLOYMENT_ID}/reference_profile",
        f"/{DEPLOYMENT_ID}/manifest",
    }
    assert {request.headers["Authorization"] for request in sidecar_requests} == {
        f"Bearer {deriver.companion_token(DEPLOYMENT_ID)}"
    }
    local = await source.local_deployment(UUID(DEPLOYMENT_ID))
    assert local is not None
    assert local.metadata.name == "classifier"
    assert local.reference_profile == (
        {
            "task_type": "classification",
            "feature_summaries": {"numerical_features": {"x": {}}},
        }
    )
