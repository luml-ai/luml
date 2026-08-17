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
    MetricTransition,
    Severity,
    TimeWindow,
)

logger = logging.getLogger("satellite")

# The collector writes inference events as OpenTelemetry spans: a nanosecond ``timestamp``
# time index plus a ``span_attributes`` JSON object carrying the ``inference.*`` payload.
INFERENCE_EVENTS_TABLE = "inference_events"
RESULTS_TABLE = "monitoring_results"
ALERTS_TABLE = "monitoring_alerts"
FAILURES_TABLE = "monitoring_worker_failures"

# span_attributes keys emitted by the Satellite inference instrumentation.
_ATTR_DEPLOYMENT = "inference.deployment_id"
_ATTR_EVENT_ID = "inference.event_id"
_ATTR_STATUS = "inference.status"
_ATTR_LATENCY = "inference.latency_ms"
_ATTR_INPUTS = "inference.inputs"
_ATTR_OUTPUT = "inference.output"
_ATTR_STATUS_CODE = "inference.status_code"

_CREATE_FAILURES = f"""
CREATE TABLE IF NOT EXISTS {FAILURES_TABLE} (
    deployment_id STRING,
    metric STRING,
    kind STRING,
    -- "error" and "at" are reserved words in GreptimeDB, hence the plainer names
    message STRING,
    window_end TIMESTAMP,
    happened_at TIMESTAMP,
    TIME INDEX (happened_at),
    PRIMARY KEY (deployment_id, metric, kind)
)
"""


def _with_ttl(sql: str, ttl: str) -> str:
    """Table options carrying the retention window, when one is configured."""
    return f"{sql.rstrip()} WITH (ttl = '{ttl}')" if ttl else sql


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


def _json_path(key: str) -> str:
    # Bracket path so a key containing dots (inference.deployment_id) is treated as one
    # literal key rather than a nested path.
    return _sql_str(f'["{key}"]')


def _to_ns(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _ms_to_dt(value: Any) -> datetime | None:  # noqa: ANN401
    """``window_end`` is a millisecond column, unlike the nanosecond trace timestamps."""
    try:
        return datetime.fromtimestamp(int(value) / 1_000, UTC)
    except (TypeError, ValueError):
        return None


def _ns_to_dt(value: Any) -> datetime | None:  # noqa: ANN401
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000_000, UTC)
    except (TypeError, ValueError):
        return None


def _flatten(value: Any) -> list[Any]:  # noqa: ANN401
    """Flatten a (possibly batched / column-vector) feature value into a scalar list."""
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return [value]


def _normalize_features(raw: Any) -> dict[str, list[Any]]:  # noqa: ANN401
    """Normalize the recorded input payload to ``{feature: [observation, ...]}``.

    The instrumentation records the whole request under ``{"inputs": {feature: [[v], ...]},
    "dynamic_attributes": {...}}``. Metrics reason per observation, so unwrap ``inputs`` and
    flatten each feature's batch (a request may carry many rows).
    """
    data = _parse_json(raw)
    if not isinstance(data, dict):
        return {}
    inner = data.get("inputs")
    if not isinstance(inner, dict):
        inner = data
    return {name: _flatten(values) for name, values in inner.items()}


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
        events_ttl: str = "",
        results_ttl: str = "",
        alerts_ttl: str = "",
    ) -> None:
        self._events_ttl = events_ttl
        self._results_ttl = results_ttl
        self._alerts_ttl = alerts_ttl
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
        """Create the monitoring tables and keep their retention in sync.

        Nothing here ever deleted a row: alerts append one row per window they keep firing
        in, and raw events hold the model's own inputs and outputs. The TTL is applied on
        every start — including to tables that already exist, and to the traces table the
        collector owns — so changing the setting is enough to change retention.
        """
        if self._tables_ready:
            return
        await self._execute(_with_ttl(_CREATE_RESULTS, self._results_ttl))
        await self._execute(_with_ttl(_CREATE_ALERTS, self._alerts_ttl))
        await self._execute(_with_ttl(_CREATE_FAILURES, self._alerts_ttl))
        await self._apply_ttl(RESULTS_TABLE, self._results_ttl)
        await self._apply_ttl(ALERTS_TABLE, self._alerts_ttl)
        await self._apply_ttl(FAILURES_TABLE, self._alerts_ttl)
        await self._apply_ttl(INFERENCE_EVENTS_TABLE, self._events_ttl)
        self._tables_ready = True

    async def _apply_ttl(self, table: str, ttl: str) -> None:
        """Retention for a table that already exists; missing tables are simply skipped."""
        if not ttl:
            return
        try:
            await self._execute(f"ALTER TABLE {table} SET 'ttl' = '{ttl}'")
        except Exception as error:  # noqa: BLE001 — retention must not block the worker
            logger.warning("Could not set retention on %s: %s", table, error)

    async def read_events(self, deployment_id: str, window: TimeWindow) -> list[InferenceEvent]:
        sql = (
            f"SELECT timestamp, span_attributes FROM {INFERENCE_EVENTS_TABLE} "
            f"WHERE json_get_string(span_attributes, {_json_path(_ATTR_DEPLOYMENT)}) "
            f"= {_sql_str(deployment_id)} "
            f"AND timestamp >= {_to_ns(window.start)} AND timestamp < {_to_ns(window.end)}"
        )
        columns, rows = self._records(await self._execute(sql))
        return [
            self._to_event(deployment_id, dict(zip(columns, row, strict=False))) for row in rows
        ]

    def _to_event(self, deployment_id: str, row: dict[str, Any]) -> InferenceEvent:
        attrs = row.get("span_attributes")
        attrs = attrs if isinstance(attrs, dict) else (_parse_json(attrs) or {})
        status = str(attrs.get(_ATTR_STATUS, "") or "")
        # The instrumentation records the upstream's own code (504 for a gateway timeout,
        # 429 for a quota); collapsing every failure to 500 here hid what actually went
        # wrong, and no timeout could ever be recognized downstream.
        status_code = _coerce_int(attrs.get(_ATTR_STATUS_CODE))
        if status_code is None:
            status_code = 200 if status == "success" else 500
        return InferenceEvent(
            event_id=str(attrs.get(_ATTR_EVENT_ID, "") or ""),
            deployment_id=deployment_id,
            status=status,
            status_code=status_code,
            latency_ms=_coerce_float(attrs.get(_ATTR_LATENCY)),
            inputs=_normalize_features(attrs.get(_ATTR_INPUTS)),
            output=_parse_json(attrs.get(_ATTR_OUTPUT)),
            timestamp=_ns_to_dt(row.get("timestamp")),
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

    async def record_metric_transition(
        self,
        deployment_id: str,
        metric: str,
        *,
        kind: str,
        error: str,
        window_end: datetime,
        at: datetime,
    ) -> None:
        """Append one entry to a metric's failure history.

        Only transitions are written — when a metric starts failing and when it recovers —
        so a metric broken for a day costs two rows rather than one per tick. The count of
        rows is then the number of incidents, which is the number worth reading.
        """
        await self._ensure_tables()
        sql = (
            f"INSERT INTO {FAILURES_TABLE} "
            f"(deployment_id, metric, kind, message, window_end, happened_at) VALUES ("
            f"{_sql_str(deployment_id)}, {_sql_str(metric)}, {_sql_str(kind)}, "
            f"{_sql_str(error[:500])}, {_sql_ts(window_end)}, {_sql_ts(at)})"
        )
        await self._execute(sql)

    async def fetch_metric_transitions(
        self, deployment_id: str, since: datetime
    ) -> list[MetricTransition]:
        """A metric's failure history: when it broke, when it came back."""
        await self._ensure_tables()
        sql = (
            f"SELECT metric, kind, message, happened_at FROM {FAILURES_TABLE} "
            f"WHERE deployment_id = {_sql_str(deployment_id)} AND happened_at >= {_sql_ts(since)} "
            f"ORDER BY happened_at ASC"
        )
        try:
            columns, rows = self._records(await self._execute(sql))
        except Exception as error:  # noqa: BLE001 — history is never worth an outage
            logger.warning("Could not read worker failure history: %s", error)
            return []
        transitions = []
        for row in rows:
            record = dict(zip(columns, row, strict=False))
            at = _ms_to_dt(record.get("happened_at"))
            if at is None:
                continue
            transitions.append(
                MetricTransition(
                    metric=str(record.get("metric", "") or ""),
                    kind=str(record.get("kind", "") or ""),
                    error=str(record.get("message", "") or ""),
                    at=at,
                )
            )
        return transitions

    async def last_materialized_window(self, deployment_id: str) -> datetime | None:
        await self._ensure_tables()
        sql = (
            f"SELECT max(window_end) FROM {RESULTS_TABLE} "
            f"WHERE deployment_id = {_sql_str(deployment_id)}"
        )
        try:
            _columns, rows = self._records(await self._execute(sql))
        except Exception as error:  # noqa: BLE001 — a missing answer only skips backfill
            logger.warning("Could not read the last materialized window: %s", error)
            return None
        value = rows[0][0] if rows and rows[0] else None
        return _ms_to_dt(value)

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
