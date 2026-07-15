import uuid

from tests.support import build_app, client_for, introspect_returning

from agent.monitoring import SESSION_COOKIE_NAME, MonitoringSessionStore
from agent.schemas.monitoring import MONITORING_READ_SCOPE, MonitoringIntrospection

_INACTIVE = introspect_returning(MonitoringIntrospection(active=False))


def _cookie(session_id: str) -> dict[str, str]:
    return {"cookie": f"{SESSION_COOKIE_NAME}={session_id}"}


async def test_sessions_derive_isolated_deployments() -> None:
    store = MonitoringSessionStore()
    session_a = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)
    session_b = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=store)

    async with client_for(app) as client:
        resp_a = await client.get("/monitoring/api/session", headers=_cookie(session_a.session_id))
        resp_b = await client.get("/monitoring/api/session", headers=_cookie(session_b.session_id))

    assert resp_a.json()["deployment_id"] == str(session_a.deployment_id)
    assert resp_b.json()["deployment_id"] == str(session_b.deployment_id)
    assert resp_a.json()["deployment_id"] != resp_b.json()["deployment_id"]


async def test_client_supplied_deployment_id_is_ignored() -> None:
    store = MonitoringSessionStore()
    session_a = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)
    other_deployment = uuid.uuid4()
    app = build_app(_INACTIVE, session_store=store)

    async with client_for(app) as client:
        resp = await client.get(
            "/monitoring/api/session",
            params={"deployment_id": str(other_deployment)},
            headers=_cookie(session_a.session_id),
        )

    assert resp.json()["deployment_id"] == str(session_a.deployment_id)


async def test_missing_session_cookie_is_unauthorized() -> None:
    app = build_app(_INACTIVE)

    async with client_for(app) as client:
        resp = await client.get("/monitoring/api/session")

    assert resp.status_code == 401


async def test_unknown_session_id_is_unauthorized() -> None:
    app = build_app(_INACTIVE)

    async with client_for(app) as client:
        resp = await client.get("/monitoring/api/session", headers=_cookie("bogus"))

    assert resp.status_code == 401


async def test_expired_session_is_unauthorized() -> None:
    now = [1000.0]
    store = MonitoringSessionStore(ttl_seconds=1800, clock=lambda: now[0])
    session_a = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)
    app = build_app(_INACTIVE, session_store=store)

    now[0] = 1000.0 + 1800.0 + 1.0
    async with client_for(app) as client:
        resp = await client.get("/monitoring/api/session", headers=_cookie(session_a.session_id))

    assert resp.status_code == 401
