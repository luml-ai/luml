"""GreptimeDB-backed adapter for the Monitoring Query API store protocol.

Reads the OpenTelemetry ``inference_events`` span table that the collector writes (payload
lives in the ``span_attributes`` JSON under ``inference.*`` keys) and serves it as
:mod:`luml_satellite.monitoring.storage.query_store` types the Query API consumes.

Runtime/Overview/Traces are driven directly from ``inference_events``. Materialized views
(``monitoring_results`` / ``monitoring_alerts``) and the reference profile are optional: when
their tables do not yet exist the corresponding sections degrade to an empty state rather
than failing. Only a real database outage raises :class:`MonitoringStoreUnavailable`.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from luml_satellite.monitoring.dashboard.alerts import parse_alert_key
from luml_satellite.monitoring.dashboard.profile import build_reference_profile, profile_status
from luml_satellite.monitoring.dashboard.schemas import ProfileStatus
from luml_satellite.monitoring.storage.query_store import (
    DeploymentDescriptor,
    InferenceEvent,
    MonitoringStoreUnavailable,
    ReferenceProfile,
    SpanRecord,
    StoredAlert,
    StoredMetricResult,
    StoredMetricTransition,
)

logger = logging.getLogger("satellite")

INFERENCE_EVENTS_TABLE = "inference_events"
OTEL_TRACES_TABLE = "otel_traces"

# OTel proto enum names, translated to the numeric values the Platform span viewer expects.
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

_ATTR_SPAN_TYPE = "dfs.span_type"
RESULTS_TABLE = "monitoring_results"
ALERTS_TABLE = "monitoring_alerts"
FAILURES_TABLE = "monitoring_worker_failures"
_RESOLVED = "resolved"
_ACKNOWLEDGED = "acknowledged"

_HISTORY_LIMIT = 2000

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


class _TableMissing(_QueryError):
    """The statement named a table GreptimeDB has not created yet.

    The collector creates ``inference_events`` and ``otel_traces`` with the first span,
    the worker creates its own tables on its first tick. Until then a read of them is
    not an error the dashboard should show — there is simply nothing there yet.
    """


def _sql_ts(moment: datetime) -> str:
    return _sql_str(moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"))


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_path(key: str) -> str:
    return _sql_str(f'["{key}"]')


def _to_ns(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _ns_to_dt(value: Any) -> datetime | None:  # noqa: ANN401
    """Trace timestamps: the OTEL tables store nanoseconds."""
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000_000, UTC)
    except TypeError, ValueError:
        return None


def _ms_to_dt(value: Any) -> datetime | None:  # noqa: ANN401
    """Monitoring tables: the Agent writes ``TimestampMillisecond`` columns.

    Reading these as nanoseconds parsed every window boundary as 1970 — which is what the
    PSI-over-time axis and the alert timestamps used to show.
    """
    try:
        return datetime.fromtimestamp(int(value) / 1_000, UTC)
    except TypeError, ValueError:
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
    except TypeError, ValueError:
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
    """GreptimeDB-backed store for the monitoring query API."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 4000,
        database: str = "public",
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        profile_source: Callable[[UUID], dict[str, Any] | None] | None = None,
        profile_status_source: Callable[[UUID], ProfileStatus | str] | None = None,
        deployment_source: Callable[[UUID], dict[str, Any] | None] | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        if (username is None) != (password is None):
            raise ValueError("username and password must be set together")
        self._url = f"http://{host}:{port}/v1/sql"
        self._database = database
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None
        self._auth = (
            httpx.BasicAuth(username, password)
            if username is not None and password is not None
            else None
        )
        self._profile_source = profile_source
        self._profile_status_source = profile_status_source
        self._deployment_source = deployment_source

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
            client = self._get_client()
            if self._auth is None:
                response = await client.post(
                    self._url, params={"db": self._database}, data={"sql": sql}
                )
            else:
                response = await client.post(
                    self._url,
                    params={"db": self._database},
                    data={"sql": sql},
                    auth=self._auth,
                )
        except httpx.HTTPError as error:
            raise MonitoringStoreUnavailable("GreptimeDB unreachable") from error
        try:
            payload = response.json()
        except ValueError as error:
            raise MonitoringStoreUnavailable(
                f"GreptimeDB bad response ({response.status_code})"
            ) from error
        if payload.get("code", 0) != 0:
            error_text = str(payload.get("error", payload))
            if "table not found" in error_text.lower():
                raise _TableMissing(error_text)
            raise _QueryError(error_text)
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
        try:
            _columns, rows = await self._query(sql)
        except _TableMissing:
            rows = []  # no span has reached the collector yet — nothing predicted so far
        last = rows[0][0] if rows and rows[0] else None
        meta = self._deployment_source(deployment_id) if self._deployment_source else None
        if last is None and not meta:
            # Nothing known about this deployment: no telemetry and no Platform record.
            return None
        meta = meta or {}
        return DeploymentDescriptor(
            deployment_id=deployment_id,
            name=meta.get("name"),
            status=meta.get("status"),
            task_type=meta.get("task_type"),
            model_kind=meta.get("model_kind") or "unknown",
            model_name=meta.get("model_name"),
            environment=meta.get("environment"),
            satellite=meta.get("satellite"),
            inference_url=meta.get("inference_url"),
            last_prediction_at=_ns_to_dt(last) if last is not None else None,
            last_monitored_at=await self._last_monitored_at(deployment_id),
        )

    async def _last_monitored_at(self, deployment_id: UUID) -> datetime | None:
        """When the worker last materialized a window for this deployment."""
        sql = (
            f"SELECT max(window_end) FROM {RESULTS_TABLE} "
            f"WHERE deployment_id = {_sql_str(str(deployment_id))}"
        )
        try:
            _columns, rows = await self._query(sql)
        except MonitoringStoreUnavailable, _TableMissing:
            return None  # the worker has not materialized anything yet
        value = rows[0][0] if rows and rows[0] else None
        return _ms_to_dt(value) if value is not None else None

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
        try:
            columns, rows = await self._query(sql)
        except _TableMissing:
            return []
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
        except TypeError, ValueError:
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
        return self._to_result(deployment_id, group, window, record)

    async def fetch_result_history(
        self,
        deployment_id: UUID,
        group: str,
        window: str,
        *,
        since: datetime,
        until: datetime | None = None,
    ) -> list[StoredMetricResult]:
        sql = (
            f"SELECT deployment_id, metric, metric_values, severity, profile_status, window_end "
            f"FROM {RESULTS_TABLE} "
            f"WHERE deployment_id = {_sql_str(str(deployment_id))} "
            f"AND metric = {_sql_str(group)} AND window_end >= {_sql_ts(since)} "
            + (f"AND window_end <= {_sql_ts(until)} " if until is not None else "")
            + f"ORDER BY window_end ASC LIMIT {_HISTORY_LIMIT}"
        )
        try:
            columns, rows = await self._query(sql)
        except _QueryError as error:
            logger.debug("fetch_result_history skipped (%s): %s", group, error)
            return []
        return [
            self._to_result(deployment_id, group, window, dict(zip(columns, row, strict=False)))
            for row in rows
        ]

    @staticmethod
    def _to_result(
        deployment_id: UUID, group: str, window: str, record: dict[str, Any]
    ) -> StoredMetricResult:
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
            computed_at=_ms_to_dt(record.get("window_end")),
        )

    async def fetch_alerts(self, deployment_id: UUID) -> list[StoredAlert]:
        """The alerts that currently need attention, one row per metric.

        ``monitoring_alerts`` is append-only: the worker re-saves an alert on every window
        it still fires in, so the table holds the alert's whole history. Only the newest
        row per metric is its current state, and a resolved one is not an alert any more —
        counting the raw rows reported 97 "active" alerts where 29 were open.
        """
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
        latest: dict[str, StoredAlert] = {}
        for row in rows:
            record = dict(zip(columns, row, strict=False))
            metric = str(record.get("metric", "") or "")
            if metric in latest:  # rows arrive newest-first, so the first one wins
                continue
            parsed = parse_alert_key(metric)
            latest[metric] = StoredAlert(
                deployment_id=deployment_id,
                group=parsed.group,
                metric=metric,
                feature=parsed.feature,
                severity=_map_severity(str(record.get("severity", "") or "")),
                current_value=_as_float(record.get("current_value")),
                threshold=_as_float(record.get("threshold")),
                state=str(record.get("state", "open") or "open"),
                first_seen=_ms_to_dt(record.get("first_seen")),
                last_seen=_ms_to_dt(record.get("last_seen")),
            )
        return [alert for alert in latest.values() if alert.state != _RESOLVED]

    async def fetch_metric_transitions(
        self, deployment_id: UUID, since: datetime
    ) -> list[StoredMetricTransition]:
        sql = (
            f"SELECT metric, kind, message, happened_at FROM {FAILURES_TABLE} "
            f"WHERE deployment_id = {_sql_str(str(deployment_id))} "
            f"AND happened_at >= {_sql_ts(since)} "
            f"ORDER BY happened_at ASC"
        )
        try:
            columns, rows = await self._query(sql)
        except _QueryError as error:
            logger.debug("fetch_metric_transitions skipped: %s", error)
            return []
        transitions = []
        for row in rows:
            record = dict(zip(columns, row, strict=False))
            at = _ms_to_dt(record.get("happened_at"))
            if at is None:
                continue
            transitions.append(
                StoredMetricTransition(
                    metric=str(record.get("metric", "") or ""),
                    kind=str(record.get("kind", "") or ""),
                    error=str(record.get("message", "") or ""),
                    at=at,
                )
            )
        return transitions

    async def acknowledge_alert(self, deployment_id: UUID, metric: str) -> bool:
        """Rewrite the alert's newest row as acknowledged.

        The table is append-only and keyed by ``(deployment_id, metric)`` over
        ``last_seen``: writing the same row back with the same ``last_seen`` replaces it
        rather than adding another entry to the alert's history, so acknowledging leaves
        the timeline of when it fired untouched.
        """
        current = next(
            (a for a in await self.fetch_alerts(deployment_id) if a.metric == metric), None
        )
        if current is None or current.last_seen is None or current.first_seen is None:
            return False
        sql = (
            f"INSERT INTO {ALERTS_TABLE} "
            f"(deployment_id, metric, current_value, threshold, severity, state, "
            f"first_seen, last_seen) VALUES ("
            f"{_sql_str(str(deployment_id))}, {_sql_str(metric)}, "
            f"{_sql_number(current.current_value)}, {_sql_number(current.threshold)}, "
            f"{_sql_str(_worker_severity(current.severity))}, {_sql_str(_ACKNOWLEDGED)}, "
            f"{_sql_ts(current.first_seen)}, {_sql_ts(current.last_seen)})"
        )
        await self._query(sql)
        return True

    async def fetch_profile(self, deployment_id: UUID) -> ReferenceProfile | None:
        return build_reference_profile(deployment_id, self._raw_profile(deployment_id))

    async def profile_status(self, deployment_id: UUID) -> ProfileStatus:
        if self._profile_status_source is not None:
            try:
                return ProfileStatus(self._profile_status_source(deployment_id))
            except TypeError, ValueError:
                logger.warning("Invalid reference profile status", exc_info=True)
            except Exception:  # noqa: BLE001 — deployment lookup must not break the dashboard
                logger.warning("Failed to read reference profile status", exc_info=True)
        return profile_status(self._raw_profile(deployment_id))

    def _raw_profile(self, deployment_id: UUID) -> dict[str, Any] | None:
        if self._profile_source is None:
            return None
        try:
            return self._profile_source(deployment_id)
        except Exception:  # noqa: BLE001 — a profile lookup must never break the dashboard
            logger.warning("Failed to read reference profile", exc_info=True)
            return None


def _as_float(value: Any) -> float | None:  # noqa: ANN401
    if value is None or value == "":
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _sql_number(value: float | None) -> str:
    return "NULL" if value is None else repr(float(value))


def _worker_severity(value: Any) -> str:  # noqa: ANN401
    """Back to the worker's vocabulary: the Query API says "ok", the worker "normal"."""
    text = str(value)
    return "normal" if text == "ok" else text


def _map_severity(value: Any) -> Any:  # noqa: ANN401
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
