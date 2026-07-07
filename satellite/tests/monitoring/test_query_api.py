import uuid

from tests.support import FIXED_NOW, ago, build_app, client_for, introspect_returning

from agent.monitoring import SESSION_COOKIE_NAME, MonitoringSessionStore
from agent.monitoring.query_store import InferenceEvent, InMemoryMonitoringStore
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

    async with client_for(app) as client:
        for path in ("/header", "/overview", "/runtime", "/data-quality"):
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
