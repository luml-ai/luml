import uuid

import pytest

from luml_satellite.monitoring import SESSION_COOKIE_NAME, MonitoringSessionStore
from luml_satellite.monitoring.storage.query_store import (
    DeploymentDescriptor,
    InferenceEvent,
    InMemoryMonitoringStore,
    ReferenceFeatureProfile,
    ReferenceProfile,
    StoredAlert,
    StoredMetricResult,
)
from luml_satellite.wire import MONITORING_READ_SCOPE, MonitoringIntrospection
from tests.support import FIXED_NOW, ago, build_app, client_for, introspect_returning

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


def _feature_drift_result(deployment_id: uuid.UUID, psi: float) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=deployment_id,
        group="feature_drift",
        window="24h",
        values={"features": {"income": {"psi": psi, "status": "critical"}}},
        severity="critical",
    )


class TestQueryAPI:
    async def test_missing_session_is_unauthorized(self) -> None:
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

    async def test_endpoints_derive_deployment_from_session(self) -> None:
        dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
        store = InMemoryMonitoringStore()
        for _ in range(3):
            store.add_event(_event(dep_a))
        for _ in range(7):
            store.add_event(_event(dep_b))

        sessions = MonitoringSessionStore()
        session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
        session_b = sessions.create(dep_b, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )

        async with client_for(app) as client:
            resp_a = await client.get(
                "/monitoring/api/runtime", headers=_cookie(session_a.session_id)
            )
            resp_b = await client.get(
                "/monitoring/api/runtime", headers=_cookie(session_b.session_id)
            )

        assert resp_a.json()["request_count"] == 3
        assert resp_b.json()["request_count"] == 7

    async def test_client_supplied_deployment_id_cannot_read_other_deployment(self) -> None:
        dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
        store = InMemoryMonitoringStore()
        for _ in range(3):
            store.add_event(_event(dep_a))
        for _ in range(7):
            store.add_event(_event(dep_b))

        sessions = MonitoringSessionStore()
        session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )

        async with client_for(app) as client:
            resp = await client.get(
                "/monitoring/api/runtime",
                params={"deployment_id": str(dep_b)},  # attempt to read B from A's session
                headers=_cookie(session_a.session_id),
            )

        assert resp.json()["request_count"] == 3  # still deployment A

    async def test_store_unavailable_returns_unavailable_state_not_500(self) -> None:
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

    async def test_feature_drift_endpoint_scoped_to_session(self) -> None:
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

    async def test_reference_profile_endpoint_scoped_to_session(self) -> None:
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

    async def test_invalid_window_is_rejected(self) -> None:
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

    @pytest.mark.parametrize("model_kind", ["tabular", "llm", "unknown"])
    async def test_header_carries_the_model_kind(self, model_kind: str) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_deployment(
            DeploymentDescriptor(deployment_id=dep, name="model", model_kind=model_kind)
        )

        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )

        async with client_for(app) as client:
            resp = await client.get("/monitoring/api/header", headers=_cookie(session.session_id))

        assert resp.json()["model_kind"] == model_kind

    async def test_custom_range_bounds_the_events_it_counts(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for seconds_back in (100, 200, 5000):  # two inside the range below, one before it
            event = _event(dep)
            store.add_event(
                InferenceEvent(
                    event_id=event.event_id,
                    deployment_id=dep,
                    ts=ago(seconds_back),
                    status="success",
                    status_code=200,
                    latency_ms=12.0,
                )
            )

        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )

        async with client_for(app) as client:
            resp = await client.get(
                "/monitoring/api/runtime",
                params={"start": ago(300).isoformat(), "end": ago(0).isoformat()},
                headers=_cookie(session.session_id),
            )

        assert resp.status_code == 200
        assert resp.json()["request_count"] == 2

    async def test_custom_range_validation(self) -> None:
        dep = uuid.uuid4()
        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(_INACTIVE, session_store=sessions, data_store=InMemoryMonitoringStore())
        headers = _cookie(session.session_id)

        async with client_for(app) as client:
            lonely = await client.get(
                "/monitoring/api/runtime", params={"start": ago(300).isoformat()}, headers=headers
            )
            backwards = await client.get(
                "/monitoring/api/runtime",
                params={"start": ago(0).isoformat(), "end": ago(300).isoformat()},
                headers=headers,
            )
            too_wide = await client.get(
                "/monitoring/api/runtime",
                params={"start": ago(40 * 24 * 3600).isoformat(), "end": ago(0).isoformat()},
                headers=headers,
            )

        assert lonely.status_code == 422
        assert backwards.status_code == 422
        assert too_wide.status_code == 422

    async def test_custom_compare_returns_baseline_rollup_and_overlay(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for seconds_back in (100, 200):  # current window
            e = _event(dep)
            store.add_event(
                InferenceEvent(
                    event_id=e.event_id,
                    deployment_id=dep,
                    ts=ago(seconds_back),
                    status="success",
                    status_code=200,
                    latency_ms=12.0,
                )
            )
        for seconds_back in (1000, 1100, 1200):  # the chosen comparison period
            e = _event(dep)
            store.add_event(
                InferenceEvent(
                    event_id=e.event_id,
                    deployment_id=dep,
                    ts=ago(seconds_back),
                    status="success",
                    status_code=200,
                    latency_ms=30.0,
                )
            )

        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )

        async with client_for(app) as client:
            resp = await client.get(
                "/monitoring/api/runtime",
                params={
                    "start": ago(300).isoformat(),
                    "end": ago(0).isoformat(),
                    "compare": "custom",
                    "compare_start": ago(1300).isoformat(),
                    "compare_end": ago(1000).isoformat(),
                },
                headers=_cookie(session.session_id),
            )

        body = resp.json()
        assert resp.status_code == 200
        assert body["request_count"] == 2
        # the comparison period's own rollup rides along for the card deltas
        assert body["baseline"]["request_count"] == 3
        # overlay: every series carries baseline points on the current window's axis
        requests = next(one for one in body["series"] if one["key"] == "requests")
        assert requests["baseline"] is not None
        assert len(requests["baseline"]) == len(requests["points"])
        assert requests["points"][0]["t"] == requests["baseline"][0]["t"]

    async def test_custom_compare_adds_deltas_to_drift_and_data_quality(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        # comparison period first: add_result keeps the last write as "the" snapshot,
        # so the current window must land last. Two windows averaging PSI 0.3, missing 5%.
        for seconds_back, psi, miss in ((2000, 0.2, 0.04), (2200, 0.4, 0.06)):
            store.add_result(
                StoredMetricResult(
                    deployment_id=dep,
                    group="feature_drift",
                    window="24h",
                    values={"features": {"income": {"psi": psi}}},
                    severity="ok",
                    computed_at=ago(seconds_back),
                )
            )
            store.add_result(
                StoredMetricResult(
                    deployment_id=dep,
                    group="data_quality",
                    window="24h",
                    values={"features": {"income": {"missing_rate": miss}}},
                    severity="ok",
                    computed_at=ago(seconds_back),
                )
            )
        # the current snapshot: PSI 0.9, missing 20%
        store.add_result(
            StoredMetricResult(
                deployment_id=dep,
                group="feature_drift",
                window="24h",
                values={"features": {"income": {"psi": 0.9, "status": "critical"}}},
                severity="critical",
                computed_at=ago(60),
            )
        )
        store.add_result(
            StoredMetricResult(
                deployment_id=dep,
                group="data_quality",
                window="24h",
                values={
                    "features": {
                        "income": {
                            "kind": "numeric",
                            "missing_rate": 0.2,
                            "status": "warning",
                        }
                    }
                },
                severity="warning",
                computed_at=ago(60),
            )
        )

        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )
        params = {
            "compare": "custom",
            "compare_start": ago(2400).isoformat(),
            "compare_end": ago(1800).isoformat(),
        }

        async with client_for(app) as client:
            drift = await client.get(
                "/monitoring/api/feature-drift", params=params, headers=_cookie(session.session_id)
            )
            quality = await client.get(
                "/monitoring/api/data-quality", params=params, headers=_cookie(session.session_id)
            )

        row = drift.json()["features"][0]
        assert row["baseline_psi"] == pytest.approx(0.3)
        assert row["psi_delta"] == pytest.approx(0.6)
        dq = quality.json()["features"][0]
        assert dq["missing_delta"] == pytest.approx(0.15)

    async def test_compare_custom_without_bounds_is_rejected(self) -> None:
        dep = uuid.uuid4()
        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(_INACTIVE, session_store=sessions, data_store=InMemoryMonitoringStore())

        async with client_for(app) as client:
            resp = await client.get(
                "/monitoring/api/runtime",
                params={"compare": "custom"},
                headers=_cookie(session.session_id),
            )

        assert resp.status_code == 422

    async def test_alerts_endpoint_is_read_only(self) -> None:
        dep = uuid.uuid4()
        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(_INACTIVE, session_store=sessions, data_store=InMemoryMonitoringStore())

        async with client_for(app) as client:
            get = await client.get("/monitoring/api/alerts", headers=_cookie(session.session_id))
            post = await client.post("/monitoring/api/alerts", headers=_cookie(session.session_id))

        assert get.status_code == 200
        assert post.status_code == 405  # no acknowledge/resolve — read-only in this slice

    async def test_alerts_endpoint_grouped_and_scoped_to_session(self) -> None:
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

    async def test_alerts_endpoint_filters_by_severity(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_alert(
            StoredAlert(
                deployment_id=dep, group="runtime", metric="error_rate", severity="critical"
            )
        )
        store.add_alert(
            StoredAlert(
                deployment_id=dep, group="data_quality", metric="missing", severity="warning"
            )
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

    async def test_traces_endpoint_paginates_and_is_session_scoped(self) -> None:
        dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
        store = InMemoryMonitoringStore()
        for _ in range(5):
            store.add_event(_event(dep_a))
        store.add_event(_event(dep_b))  # must not appear under A's session

        sessions = MonitoringSessionStore()
        session_a = sessions.create(dep_a, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )

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

    async def test_traces_sort_by_latency_and_status(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for latency, code in ((10.0, 200), (300.0, 500), (40.0, 200)):
            e = _event(dep)
            store.add_event(
                InferenceEvent(
                    event_id=e.event_id,
                    deployment_id=dep,
                    ts=ago(100 + latency),
                    status="success" if code == 200 else "error",
                    status_code=code,
                    latency_ms=latency,
                )
            )

        sessions = MonitoringSessionStore()
        session = sessions.create(dep, MONITORING_READ_SCOPE)
        app = build_app(
            _INACTIVE, session_store=sessions, data_store=store, clock=lambda: FIXED_NOW
        )
        headers = _cookie(session.session_id)

        async with client_for(app) as client:
            slowest_first = await client.get(
                "/monitoring/api/traces",
                params={"sort": "latency", "order": "desc"},
                headers=headers,
            )
            errors_first = await client.get(
                "/monitoring/api/traces",
                params={"sort": "status", "order": "desc"},
                headers=headers,
            )
            bad = await client.get(
                "/monitoring/api/traces", params={"sort": "nope"}, headers=headers
            )

        assert [row["latency_ms"] for row in slowest_first.json()["rows"]] == [300.0, 40.0, 10.0]
        assert [row["status_code"] for row in errors_first.json()["rows"]][0] == 500
        assert bad.status_code == 422

    async def test_traces_endpoint_rejects_invalid_pagination(self) -> None:
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
