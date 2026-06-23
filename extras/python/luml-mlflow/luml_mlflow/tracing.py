"""GenAI tracing bridge: MLflow trace/span entities → luml SDK tracker.

MLflow traces are scoped to an MLflow *experiment* (luml *group*) and a run is
**optional** at the MLflow API level. luml has no equivalent — ``tracker.log_span``
requires a luml *experiment*, and in this package a luml experiment IS an MLflow
*run*. So a trace without an active run has no luml home; this module funnels
that case through the shared ``unsupported()`` chokepoint (governed by
``LUML_MLFLOW_ON_UNSUPPORTED``) and never persists orphan spans either way.

Owning-run resolution: the run id is read from the trace's
``mlflow.sourceRun`` request metadata, which MLflow sets when a run is active
while tracing.
"""

import json
import logging
from typing import TYPE_CHECKING, Any

from mlflow.entities import (
    Span,
    SpanStatusCode,
    Trace,
    TraceData,
    TraceInfo,
    TraceLocation,
    TraceState,
)
from mlflow.exceptions import MlflowException
from mlflow.tracing.constant import TraceMetadataKey

from luml_mlflow._tracker import ThreadSafeTracker
from luml_mlflow._unsupported import unsupported

if TYPE_CHECKING:
    from luml.experiments.backends.data_types import SpanRecord

logger = logging.getLogger(__name__)

META_TRACE_INDEX = "trace_index"
"""Sub-key of the experiment ``metadata`` column. Maps ``trace_id`` →
``{tags, metadata, request_preview, response_preview, client_request_id,
state}`` so trace-level fields can round-trip through ``get_trace_info``."""

_SPAN_STATUS_TO_LUML: dict[str, int] = {
    SpanStatusCode.UNSET.value: 0,
    SpanStatusCode.OK.value: 1,
    SpanStatusCode.ERROR.value: 2,
}

def resolve_owning_run_id(trace_metadata: dict[str, str]) -> str | None:
    """Return the run id that owns a trace, or ``None`` if there is none.

    MLflow sets ``mlflow.sourceRun`` in the trace's request metadata when a run
    is active while tracing; that is the canonical signal of an owning run.
    """
    return (trace_metadata or {}).get(TraceMetadataKey.SOURCE_RUN)


def _trace_index(tracker: ThreadSafeTracker, run_id: str) -> dict[str, Any]:
    meta = tracker.get_experiment_metadata(run_id)
    return dict(meta.get(META_TRACE_INDEX) or {})


def _write_trace_index_entry(
    tracker: ThreadSafeTracker, run_id: str, trace_id: str, entry: dict[str, Any]
) -> None:
    index = _trace_index(tracker, run_id)
    index[trace_id] = entry
    tracker.update_experiment_metadata(run_id, {META_TRACE_INDEX: index})


def _read_trace_index_entry(
    tracker: ThreadSafeTracker, run_id: str, trace_id: str
) -> dict[str, Any] | None:
    return _trace_index(tracker, run_id).get(trace_id)


def find_trace_owner(tracker: ThreadSafeTracker, trace_id: str) -> str | None:
    """Reverse-look-up a trace's owning run id by scanning experiments' indices.

    Used by ``get_trace`` and friends, which only receive a ``trace_id`` (no run
    context). Linear scan of experiments is acceptable for the local store size
    this plugin is designed for.
    """
    for record in tracker.list_experiments():
        if record.metadata and trace_id in (
            record.metadata.get(META_TRACE_INDEX) or {}
        ):
            return record.id
    return None


def start_trace(tracker: ThreadSafeTracker, trace_info: TraceInfo) -> TraceInfo:
    """Persist a new trace's metadata onto its owning run's metadata column.

    No spans are persisted here — only the trace-level fields the SDK has no
    native home for. ``log_spans`` writes spans separately and may also arrive
    before ``start_trace`` in some MLflow clients; the index entry is created
    on demand if missing.
    """
    run_id = resolve_owning_run_id(trace_info.trace_metadata)
    if run_id is None:
        unsupported(
            "Tracing requires an active MLflow run (luml has no equivalent of "
            "an experiment-only trace). Wrap tracing in `with mlflow.start_run(): ...`",
        )
        return trace_info

    if tracker.get_experiment_record(run_id) is None:
        unsupported(
            f"Trace {trace_info.trace_id!r} references unknown run {run_id!r}; "
            "the run must be created before tracing.",
        )
        return trace_info

    entry = {
        "tags": dict(trace_info.tags or {}),
        "metadata": dict(trace_info.trace_metadata or {}),
        "request_preview": trace_info.request_preview,
        "response_preview": trace_info.response_preview,
        "client_request_id": trace_info.client_request_id,
        "request_time": trace_info.request_time,
        "execution_duration": trace_info.execution_duration,
        "state": trace_info.state.value if trace_info.state else None,
    }
    _write_trace_index_entry(tracker, run_id, trace_info.trace_id, entry)
    return trace_info


def log_spans(
    tracker: ThreadSafeTracker, location: str, spans: list[Span]
) -> list[Span]:
    """Persist a batch of MLflow spans via ``tracker.log_span``.

    Spans are grouped by trace id; each group's owning run is resolved from the
    first span that carries ``mlflow.sourceRun`` in its trace metadata. The
    ``location`` argument is the MLflow experiment id (= luml group id) and is
    used as a hint when no span carries source-run metadata: if the location
    matches the trace's already-indexed run, use that; otherwise the trace is
    treated as runless and dropped through ``unsupported()``.
    """
    if not spans:
        return []

    by_trace: dict[str, list[Span]] = {}
    for span in spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    written: list[Span] = []
    for trace_id, trace_spans in by_trace.items():
        run_id = _resolve_run_for_log_spans(tracker, trace_id, trace_spans, location)
        if run_id is None:
            continue
        if tracker.get_experiment_record(run_id) is None:
            unsupported(
                f"Spans for trace {trace_id!r} reference unknown run {run_id!r}; "
                "the run must be created before tracing.",
            )
            continue
        if _read_trace_index_entry(tracker, run_id, trace_id) is None:
            _write_trace_index_entry(
                tracker,
                run_id,
                trace_id,
                {
                    "tags": {},
                    "metadata": {TraceMetadataKey.SOURCE_RUN: run_id},
                    "request_preview": None,
                    "response_preview": None,
                    "client_request_id": None,
                    "request_time": (
                        min(s.start_time_ns for s in trace_spans) // 1_000_000
                    ),
                    "execution_duration": None,
                    "state": TraceState.IN_PROGRESS.value,
                },
            )
        for span in trace_spans:
            _write_span(tracker, run_id, span)
            written.append(span)
    return written


def _resolve_run_for_log_spans(
    tracker: ThreadSafeTracker,
    trace_id: str,
    trace_spans: list[Span],
    location: str | None,
) -> str | None:
    """Find the owning run id for a batch of spans within a single trace."""
    indexed_run = find_trace_owner(tracker, trace_id)
    if indexed_run is not None:
        return indexed_run

    if location and tracker.get_experiment_record(location) is not None:
        # location is an MLflow experiment id (= luml group id), not a run id —
        # only treat as a run id when it actually identifies an experiment row.
        return location

    return unsupported(
        f"Span batch for trace {trace_id!r} has no owning MLflow run "
        "(no mlflow.sourceRun in trace metadata and the location is not a "
        "known run). Wrap tracing in `with mlflow.start_run(): ...`",
    )


def _write_span(tracker: ThreadSafeTracker, run_id: str, span: Span) -> None:
    tracker.log_span(
        trace_id=span.trace_id,
        span_id=span.span_id,
        name=span.name,
        start_time_unix_nano=span.start_time_ns,
        end_time_unix_nano=span.end_time_ns or span.start_time_ns,
        parent_span_id=span.parent_id,
        kind=0,
        status_code=_SPAN_STATUS_TO_LUML.get(span.status.status_code.value, 0),
        status_message=span.status.description or None,
        attributes=dict(span.attributes) if span.attributes else None,
        events=_serialize_events(span.events),
        links=_serialize_links(span.links),
        trace_flags=0,
        experiment_id=run_id,
    )


def _serialize_events(events: list[Any] | None) -> list[dict[str, Any]] | None:
    if not events:
        return None
    out: list[dict[str, Any]] = []
    for ev in events:
        out.append(
            {
                "name": ev.name,
                "time_unix_nano": ev.timestamp,
                "attributes": dict(ev.attributes) if ev.attributes else {},
            }
        )
    return out


def _serialize_links(links: list[Any] | None) -> list[dict[str, Any]] | None:
    if not links:
        return None
    out: list[dict[str, Any]] = []
    for link in links:
        out.append(
            {
                "trace_id": link.trace_id,
                "span_id": link.span_id,
                "attributes": dict(link.attributes) if link.attributes else {},
            }
        )
    return out


def set_trace_tag(
    tracker: ThreadSafeTracker, trace_id: str, key: str, value: str
) -> None:
    run_id = find_trace_owner(tracker, trace_id)
    if run_id is None:
        raise MlflowException(f"Trace {trace_id!r} not found")
    entry = _read_trace_index_entry(tracker, run_id, trace_id) or {}
    tags = dict(entry.get("tags") or {})
    tags[key] = value
    entry["tags"] = tags
    _write_trace_index_entry(tracker, run_id, trace_id, entry)


def delete_trace_tag(tracker: ThreadSafeTracker, trace_id: str, key: str) -> None:
    run_id = find_trace_owner(tracker, trace_id)
    if run_id is None:
        raise MlflowException(f"Trace {trace_id!r} not found")
    entry = _read_trace_index_entry(tracker, run_id, trace_id) or {}
    tags = dict(entry.get("tags") or {})
    tags.pop(key, None)
    entry["tags"] = tags
    _write_trace_index_entry(tracker, run_id, trace_id, entry)


def get_trace_info(tracker: ThreadSafeTracker, trace_id: str) -> TraceInfo:
    run_id = find_trace_owner(tracker, trace_id)
    if run_id is None:
        raise MlflowException(f"Trace {trace_id!r} not found")
    entry = _read_trace_index_entry(tracker, run_id, trace_id) or {}
    return _build_trace_info(tracker, run_id, trace_id, entry)


def get_trace(tracker: ThreadSafeTracker, trace_id: str) -> Trace:
    run_id = find_trace_owner(tracker, trace_id)
    if run_id is None:
        raise MlflowException(f"Trace {trace_id!r} not found")
    entry = _read_trace_index_entry(tracker, run_id, trace_id) or {}
    info = _build_trace_info(tracker, run_id, trace_id, entry)
    details = tracker.get_trace(run_id, trace_id)
    spans: list[Span] = []
    if details is not None:
        for record in details.spans:
            spans.append(_span_record_to_mlflow(record))
    return Trace(info=info, data=TraceData(spans=spans))


def search_traces(
    tracker: ThreadSafeTracker,
    experiment_ids: list[str] | None,
    max_results: int = 100,
) -> tuple[list[TraceInfo], str | None]:
    """Minimal search: list trace infos owned by runs in the given group ids.

    ``experiment_ids`` in MLflow terms are luml *group* ids; we list each
    group's experiments (= runs), then unpack any trace-index entries on each
    run's metadata column. No filter parsing — that is governed by the same
    minimal-scope rule as ``_search_runs``.
    """
    group_ids = set(experiment_ids or [])
    infos: list[TraceInfo] = []
    for record in tracker.list_experiments():
        if group_ids and record.group_id not in group_ids:
            continue
        index = (record.metadata or {}).get(META_TRACE_INDEX) or {}
        for trace_id, entry in index.items():
            infos.append(_build_trace_info(tracker, record.id, trace_id, entry))
    infos.sort(key=lambda t: t.request_time, reverse=True)
    return infos[:max_results], None


def _build_trace_info(
    tracker: ThreadSafeTracker, run_id: str, trace_id: str, entry: dict[str, Any]
) -> TraceInfo:
    record = tracker.get_experiment_record(run_id)
    group_id = record.group_id if record is not None else ""
    state_value = entry.get("state") or TraceState.STATE_UNSPECIFIED.value
    try:
        state = TraceState(state_value)
    except ValueError:
        state = TraceState.STATE_UNSPECIFIED
    request_time = entry.get("request_time") or 0
    return TraceInfo(
        trace_id=trace_id,
        trace_location=TraceLocation.from_experiment_id(group_id or ""),
        request_time=request_time,
        state=state,
        request_preview=entry.get("request_preview"),
        response_preview=entry.get("response_preview"),
        client_request_id=entry.get("client_request_id"),
        execution_duration=entry.get("execution_duration"),
        trace_metadata=dict(entry.get("metadata") or {}),
        tags=dict(entry.get("tags") or {}),
    )


def _span_record_to_mlflow(record: "SpanRecord") -> Span:
    """Convert a luml ``SpanRecord`` back to an MLflow :class:`Span`.

    Constructs an OpenTelemetry ``ReadableSpan`` directly — the
    ``Span.from_dict`` path is base64-byte oriented, which doesn't fit our
    plain-hex storage, so we go around it.
    """
    from opentelemetry.sdk.trace import Event as OTelEvent
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.trace import SpanContext, TraceFlags
    from opentelemetry.trace.status import Status, StatusCode

    status_code_map = {
        0: StatusCode.UNSET,
        1: StatusCode.OK,
        2: StatusCode.ERROR,
    }
    trace_int = int(record.trace_id, 16)
    span_int = int(record.span_id, 16)
    ctx = SpanContext(
        trace_id=trace_int,
        span_id=span_int,
        is_remote=False,
        trace_flags=TraceFlags(record.trace_flags or 0),
    )
    parent_ctx = None
    if record.parent_span_id:
        parent_ctx = SpanContext(
            trace_id=trace_int,
            span_id=int(record.parent_span_id, 16),
            is_remote=False,
            trace_flags=TraceFlags(record.trace_flags or 0),
        )
    attributes = _ensure_json_attributes(dict(record.attributes or {}))
    events = [
        OTelEvent(
            name=ev.get("name", ""),
            timestamp=ev.get("time_unix_nano", 0),
            attributes=ev.get("attributes") or {},
        )
        for ev in (record.events or [])
    ]
    otel = ReadableSpan(
        name=record.name,
        context=ctx,
        parent=parent_ctx,
        start_time=record.start_time_unix_nano,
        end_time=record.end_time_unix_nano,
        status=Status(
            status_code_map.get(record.status_code or 0, StatusCode.UNSET),
            description=record.status_message or None,
        ),
        attributes=attributes,
        events=events,
    )
    return Span(otel)


def _ensure_json_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """MLflow's ``Span.from_dict`` expects attribute values that are
    JSON-encoded strings (per OTel exporter convention). Wrap any non-string
    values so they parse cleanly on the way back."""
    out: dict[str, Any] = {}
    for key, value in attributes.items():
        if isinstance(value, str):
            out[key] = value
        else:
            out[key] = json.dumps(value)
    return out


__all__ = [
    "META_TRACE_INDEX",
    "delete_trace_tag",
    "find_trace_owner",
    "get_trace",
    "get_trace_info",
    "log_spans",
    "resolve_owning_run_id",
    "search_traces",
    "set_trace_tag",
    "start_trace",
]
