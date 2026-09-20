from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
import respx

from luml_satellite.monitoring.compute.health import MetricFailure
from luml_satellite.monitoring.dashboard.schemas import ProfileStatus
from luml_satellite.monitoring.storage.greptime_query import GreptimeQueryStore
from luml_satellite.monitoring.storage.query_store import MonitoringStoreUnavailable

_URL = "http://gt:4000/v1/sql"
_DEP = UUID("019f46e3-3aa1-7672-96a9-8c6d98ab25cd")


def _store() -> GreptimeQueryStore:
    return GreptimeQueryStore(host="gt", port=4000)


def _records(columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {
        "code": 0,
        "output": [
            {
                "records": {
                    "schema": {"column_schemas": [{"name": c} for c in columns]},
                    "rows": rows,
                }
            }
        ],
    }


_PLATFORM_RECORD = {
    "name": "fraud scoring",
    "status": "active",
    "task_type": "classification",
    "model_name": "lisa_router",
    "satellite": "eu-west",
    "inference_url": "/deployments/dep-1",
}


_ARTIFACT_PROFILE = {
    "profile_status": "ready",
    "task_type": "regression",
    "n_reference_samples": 4000,
    "feature_summaries": {
        "numerical_features": {
            "temperature": {
                "mean": 0.42,
                "std": 0.09,
                "min": 0.1,
                "max": 0.8,
                "count": 4000,
                "missing": 0,
                "quantiles": {"q05": 0.28, "q50": 0.42, "q95": 0.57},
                "bin_edges": [0.1, 0.35, 0.6, 0.8],
                "probabilities": [0.2, 0.5, 0.3],
            }
        },
        "categorical_features": {
            "language": {
                "categories": ["de", "en", "tr"],
                "probabilities": {"en": 0.2, "de": 0.7},
                "count": 4000,
                "missing": 0,
                "n_unique": 3,
            }
        },
    },
}


_ALERT_COLUMNS = [
    "deployment_id",
    "metric",
    "current_value",
    "threshold",
    "severity",
    "state",
    "first_seen",
    "last_seen",
]


def _alert_row(metric: str, state: str, minutes_ago: int, value: float) -> list[Any]:
    """One stored row: the worker carries ``first_seen`` forward and moves ``last_seen``."""
    base = datetime(2026, 7, 9, 20, 30, tzinfo=UTC).timestamp()
    first_seen = int((base - 10 * 60) * 1_000)
    last_seen = int((base - minutes_ago * 60) * 1_000)
    return [str(_DEP), metric, value, 0.25, "critical", state, first_seen, last_seen]


class TestGreptimeQuery:
    @respx.mock
    async def test_reads_latest_worker_heartbeat_per_shard(self) -> None:
        tick = datetime(2026, 7, 9, 20, 30, tzinfo=UTC)
        deployments = (
            '{"019f46e3-3aa1-7672-96a9-8c6d98ab25cd":'
            '{"failures":[{"at":"2026-07-09T20:30:00+00:00",'
            '"error":"broken","metric":"runtime"}],'
            '"last_lag_seconds":2.0,"last_processed_at":null,'
            '"last_window_end":"2026-07-09T20:29:00+00:00",'
            '"windows_processed":4}}'
        )
        body = _records(
            [
                "shard_index",
                "shard_count",
                "tick_at",
                "window_seconds",
                "interval_seconds",
                "deployments",
            ],
            [[0, 2, int(tick.timestamp() * 1000), 300.0, 60.0, deployments]],
        )
        respx.post(_URL).mock(return_value=httpx.Response(200, json=body))

        store = _store()
        heartbeat = (await store.read_worker_heartbeats())[0]

        assert heartbeat.shard_index == 0
        assert heartbeat.shard_count == 2
        assert heartbeat.tick_at == tick
        assert heartbeat.deployments[str(_DEP)].windows_processed == 4
        assert heartbeat.deployments[str(_DEP)].failures == (
            MetricFailure("runtime", "broken", tick),
        )
        await store.aclose()

    @respx.mock
    async def test_fetch_events_parses_span_attributes(self) -> None:
        ns = int(datetime(2026, 7, 9, 20, 30, tzinfo=UTC).timestamp() * 1_000_000_000)
        attrs = {
            "inference.deployment_id": str(_DEP),
            "inference.event_id": "ev-1",
            "inference.status": "success",
            "inference.latency_ms": 12.5,
            "inference.trace_id": "t1",
            "inference.inputs": '{"x": 1}',
            "inference.output": '{"y": 2}',
        }
        body = _records(["timestamp", "span_attributes"], [[ns, attrs]])
        respx.post(_URL).mock(return_value=httpx.Response(200, json=body))

        store = _store()
        end = datetime.now(UTC)
        events = await store.fetch_events(_DEP, end - timedelta(days=5), end)

        assert len(events) == 1
        e = events[0]
        assert e.deployment_id == _DEP
        assert e.event_id == "ev-1"
        assert e.status == "success"
        assert e.status_code == 200
        assert e.latency_ms == 12.5
        assert e.trace_id == "t1"
        assert e.inputs == '{"x": 1}'
        await store.aclose()

    @respx.mock
    async def test_describe_deployment_uses_max_timestamp(self) -> None:
        ns = int(datetime(2026, 7, 9, 20, 30, tzinfo=UTC).timestamp() * 1_000_000_000)
        body = _records(["max(timestamp)"], [[ns]])
        respx.post(_URL).mock(return_value=httpx.Response(200, json=body))

        store = _store()
        desc = await store.describe_deployment(_DEP)

        assert desc is not None
        assert desc.deployment_id == _DEP
        assert desc.model_kind == "unknown"
        assert desc.last_prediction_at == datetime(2026, 7, 9, 20, 30, tzinfo=UTC)
        await store.aclose()

    @respx.mock
    async def test_describe_deployment_none_when_nothing_is_known(self) -> None:
        body = _records(["max(timestamp)"], [[None]])
        respx.post(_URL).mock(return_value=httpx.Response(200, json=body))
        store = _store()
        assert await store.describe_deployment(_DEP) is None
        await store.aclose()

    @respx.mock
    async def test_describe_deployment_carries_the_platform_identity(self) -> None:
        ns = int(datetime(2026, 7, 9, 20, 30, tzinfo=UTC).timestamp() * 1_000_000_000)
        window_end_ms = int(datetime(2026, 7, 9, 20, 25, tzinfo=UTC).timestamp() * 1_000)
        respx.post(_URL).mock(
            side_effect=[
                httpx.Response(200, json=_records(["max(timestamp)"], [[ns]])),
                httpx.Response(200, json=_records(["max(window_end)"], [[window_end_ms]])),
            ]
        )
        store = GreptimeQueryStore(
            host="gt", port=4000, deployment_source=lambda _: _PLATFORM_RECORD
        )

        desc = await store.describe_deployment(_DEP)

        assert desc is not None
        assert (desc.name, desc.status, desc.task_type) == (
            "fraud scoring",
            "active",
            "classification",
        )
        assert (desc.model_name, desc.satellite) == ("lisa_router", "eu-west")
        assert desc.inference_url == "/deployments/dep-1"
        assert desc.last_prediction_at == datetime(2026, 7, 9, 20, 30, tzinfo=UTC)
        # window boundaries are millisecond columns, not nanosecond ones
        assert desc.last_monitored_at == datetime(2026, 7, 9, 20, 25, tzinfo=UTC)
        await store.aclose()

    @respx.mock
    async def test_deployment_without_telemetry_still_has_a_header(self) -> None:
        respx.post(_URL).mock(
            side_effect=[
                httpx.Response(200, json=_records(["max(timestamp)"], [[None]])),
                httpx.Response(200, json=_records(["max(window_end)"], [[None]])),
            ]
        )
        store = GreptimeQueryStore(
            host="gt", port=4000, deployment_source=lambda _: _PLATFORM_RECORD
        )

        desc = await store.describe_deployment(_DEP)

        assert desc is not None
        assert desc.name == "fraud scoring"
        assert desc.last_prediction_at is None
        await store.aclose()

    @respx.mock
    async def test_missing_table_degrades_gracefully(self) -> None:
        # GreptimeDB returns HTTP 400 + non-zero code when a materialized table is absent.
        respx.post(_URL).mock(
            return_value=httpx.Response(
                400, json={"code": 4001, "error": "Table not found: public.monitoring_results"}
            )
        )
        store = _store()
        assert await store.fetch_result(_DEP, "feature_drift", "24h") is None
        assert await store.fetch_alerts(_DEP) == []
        await store.aclose()

    @respx.mock
    async def test_connection_error_is_store_unavailable(self) -> None:
        respx.post(_URL).mock(side_effect=httpx.ConnectError("refused"))
        store = _store()
        with pytest.raises(MonitoringStoreUnavailable):
            await store.fetch_events(_DEP, datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))
        await store.aclose()

    async def test_reference_profile_comes_from_the_deployment_artifact(self) -> None:
        """The baseline is not in GreptimeDB — it ships in the artifact and the Agent holds it
        per deployment, so the tab is served from that lookup."""
        store = GreptimeQueryStore(host="gt", port=4000, profile_source=lambda _: _ARTIFACT_PROFILE)

        profile = await store.fetch_profile(_DEP)

        assert profile is not None
        assert await store.profile_status(_DEP) == "ready"
        assert profile.baseline_label == "regression · 4000 reference samples"
        assert sorted(profile.features) == ["language", "temperature"]

        numeric = profile.features["temperature"]
        assert numeric.kind == "numeric"
        assert numeric.bin_edges == [0.1, 0.35, 0.6, 0.8]
        assert numeric.histogram == [0.2, 0.5, 0.3]
        assert numeric.summary["mean"] == 0.42
        assert numeric.summary["q95"] == 0.57

        categorical = profile.features["language"]
        assert categorical.kind == "categorical"
        assert categorical.categories == ["de", "en", "tr"]
        # probabilities are keyed by category in the artifact; unlisted labels read as zero
        assert categorical.category_probabilities == [0.7, 0.2, 0.0]

    async def test_no_profile_source_keeps_the_tab_empty(self) -> None:
        store = _store()

        assert await store.fetch_profile(_DEP) is None
        assert await store.profile_status(_DEP) is ProfileStatus.ABSENT

    async def test_placeholder_profile_is_reported_as_such(self) -> None:
        raw = {**_ARTIFACT_PROFILE, "profile_status": "placeholder"}
        store = GreptimeQueryStore(host="gt", port=4000, profile_source=lambda _: raw)

        assert await store.profile_status(_DEP) == "placeholder"

    async def test_profile_without_summaries_is_not_shown(self) -> None:
        raw = {"profile_status": "ready", "feature_summaries": {}}
        store = GreptimeQueryStore(host="gt", port=4000, profile_source=lambda _: raw)

        assert await store.fetch_profile(_DEP) is None
        assert await store.profile_status(_DEP) == "placeholder"

    async def test_failing_profile_lookup_does_not_break_the_dashboard(self) -> None:
        def explode(_: UUID) -> dict[str, Any]:
            raise RuntimeError("deployment state unavailable")

        store = GreptimeQueryStore(host="gt", port=4000, profile_source=explode)

        assert await store.fetch_profile(_DEP) is None
        assert await store.profile_status(_DEP) is ProfileStatus.ABSENT

    async def test_deployment_profile_status_source_preserves_unsupported(self) -> None:
        store = GreptimeQueryStore(
            host="gt",
            port=4000,
            profile_status_source=lambda _: ProfileStatus.UNSUPPORTED,
        )

        assert await store.fetch_profile(_DEP) is None
        assert await store.profile_status(_DEP) is ProfileStatus.UNSUPPORTED

    @respx.mock
    async def test_alert_history_collapses_to_the_current_state(self) -> None:
        """The worker re-saves an alert on every window it still fires in, so the table holds
        its whole history — counting rows reported three times as many alerts as there were."""
        rows = [  # newest first, as the query orders them
            _alert_row("feature_drift:income", "open", 0, 0.42),
            _alert_row("feature_drift:income", "open", 5, 0.38),
            _alert_row("feature_drift:income", "open", 10, 0.31),
        ]
        respx.post(_URL).mock(return_value=httpx.Response(200, json=_records(_ALERT_COLUMNS, rows)))
        store = _store()

        alerts = await store.fetch_alerts(_DEP)

        assert len(alerts) == 1
        assert alerts[0].metric == "feature_drift:income"
        assert alerts[0].current_value == 0.42  # the newest reading, not the first
        # the alert has been firing since its oldest window
        assert alerts[0].first_seen == datetime(2026, 7, 9, 20, 20, tzinfo=UTC)
        await store.aclose()

    @respx.mock
    async def test_resolved_alerts_are_not_active_any_more(self) -> None:
        rows = [
            _alert_row("data_quality:region.unseen_category", "resolved", 0, 0.0),
            _alert_row("data_quality:region.unseen_category", "open", 5, 0.03),
            _alert_row("runtime:error_rate", "open", 1, 0.09),
        ]
        respx.post(_URL).mock(return_value=httpx.Response(200, json=_records(_ALERT_COLUMNS, rows)))
        store = _store()

        alerts = await store.fetch_alerts(_DEP)

        # the resolved one is gone even though it still has open rows behind it
        assert [alert.metric for alert in alerts] == ["runtime:error_rate"]
        await store.aclose()


class TestBeforeTheFirstSpan:
    """A fresh GreptimeDB has no collector tables until the first inference lands.

    The dashboard is opened before that — right after a deploy — and its header used
    to answer 500 with "Table not found: inference_events". Nothing there yet is not
    an error; it is an empty dashboard with the deployment's identity in the header.
    """

    @staticmethod
    def _missing(table: str) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": 4001,
                "error": f"Failed to plan SQL: Table not found: greptime.public.{table}",
            },
        )

    @respx.mock
    async def test_the_header_has_the_platform_identity_and_no_timestamps(self) -> None:
        def answer(request: httpx.Request) -> httpx.Response:
            sql = request.content.decode()
            if "inference_events" in sql:
                return self._missing("inference_events")
            if "monitoring_results" in sql:
                return self._missing("monitoring_results")  # the worker has not ticked yet
            return httpx.Response(200, json=_records([], []))

        respx.post(_URL).mock(side_effect=answer)
        store = GreptimeQueryStore(
            host="gt",
            port=4000,
            deployment_source=lambda _id: {
                "name": "iris",
                "status": "active",
                "model_kind": "tabular",
            },
        )

        descriptor = await store.describe_deployment(UUID("01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"))

        assert descriptor is not None
        assert descriptor.name == "iris" and descriptor.status == "active"
        assert descriptor.last_prediction_at is None
        assert descriptor.last_monitored_at is None
        await store.aclose()

    @respx.mock
    async def test_a_window_before_the_table_exists_is_empty(self) -> None:
        respx.post(_URL).mock(return_value=self._missing("inference_events"))
        store = _store()

        events = await store.fetch_events(
            UUID("01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"),
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )

        assert events == []
        await store.aclose()

    @respx.mock
    async def test_any_other_query_error_still_fails_the_read(self) -> None:
        """Only a missing table is a phase; a rejected statement is a bug to surface."""
        from luml_satellite.monitoring.storage.greptime_query import _QueryError

        respx.post(_URL).mock(
            return_value=httpx.Response(
                400, json={"code": 3000, "error": "Failed to plan SQL: syntax"}
            )
        )
        store = _store()

        with pytest.raises(_QueryError):
            await store.fetch_events(
                UUID("01a014fd-1ebc-7021-b0f5-fe92f2fdaf9b"),
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            )
        await store.aclose()
