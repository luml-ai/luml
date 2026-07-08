import urllib.parse
from datetime import UTC, datetime

import httpx

from agent.monitoring.greptime import GreptimeMonitoringStore
from agent.monitoring.models import Alert, AlertState, MetricResult, Severity, TimeWindow

WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    end=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
)


def _records(columns: list[str], rows: list[list]) -> dict:
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


def _affected() -> dict:
    return {"code": 0, "output": [{"affectedrows": 1}]}


class Recorder:
    """Captures the SQL statements sent to GreptimeDB and returns canned responses."""

    def __init__(self, response_for: dict | None = None) -> None:
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


async def test_read_events_parses_records() -> None:
    rows = [
        [
            "evt-1",
            "dep-1",
            "success",
            200,
            12.5,
            '{"age": 30}',
            "51000",
            1767225600000,
        ]
    ]
    columns = [
        "event_id",
        "deployment_id",
        "status",
        "status_code",
        "latency_ms",
        "inputs",
        "output",
        "ts",
    ]
    recorder = Recorder({"SELECT": _records(columns, rows)})
    store = recorder.store()

    events = await store.read_events("dep-1", WINDOW)

    assert len(events) == 1
    event = events[0]
    assert event.event_id == "evt-1"
    assert event.status_code == 200
    assert event.latency_ms == 12.5
    assert event.inputs == {"age": 30}
    assert event.output == 51000
    assert isinstance(event.timestamp, datetime)

    sql = recorder.statements[0]
    assert "FROM inference_events" in sql
    assert "deployment_id = 'dep-1'" in sql
    assert "2026-01-01T00:00:00+00:00" in sql


async def test_read_events_empty_result() -> None:
    recorder = Recorder({"SELECT": _records(["event_id"], [])})
    store = recorder.store()

    assert await store.read_events("dep-1", WINDOW) == []


async def test_write_result_creates_tables_then_inserts() -> None:
    recorder = Recorder()
    store = recorder.store()
    result = MetricResult(
        deployment_id="dep-1",
        metric="runtime",
        window_start=WINDOW.start,
        window_end=WINDOW.end,
        values={"error_rate": 0.1, "request_count": 10},
        severity=Severity.CRITICAL,
        profile_status="absent",
    )

    await store.write_result(result)

    creates = [s for s in recorder.statements if s.strip().startswith("CREATE TABLE")]
    assert any("monitoring_results" in s for s in creates)
    assert any("monitoring_alerts" in s for s in creates)

    insert = next(s for s in recorder.statements if s.startswith("INSERT INTO monitoring_results"))
    assert "'runtime'" in insert
    assert "'critical'" in insert
    assert '"error_rate": 0.1' in insert


async def test_tables_created_only_once() -> None:
    recorder = Recorder()
    store = recorder.store()
    result = MetricResult(
        deployment_id="dep-1",
        metric="runtime",
        window_start=WINDOW.start,
        window_end=WINDOW.end,
        values={},
        severity=Severity.NORMAL,
        profile_status="absent",
    )

    await store.write_result(result)
    await store.write_result(result)

    creates = [s for s in recorder.statements if s.strip().startswith("CREATE TABLE")]
    assert len(creates) == 2


async def test_save_alert_inserts_row() -> None:
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

    insert = next(s for s in recorder.statements if s.startswith("INSERT INTO monitoring_alerts"))
    assert "'runtime:error_rate'" in insert
    assert "'open'" in insert
    assert "0.1" in insert


async def test_active_alerts_keeps_latest_and_drops_resolved() -> None:
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


async def test_active_alerts_bootstraps_missing_tables() -> None:
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
