"""GreptimeDB-backed adapter for the Monitoring Query API store protocol.

Reads the OpenTelemetry ``inference_events`` span table that the collector writes (payload
lives in the ``span_attributes`` JSON under ``inference.*`` keys) and serves it as
:mod:`agent.monitoring.query_store` types the Query API consumes.

Runtime/Overview/Traces are driven directly from ``inference_events``. Materialized views
(``monitoring_results`` / ``monitoring_alerts``) and the reference profile are optional: when
their tables do not yet exist the corresponding sections degrade to an empty state rather
than failing. Only a real database outage raises :class:`MonitoringStoreUnavailable`.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from agent.monitoring.query_store import (
    DeploymentDescriptor,
    InferenceEvent,
    MonitoringStoreUnavailable,
    ReferenceProfile,
    SpanRecord,
    StoredAlert,
    StoredMetricResult,
)

logger = logging.getLogger("satellite")

INFERENCE_EVENTS_TABLE = "inference_events"
OTEL_TRACES_TABLE = "otel_traces"

# The collector stores span kind/status as OTel proto enum names; the Platform's span
# viewer expects their numeric values, so translate on the way out.
_SPAN_KINDS = {
    "SPAN_KIND_UNSPECIFIED": 0,
    "SPAN_KIND_INTERNAL": 1,
    "SPAN_KIND_SERVER": 2,
    "SPAN_KIND_CLIENT": 3,
    "SPAN_KIND_PRODUCER": 4,
    "SPAN_KIND_CONSUMER": 5,
}
_SPAN_STATUS = {
    "STATUS_CODE_UNSET": 0,
    "STATUS_CODE_OK": 1,
    "STATUS_CODE_ERROR": 2,
}

# Set by instrumentation that knows its span semantics (chat/agent/tool/...); absent
# spans fall back to the viewer's default icon.
_ATTR_SPAN_TYPE = "dfs.span_type"
RESULTS_TABLE = "monitoring_results"
ALERTS_TABLE = "monitoring_alerts"

# span_attributes keys emitted by the Satellite inference instrumentation.
_ATTR_DEPLOYMENT = "inference.deployment_id"
_ATTR_EVENT_ID = "inference.event_id"
_ATTR_STATUS = "inference.status"
_ATTR_LATENCY = "inference.latency_ms"
_ATTR_TRACE = "inference.trace_id"
_ATTR_SPAN = "inference.span_id"
_ATTR_INPUTS = "inference.inputs"
_ATTR_OUTPUT = "inference.output"


class _QueryError(RuntimeError):
    """A query-level GreptimeDB error (e.g. a table that does not exist yet)."""


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_path(key: str) -> str:
    # Bracket path so keys containing dots (inference.deployment_id) are treated as one
    # literal key rather than a nested path.
    return _sql_str(f'["{key}"]')


def _to_ns(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _ns_to_dt(value: Any) -> datetime | None:  # noqa: ANN401
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000_000, UTC)
    except (TypeError, ValueError):
        return None


def _as_attrs(value: Any) -> dict[str, Any]:  # noqa: ANN401
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _as_int(value: Any) -> int | None:  # noqa: ANN401
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[Any]:  # noqa: ANN401
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


class GreptimeQueryStore:
    """Query API :class:`~agent.monitoring.query_store.MonitoringStore` over GreptimeDB."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 4000,
        database: str = "public",
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._url = f"http://{host}:{port}/v1/sql"
        self._database = database
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _query(self, sql: str) -> tuple[list[str], list[list[Any]]]:
        try:
            response = await self._get_client().post(
                self._url, params={"db": self._database}, data={"sql": sql}
            )
        except httpx.HTTPError as error:
            raise MonitoringStoreUnavailable("GreptimeDB unreachable") from error
        # GreptimeDB returns SQL-level failures (e.g. a missing table) as an HTTP 4xx with a
        # JSON body carrying a non-zero code, so parse the body before trusting the status.
        try:
            payload = response.json()
        except ValueError as error:
            raise MonitoringStoreUnavailable(
                f"GreptimeDB bad response ({response.status_code})"
            ) from error
        if payload.get("code", 0) != 0:
            raise _QueryError(str(payload.get("error", payload)))
        for item in payload.get("output", []):
            records = item.get("records")
            if records:
                columns = [c["name"] for c in records["schema"]["column_schemas"]]
                return columns, records.get("rows", [])
        return [], []

    async def describe_deployment(self, deployment_id: UUID) -> DeploymentDescriptor | None:
        dep = _sql_str(str(deployment_id))
        sql = (
            f"SELECT max(timestamp) FROM {INFERENCE_EVENTS_TABLE} "
            f"WHERE json_get_string(span_attributes, {_json_path(_ATTR_DEPLOYMENT)}) = {dep}"
        )
        _columns, rows = await self._query(sql)
        last = rows[0][0] if rows and rows[0] else None
        if last is None:
            # No collected events for this deployment yet.
            return None
        return DeploymentDescriptor(
            deployment_id=deployment_id,
            last_prediction_at=_ns_to_dt(last),
        )

    async def fetch_events(
        self, deployment_id: UUID, start: datetime, end: datetime
    ) -> list[InferenceEvent]:
        dep = _sql_str(str(deployment_id))
        sql = (
            f"SELECT timestamp, span_attributes FROM {INFERENCE_EVENTS_TABLE} "
            f"WHERE json_get_string(span_attributes, {_json_path(_ATTR_DEPLOYMENT)}) = {dep} "
            f"AND timestamp >= {_to_ns(start)} AND timestamp < {_to_ns(end)} "
            f"ORDER BY timestamp"
        )
        columns, rows = await self._query(sql)
        events = []
        for row in rows:
            record = dict(zip(columns, row, strict=False))
            event = self._to_event(deployment_id, record)
            if event is not None:
                events.append(event)
        return events

    async def fetch_spans(self, trace_id: str) -> list[SpanRecord]:
        sql = (
            f"SELECT trace_id, span_id, parent_span_id, span_name, span_kind, "
            f"timestamp, timestamp_end, span_status_code, span_status_message, "
            f"span_attributes, span_events, span_links "
            f"FROM {OTEL_TRACES_TABLE} "
            f"WHERE trace_id = {_sql_str(trace_id)} ORDER BY timestamp"
        )
        try:
            columns, rows = await self._query(sql)
        except _QueryError:
            # otel_traces is optional: without it a trace still renders as its single
            # inference span, synthesized by the query service.
            logger.debug("otel_traces unavailable; no span tree for trace %s", trace_id)
            return []
        spans = []
        for row in rows:
            span = self._to_span(dict(zip(columns, row, strict=False)))
            if span is not None:
                spans.append(span)
        return spans

    @staticmethod
    def _to_span(record: dict[str, Any]) -> SpanRecord | None:
        start, end = record.get("timestamp"), record.get("timestamp_end")
        span_id = str(record.get("span_id") or "")
        if start is None or end is None or not span_id:
            return None
        attrs = _as_attrs(record.get("span_attributes"))
        span_type = attrs.get(_ATTR_SPAN_TYPE)
        # The collector writes '' rather than NULL for a missing parent.
        parent = str(record.get("parent_span_id") or "") or None
        message = str(record.get("span_status_message") or "") or None
        return SpanRecord(
            span_id=span_id,
            trace_id=str(record.get("trace_id") or ""),
            parent_span_id=parent,
            name=str(record.get("span_name") or ""),
            kind=_SPAN_KINDS.get(str(record.get("span_kind") or ""), 0),
            start_time_unix_nano=int(start),
            end_time_unix_nano=int(end),
            status_code=_SPAN_STATUS.get(str(record.get("span_status_code") or "")),
            status_message=message,
            dfs_span_type=_as_int(span_type),
            attributes=attrs,
            events=_as_list(record.get("span_events")),
            links=_as_list(record.get("span_links")),
        )

    @staticmethod
    def _to_event(deployment_id: UUID, record: dict[str, Any]) -> InferenceEvent | None:
        attrs = _as_attrs(record.get("span_attributes"))
        ts = _ns_to_dt(record.get("timestamp"))
        if ts is None:
            return None
        status = str(attrs.get(_ATTR_STATUS, "") or "")
        try:
            latency = float(attrs.get(_ATTR_LATENCY))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            latency = 0.0
        return InferenceEvent(
            event_id=str(attrs.get(_ATTR_EVENT_ID, "") or ""),
            deployment_id=deployment_id,
            ts=ts,
            status=status,
            status_code=200 if status == "success" else 500,
            latency_ms=latency,
            trace_id=attrs.get(_ATTR_TRACE),
            span_id=attrs.get(_ATTR_SPAN),
            inputs=attrs.get(_ATTR_INPUTS),
            output=attrs.get(_ATTR_OUTPUT),
        )

    async def fetch_result(
        self, deployment_id: UUID, group: str, window: str
    ) -> StoredMetricResult | None:
        dep = _sql_str(str(deployment_id))
        sql = (
            f"SELECT deployment_id, metric, metric_values, severity, profile_status, window_end "
            f"FROM {RESULTS_TABLE} "
            f"WHERE deployment_id = {dep} AND metric = {_sql_str(group)} "
            f"ORDER BY window_end DESC LIMIT 1"
        )
        try:
            columns, rows = await self._query(sql)
        except _QueryError as error:
            logger.debug("fetch_result skipped (%s): %s", group, error)
            return None
        if not rows:
            return None
        record = dict(zip(columns, rows[0], strict=False))
        try:
            values = json.loads(record.get("metric_values") or "{}")
        except json.JSONDecodeError:
            values = {}
        return StoredMetricResult(
            deployment_id=deployment_id,
            group=group,
            window=window,
            values=_normalize_severity(values) if isinstance(values, dict) else {},
            severity=_map_severity(str(record.get("severity", "") or "")),
            computed_at=_ns_to_dt(record.get("window_end")),
        )

    async def fetch_alerts(self, deployment_id: UUID) -> list[StoredAlert]:
        dep = _sql_str(str(deployment_id))
        sql = (
            f"SELECT deployment_id, metric, current_value, threshold, severity, state, "
            f"first_seen, last_seen FROM {ALERTS_TABLE} "
            f"WHERE deployment_id = {dep} ORDER BY last_seen DESC"
        )
        try:
            columns, rows = await self._query(sql)
        except _QueryError as error:
            logger.debug("fetch_alerts skipped: %s", error)
            return []
        alerts = []
        for row in rows:
            record = dict(zip(columns, row, strict=False))
            alerts.append(
                StoredAlert(
                    deployment_id=deployment_id,
                    group=str(record.get("metric", "") or ""),
                    metric=str(record.get("metric", "") or ""),
                    severity=_map_severity(str(record.get("severity", "") or "")),
                    current_value=_as_float(record.get("current_value")),
                    threshold=_as_float(record.get("threshold")),
                    state=str(record.get("state", "open") or "open"),
                    first_seen=_ns_to_dt(record.get("first_seen")),
                    last_seen=_ns_to_dt(record.get("last_seen")),
                )
            )
        return alerts

    async def fetch_profile(self, deployment_id: UUID) -> ReferenceProfile | None:
        # The reference profile is not materialized in GreptimeDB; the Reference Profile
        # tab shows an empty state until a profile source is wired.
        return None

    async def profile_status(self, deployment_id: UUID) -> str:
        return "ready"


def _as_float(value: Any) -> float | None:  # noqa: ANN401
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_severity(value: Any) -> Any:  # noqa: ANN401
    # The worker (models.Severity) says "normal"; the Query API contract says "ok".
    return "ok" if value == "normal" else value


def _normalize_severity(obj: Any) -> Any:  # noqa: ANN401
    """Translate the worker's severity vocabulary within a materialized result payload."""
    if isinstance(obj, dict):
        return {
            key: (
                _map_severity(value)
                if key in ("status", "severity")
                else _normalize_severity(value)
            )
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize_severity(item) for item in obj]
    return obj
