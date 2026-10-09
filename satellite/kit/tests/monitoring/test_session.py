import uuid

from luml_satellite.monitoring import MonitoringSessionStore
from luml_satellite.monitoring.dashboard.session import MonitoringSession
from luml_satellite.wire import MONITORING_READ_SCOPE


class TestSession:
    def test_create_returns_deployment_scoped_session(self) -> None:
        now = [0.0]
        store = MonitoringSessionStore(clock=lambda: now[0])
        deployment_id = uuid.uuid4()

        session = store.create(deployment_id, MONITORING_READ_SCOPE)

        assert session.deployment_id == deployment_id
        assert session.scope == MONITORING_READ_SCOPE
        assert store.get(session.session_id) == session

    def test_get_returns_none_for_unknown_id(self) -> None:
        store = MonitoringSessionStore()
        assert store.get("does-not-exist") is None

    def test_get_returns_none_after_expiry(self) -> None:
        now = [0.0]
        store = MonitoringSessionStore("secret", ttl_seconds=60, clock=lambda: now[0])
        session = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)

        # untouched for a full TTL: gone (touching would have slid the expiry)
        now[0] = 60.0
        assert store.get(session.session_id) is None

    def test_session_from_one_replica_is_accepted_by_another(self) -> None:
        now = [0.0]
        first = MonitoringSessionStore("shared-secret", ttl_seconds=60, clock=lambda: now[0])
        second = MonitoringSessionStore("shared-secret", ttl_seconds=60, clock=lambda: now[0])
        session = first.create(uuid.uuid4(), MONITORING_READ_SCOPE)

        assert second.get(session.session_id) == session

    def test_tampered_session_is_refused(self) -> None:
        store = MonitoringSessionStore("secret", clock=lambda: 0.0)
        session = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)
        replacement = "a" if session.session_id[-1] != "a" else "b"

        assert store.get(f"{session.session_id[:-1]}{replacement}") is None

    def test_is_expired_boundary(self) -> None:
        session = MonitoringSession(
            "id",
            uuid.uuid4(),
            MONITORING_READ_SCOPE,
            issued_at=0.0,
            expires_at=100.0,
            hard_deadline=200.0,
        )
        assert not session.is_expired(99.9)
        assert session.is_expired(100.0)

    def test_activity_slides_the_expiry(self) -> None:
        now = [0.0]
        store = MonitoringSessionStore("secret", ttl_seconds=60, clock=lambda: now[0])
        session = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)

        now[0] = 50.0
        renewed = store.get(session.session_id)
        assert renewed is not None
        now[0] = 100.0
        renewed = store.get(renewed.session_id)
        assert renewed is not None

        now[0] = 161.0
        assert store.get(renewed.session_id) is None

    def test_sliding_never_passes_the_hard_deadline(self) -> None:
        now = [0.0]
        store = MonitoringSessionStore(
            "secret", ttl_seconds=60, max_age_seconds=90, clock=lambda: now[0]
        )
        session = store.create(uuid.uuid4(), MONITORING_READ_SCOPE)

        now[0] = 50.0
        renewed = store.get(session.session_id)
        assert renewed is not None
        assert renewed.expires_at == 90.0  # capped, not 110

        now[0] = 90.0
        assert store.get(renewed.session_id) is None
