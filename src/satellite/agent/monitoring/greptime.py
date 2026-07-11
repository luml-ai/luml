import json
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx

from agent.monitoring.models import (
    Alert,
    AlertState,
    InferenceEvent,
    MetricResult,
    Severity,
    TimeWindow,
)

logger = logging.getLogger("satellite")

# Table + time-index conventions from part 1's collection layer. Kept as constants
# so a differing convention is a one-line change rather than a schema hunt.
INFERENCE_EVENTS_TABLE = "inference_events"
INFERENCE_EVENTS_TIME_INDEX = "ts"
RESULTS_TABLE = "monitoring_results"
ALERTS_TABLE = "monitoring_alerts"

_CREATE_RESULTS = f"""
CREATE TABLE IF NOT EXISTS {RESULTS_TABLE} (
    deployment_id STRING,
    metric STRING,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    metric_values STRING,
    severity STRING,
    profile_status STRING,
    TIME INDEX (window_end),
    PRIMARY KEY (deployment_id, metric, window_start)
)
"""

_CREATE_ALERTS = f"""
CREATE TABLE IF NOT EXISTS {ALERTS_TABLE} (
    deployment_id STRING,
    metric STRING,
    current_value DOUBLE,
    threshold DOUBLE,
    severity STRING,
    state STRING,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    TIME INDEX (last_seen),
    PRIMARY KEY (deployment_id, metric)
)
"""


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_ts(value: datetime) -> str:
    return _sql_str(value.isoformat())


class GreptimeMonitoringStore:
    """Backs the worker with GreptimeDB over its SQL/HTTP interface.

    Reads the ``inference_events`` trace table and writes ``monitoring_results`` and
    ``monitoring_alerts``. Table creation is lazy and best-effort so a database outage
    only skips writes; the worker retries the window next interval.
    """

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 4000,
        database: str = "public",
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = f"http://{host}:{port}/v1/sql"
        self._database = database
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None
        self._tables_ready = False

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _execute(self, sql: str) -> dict[str, Any]:
        response = await self._get_client().post(
            self._url, params={"db": self._database}, data={"sql": sql}
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"GreptimeDB error: {payload.get('error', payload)}")
        return payload

    @staticmethod
    def _records(payload: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
        for item in payload.get("output", []):
            records = item.get("records")
            if records:
                columns = [c["name"] for c in records["schema"]["column_schemas"]]
                return columns, records.get("rows", [])
        return [], []

    async def _ensure_tables(self) -> None:
        if self._tables_ready:
            return
        await self._execute(_CREATE_RESULTS)
        await self._execute(_CREATE_ALERTS)
        self._tables_ready = True

    async def read_events(self, deployment_id: str, window: TimeWindow) -> list[InferenceEvent]:
        ts = INFERENCE_EVENTS_TIME_INDEX
        sql = (
            f"SELECT event_id, deployment_id, status, status_code, latency_ms, "
            f"inputs, output, {ts} FROM {INFERENCE_EVENTS_TABLE} "
            f"WHERE deployment_id = {_sql_str(deployment_id)} "
            f"AND {ts} >= {_sql_ts(window.start)} AND {ts} < {_sql_ts(window.end)}"
        )
        columns, rows = self._records(await self._execute(sql))
        return [self._to_event(dict(zip(columns, row, strict=False))) for row in rows]

    def _to_event(self, row: dict[str, Any]) -> InferenceEvent:
        return InferenceEvent(
            event_id=str(row.get("event_id", "")),
            deployment_id=str(row.get("deployment_id", "")),
            status=str(row.get("status", "")),
            status_code=_coerce_int(row.get("status_code")),
            latency_ms=_coerce_float(row.get("latency_ms")),
            inputs=_parse_json(row.get("inputs")),
            output=_parse_json(row.get("output")),
            timestamp=_parse_timestamp(row.get(INFERENCE_EVENTS_TIME_INDEX)),
        )

    async def write_result(self, result: MetricResult) -> None:
        await self._ensure_tables()
        values = _sql_str(json.dumps(result.values))
        sql = (
            f"INSERT INTO {RESULTS_TABLE} "
            f"(deployment_id, metric, window_start, window_end, metric_values, "
            f"severity, profile_status) VALUES ("
            f"{_sql_str(result.deployment_id)}, {_sql_str(result.metric)}, "
            f"{_sql_ts(result.window_start)}, {_sql_ts(result.window_end)}, {values}, "
            f"{_sql_str(result.severity.value)}, {_sql_str(result.profile_status)})"
        )
        await self._execute(sql)

    async def save_alert(self, alert: Alert) -> None:
        await self._ensure_tables()
        sql = (
            f"INSERT INTO {ALERTS_TABLE} "
            f"(deployment_id, metric, current_value, threshold, severity, state, "
            f"first_seen, last_seen) VALUES ("
            f"{_sql_str(alert.deployment_id)}, {_sql_str(alert.metric)}, "
            f"{alert.current_value}, {alert.threshold}, {_sql_str(alert.severity.value)}, "
            f"{_sql_str(alert.state.value)}, {_sql_ts(alert.first_seen)}, "
            f"{_sql_ts(alert.last_seen)})"
        )
        await self._execute(sql)

    async def active_alerts(self, deployment_id: str) -> list[Alert]:
        await self._ensure_tables()
        sql = (
            f"SELECT deployment_id, metric, current_value, threshold, severity, state, "
            f"first_seen, last_seen FROM {ALERTS_TABLE} "
            f"WHERE deployment_id = {_sql_str(deployment_id)} ORDER BY last_seen DESC"
        )
        columns, rows = self._records(await self._execute(sql))
        latest: dict[str, Alert] = {}
        for row in rows:
            alert = self._to_alert(dict(zip(columns, row, strict=False)))
            latest.setdefault(alert.metric, alert)
        return [a for a in latest.values() if a.state != AlertState.RESOLVED]

    @staticmethod
    def _to_alert(row: dict[str, Any]) -> Alert:
        return Alert(
            deployment_id=str(row.get("deployment_id", "")),
            metric=str(row.get("metric", "")),
            current_value=_coerce_float(row.get("current_value")) or 0.0,
            threshold=_coerce_float(row.get("threshold")) or 0.0,
            severity=_coerce_enum(Severity, row.get("severity"), Severity.WARNING),
            state=_coerce_enum(AlertState, row.get("state"), AlertState.OPEN),
            first_seen=_parse_timestamp(row.get("first_seen")) or datetime.now(UTC),
            last_seen=_parse_timestamp(row.get("last_seen")) or datetime.now(UTC),
        )


def _coerce_enum[E: StrEnum](enum: type[E], value: Any, fallback: E) -> E:  # noqa: ANN401
    try:
        return enum(str(value))
    except ValueError:
        return fallback


def _coerce_int(value: Any) -> int | None:  # noqa: ANN401
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:  # noqa: ANN401
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_json(value: Any) -> Any:  # noqa: ANN401
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _parse_timestamp(value: Any) -> datetime | None:  # noqa: ANN401
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
