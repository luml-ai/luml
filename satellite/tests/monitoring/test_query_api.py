import uuid

from tests.support import FIXED_NOW, ago, build_app, client_for, introspect_returning

from agent.monitoring import (
    SESSION_COOKIE_NAME,
    InferenceEvent,
    InMemoryMonitoringStore,
    MonitoringSessionStore,
    ReferenceFeatureProfile,
    ReferenceProfile,
    StoredAlert,
    StoredMetricResult,
)
from agent.schemas.monitoring import MONITORING_READ_SCOPE, MonitoringIntrospection

_INACTIVE = introspect_returning(MonitoringIntrospection(active=False))


def _cookie(session_id: str) -> dict[str, str]:
    return {"cookie": f"{SESSION_COOKIE_NAME}={session_id}"}


def _event(deployment_id: uuid.UUID) -> InferenceEvent:
    return InferenceEvent(
        event_id=str(uuid.uuid4()),
        deployment_id=deployment_id,
        ts=ago(100),
        status="success",
        status_code=200,
        latency_ms=12.0,
    )


async def test_missing_session_is_unauthorized() -> None:
    app = build_app(_INACTIVE, data_store=InMemoryMonitoringStore())

    paths = (
        "/header",
        "/overview",
        "/runtime",
        "/data-quality",
        "/feature-drift",
        "/reference-profile",
        "/alerts",
        "/traces",
    )
    async with client_for(app) as client:
        for path in paths:
            resp = await client.get(f"/monitoring/api{path}")
            assert resp.status_code == 401


async def test_endpoints_derive_deployment_from_session() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    for _ in range(3):
        store.add_event(_event(dep_a))
    for _ in range(7):
        store.add_event(_event(dep_b))

    sessions = MonitoringSessionStore()
    session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
    session_b = sessions.create(dep_b, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW)

    async with client_for(app) as client:
        resp_a = await client.get("/monitoring/api/runtime", headers=_cookie(session_a.session_id))
        resp_b = await client.get("/monitoring/api/runtime", headers=_cookie(session_b.session_id))

    assert resp_a.json()["request_count"] == 3
    assert resp_b.json()["request_count"] == 7


async def test_client_supplied_deployment_id_cannot_read_other_deployment() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    for _ in range(3):
        store.add_event(_event(dep_a))
    for _ in range(7):
        store.add_event(_event(dep_b))

    sessions = MonitoringSessionStore()
    session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW)

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/runtime",
            params={"deployment_id": str(dep_b)},  # attempt to read B from A's session
            headers=_cookie(session_a.session_id),
        )

    assert resp.json()["request_count"] == 3  # still deployment A


async def test_store_unavailable_returns_unavailable_state_not_500() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.unavailable = True
    sessions = MonitoringSessionStore()
    session = sessions.create(dep, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store)

    async with client_for(app) as client:
        resp = await client.get("/monitoring/api/overview", headers=_cookie(session.session_id))

    assert resp.status_code == 200
    assert resp.json()["state"] == "unavailable"


def _feature_drift_result(deployment_id: uuid.UUID, psi: float) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=deployment_id,
        group="feature_drift",
        window="24h",
        values={"features": {"income": {"psi": psi, "status": "critical"}}},
        severity="critical",
    )


async def test_feature_drift_endpoint_scoped_to_session() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_result(_feature_drift_result(dep_a, psi=0.30))
    store.add_result(_feature_drift_result(dep_b, psi=0.70))

    sessions = MonitoringSessionStore()
    session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
    session_b = sessions.create(dep_b, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store)

    async with client_for(app) as client:
        resp_a = await client.get(
            "/monitoring/api/feature-drift",
            params={"deployment_id": str(dep_b)},  # A's session must ignore this
            headers=_cookie(session_a.session_id),
        )
        resp_b = await client.get(
            "/monitoring/api/feature-drift", headers=_cookie(session_b.session_id)
        )

    assert resp_a.json()["features"][0]["psi"] == 0.30  # still deployment A
    assert resp_b.json()["features"][0]["psi"] == 0.70


async def test_reference_profile_endpoint_scoped_to_session() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_profile(
        ReferenceProfile(
            deployment_id=dep_a,
            baseline_label="baseline-a",
            features={"income": ReferenceFeatureProfile(feature="income", kind="numeric")},
        )
    )

    sessions = MonitoringSessionStore()
    session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
    session_b = sessions.create(dep_b, MONITORING_READ_SCOPE)  # no profile loaded for B
    app = build_app(_INACTIVE, session_store=sessions, data_store=store)

    async with client_for(app) as client:
        resp_a = await client.get(
            "/monitoring/api/reference-profile", headers=_cookie(session_a.session_id)
        )
        resp_b = await client.get(
            "/monitoring/api/reference-profile", headers=_cookie(session_b.session_id)
        )

    assert resp_a.json()["state"] == "ok"
    assert resp_a.json()["features"] == ["income"]
    assert resp_b.json()["state"] == "empty"  # B cannot see A's profile


async def test_invalid_window_is_rejected() -> None:
    dep = uuid.uuid4()
    sessions = MonitoringSessionStore()
    session = sessions.create(dep, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=InMemoryMonitoringStore())

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/overview",
            params={"window": "99y"},
            headers=_cookie(session.session_id),
        )

    assert resp.status_code == 422


async def test_alerts_endpoint_is_read_only() -> None:
    dep = uuid.uuid4()
    sessions = MonitoringSessionStore()
    session = sessions.create(dep, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=InMemoryMonitoringStore())

    async with client_for(app) as client:
        get = await client.get("/monitoring/api/alerts", headers=_cookie(session.session_id))
        post = await client.post("/monitoring/api/alerts", headers=_cookie(session.session_id))

    assert get.status_code == 200
    assert post.status_code == 405  # no acknowledge/resolve — read-only in this slice


async def test_alerts_endpoint_grouped_and_scoped_to_session() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_alert(
        StoredAlert(
            deployment_id=dep_a,
            group="runtime",
            metric="error_rate",
            severity="critical",
            current_value=0.44,
            threshold=0.1,
            last_seen=ago(60),
        )
    )
    store.add_alert(
        StoredAlert(
            deployment_id=dep_b,
            group="feature_drift",
            metric="psi",
            feature="income",
            severity="warning",
            last_seen=ago(60),
        )
    )
    sessions = MonitoringSessionStore()
    session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store)

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/alerts",
            params={"deployment_id": str(dep_b)},  # A's session must ignore this
            headers=_cookie(session_a.session_id),
        )

    body = resp.json()
    assert [g["group"] for g in body["groups"]] == ["runtime"]  # only deployment A's alert
    assert body["groups"][0]["alerts"][0]["metric"] == "error_rate"


async def test_alerts_endpoint_filters_by_severity() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_alert(
        StoredAlert(deployment_id=dep, group="runtime", metric="error_rate", severity="critical")
    )
    store.add_alert(
        StoredAlert(deployment_id=dep, group="data_quality", metric="missing", severity="warning")
    )
    sessions = MonitoringSessionStore()
    session = sessions.create(dep, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store)

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/alerts",
            params={"severity": "critical"},
            headers=_cookie(session.session_id),
        )

    body = resp.json()
    assert [g["group"] for g in body["groups"]] == ["runtime"]  # warning group filtered out


async def test_traces_endpoint_paginates_and_is_session_scoped() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    for _ in range(5):
        store.add_event(_event(dep_a))
    store.add_event(_event(dep_b))  # must not appear under A's session

    sessions = MonitoringSessionStore()
    session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW)

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/traces",
            params={"limit": 2, "offset": 0, "deployment_id": str(dep_b)},  # dep_b ignored
            headers=_cookie(session_a.session_id),
        )

    body = resp.json()
    assert body["total"] == 5  # deployment A only, not B
    assert len(body["rows"]) == 2
    assert body["limit"] == 2 and body["offset"] == 0


async def test_traces_endpoint_rejects_invalid_pagination() -> None:
    dep = uuid.uuid4()
    sessions = MonitoringSessionStore()
    session = sessions.create(dep, MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=sessions, data_store=InMemoryMonitoringStore())

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/traces",
            params={"limit": 0},  # below the ge=1 bound
            headers=_cookie(session.session_id),
        )

    assert resp.status_code == 422
