import uuid

from agent.monitoring import MonitoringSessionStore
from agent.monitoring.session import MonitoringSession
from agent.schemas.monitoring import MONITORING_READ_SCOPE


def test_create_returns_deployment_scoped_session() -> None:
    store = MonitoringSessionStore()
    deployment_id = uuid.uuid4()

    session = store.create(deployment_id, MONITORING_READ_SCOPE)

    assert session.deployment_id == deployment_id
    assert session.scope == MONITORING_READ_SCOPE
    assert store.get(session.session_id) == session


def test_get_returns_none_for_unknown_id() -> None:
    store = MonitoringSessionStore()
    assert store.get("does-not-exist") is None


def test_get_returns_none_after_expiry() -> None:
    now = [0.0]
    store = MonitoringSessionStore(ttl_seconds=60, clock=lambda: now[0])
    session = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)

    now[0] = 59.0
    assert store.get(session.session_id) is not None

    now[0] = 60.0
    assert store.get(session.session_id) is None


def test_create_purges_expired_sessions() -> None:
    now = [0.0]
    store = MonitoringSessionStore(ttl_seconds=60, clock=lambda: now[0])
    stale = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)

    now[0] = 100.0
    fresh = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)

    assert store.get(fresh.session_id) is not None
    assert stale.session_id not in store._sessions


def test_is_expired_boundary() -> None:
    session = MonitoringSession("id", uuid.uuid4(), MONITORING_READ_SCOPE, expires_at=100.0)
    assert not session.is_expired(99.9)
    assert session.is_expired(100.0)
