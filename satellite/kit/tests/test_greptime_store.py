import logging
import urllib.parse
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from luml_satellite.monitoring.compute.models import (
    Alert,
    AlertState,
    MetricResult,
    Severity,
    TimeWindow,
)
from luml_satellite.monitoring.dashboard.schemas import ProfileStatus
from luml_satellite.monitoring.storage.greptime import GreptimeMonitoringStore, _to_ns

WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    end=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
)


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


def _affected() -> dict[str, Any]:
    return {"code": 0, "output": [{"affectedrows": 1}]}


class Recorder:
    """Captures the SQL statements sent to GreptimeDB and returns canned responses."""

    def __init__(self, response_for: dict[str, dict[str, Any]] | None = None) -> None:
        self.statements: list[str] = []
        self._response_for = response_for or {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = urllib.parse.parse_qs(request.content.decode())
        sql = body["sql"][0]
        self.statements.append(sql)
        for keyword, payload in self._response_for.items():
            if keyword in sql:
                return httpx.Response(200, json=payload)
        return httpx.Response(200, json=_affected())

    def store(self) -> GreptimeMonitoringStore:
        client = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return GreptimeMonitoringStore(client=client, database="public")


class TestGreptimeStore:
    async def test_read_events_parses_records(self) -> None:
        ns = int(datetime(2026, 1, 1, 0, 1, tzinfo=UTC).timestamp() * 1_000_000_000)
        span_attributes = {
            "inference.event_id": "evt-1",
            "inference.deployment_id": "dep-1",
            "inference.status": "success",
            "inference.latency_ms": 12.5,
            # A request carries a batch of observations per feature; read_events flattens them.
            "inference.inputs": '{"inputs": {"age": [[30], [31]]}, "dynamic_attributes": {}}',
            "inference.output": "51000",
        }
        rows = [[ns, span_attributes]]
        recorder = Recorder({"SELECT": _records(["timestamp", "span_attributes"], rows)})
        store = recorder.store()

        events = await store.read_events("dep-1", WINDOW)

        assert len(events) == 1
        event = events[0]
        assert event.event_id == "evt-1"
        assert event.deployment_id == "dep-1"
        assert event.status_code == 200
        assert event.latency_ms == 12.5
        assert event.inputs == {"age": [30, 31]}
        assert event.output == 51000
        assert isinstance(event.timestamp, datetime)

        sql = recorder.statements[0]
        assert "FROM inference_events" in sql
        assert "json_get_string(span_attributes" in sql
        assert "'dep-1'" in sql
        assert str(_to_ns(WINDOW.start)) in sql

    async def test_read_events_empty_result(self) -> None:
        recorder = Recorder({"SELECT": _records(["event_id"], [])})
        store = recorder.store()

        assert await store.read_events("dep-1", WINDOW) == []

    async def test_write_result_creates_tables_then_inserts(self) -> None:
        recorder = Recorder()
        store = recorder.store()
        result = MetricResult(
            deployment_id="dep-1",
            metric="runtime",
            window_start=WINDOW.start,
            window_end=WINDOW.end,
            values={"error_rate": 0.1, "request_count": 10},
            severity=Severity.CRITICAL,
            profile_status=ProfileStatus.ABSENT,
        )

        await store.write_result(result)

        creates = [s for s in recorder.statements if s.strip().startswith("CREATE TABLE")]
        assert any("monitoring_results" in s for s in creates)
        assert any("monitoring_alerts" in s for s in creates)

        insert = next(
            s for s in recorder.statements if s.startswith("INSERT INTO monitoring_results")
        )
        assert "'runtime'" in insert
        assert "'critical'" in insert
        assert '"error_rate": 0.1' in insert

    async def test_tables_created_only_once(self) -> None:
        recorder = Recorder()
        store = recorder.store()
        result = MetricResult(
            deployment_id="dep-1",
            metric="runtime",
            window_start=WINDOW.start,
            window_end=WINDOW.end,
            values={},
            severity=Severity.NORMAL,
            profile_status=ProfileStatus.ABSENT,
        )

        await store.write_result(result)
        await store.write_result(result)

        creates = [s for s in recorder.statements if s.strip().startswith("CREATE TABLE")]
        # results, alerts and the worker's own failure history
        assert len(creates) == 3

    async def test_save_alert_inserts_row(self) -> None:
        recorder = Recorder()
        store = recorder.store()
        alert = Alert(
            deployment_id="dep-1",
            metric="runtime:error_rate",
            current_value=0.1,
            threshold=0.05,
            severity=Severity.CRITICAL,
            state=AlertState.OPEN,
            first_seen=WINDOW.end,
            last_seen=WINDOW.end,
        )

        await store.save_alert(alert)

        insert = next(
            s for s in recorder.statements if s.startswith("INSERT INTO monitoring_alerts")
        )
        assert "'runtime:error_rate'" in insert
        assert "'open'" in insert
        assert "0.1" in insert

    async def test_active_alerts_keeps_latest_and_drops_resolved(self) -> None:
        columns = [
            "deployment_id",
            "metric",
            "current_value",
            "threshold",
            "severity",
            "state",
            "first_seen",
            "last_seen",
        ]
        t0 = "2026-01-01T00:00:00+00:00"
        t5 = "2026-01-01T00:05:00+00:00"
        t10 = "2026-01-01T00:10:00+00:00"
        rows = [
            ["dep-1", "runtime:error_rate", 0.2, 0.05, "critical", "open", t0, t10],
            ["dep-1", "runtime:error_rate", 0.1, 0.05, "warning", "open", t0, t5],
            ["dep-1", "runtime:latency_p95", 1200.0, 1000.0, "warning", "resolved", t0, t5],
        ]
        recorder = Recorder({"SELECT": _records(columns, rows)})
        store = recorder.store()

        alerts = await store.active_alerts("dep-1")

        assert len(alerts) == 1
        assert alerts[0].metric == "runtime:error_rate"
        assert alerts[0].current_value == 0.2
        assert alerts[0].state == AlertState.OPEN

    async def test_active_alerts_bootstraps_missing_tables(self) -> None:
        """On a fresh database the alerts table does not exist yet. active_alerts must
        create it before reading rather than erroring, otherwise the very first tick
        (which reads alerts before writing anything) would be permanently blocked and
        the tables would never be created.
        """
        alerts_table_created = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal alerts_table_created
            sql = urllib.parse.parse_qs(request.content.decode())["sql"][0]
            if sql.strip().startswith("CREATE TABLE"):
                if "monitoring_alerts" in sql:
                    alerts_table_created = True
                return httpx.Response(200, json=_affected())
            if "SELECT" in sql and "monitoring_alerts" in sql and not alerts_table_created:
                return httpx.Response(200, json={"code": 4001, "error": "table not found"})
            return httpx.Response(200, json=_records(["metric"], []))

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        store = GreptimeMonitoringStore(client=client, database="public")

        alerts = await store.active_alerts("dep-1")  # must not raise on a fresh database

        assert alerts == []
        assert alerts_table_created

    async def test_read_events_before_the_collector_created_the_table_is_empty(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A fresh database has no ``inference_events`` until the first span lands.

        Every worker tick used to log a WARNING per monitored deployment and count a
        storage failure against it. There simply are no events yet.
        """
        recorder = Recorder()
        missing = {"code": 4001, "error": "Table not found: greptime.public.inference_events"}

        def handler(request: httpx.Request) -> httpx.Response:
            sql = urllib.parse.parse_qs(request.content.decode())["sql"][0]
            recorder.statements.append(sql)
            if "FROM inference_events" in sql:
                return httpx.Response(400, json=missing)
            return httpx.Response(200, json=_affected())

        store = GreptimeMonitoringStore(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), database="public"
        )

        with caplog.at_level(logging.DEBUG, logger="satellite"):
            first = await store.read_events("dep-1", WINDOW)
            second = await store.read_events("dep-2", WINDOW)

        assert first == [] and second == []
        assert all(r.levelno < logging.WARNING for r in caplog.records)
        notices = [r for r in caplog.records if "does not exist yet" in r.getMessage()]
        assert len(notices) == 1  # said once, not once per deployment per tick

    async def test_other_400s_still_fail_the_read(self) -> None:
        """Only a missing table is a phase; a malformed query is a bug and must surface."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"code": 3000, "error": "Failed to plan SQL: syntax"})

        store = GreptimeMonitoringStore(
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), database="public"
        )

        with pytest.raises(httpx.HTTPStatusError):
            await store.read_events("dep-1", WINDOW)
