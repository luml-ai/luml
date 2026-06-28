"""GenAI tracing bridge: MLflow trace/span entities → luml SDK tracker.

MLflow traces are scoped to an MLflow *experiment* (luml *group*) and a run is
**optional** at the MLflow API level. luml has no equivalent — ``tracker.log_span``
requires a luml *experiment*, and in this package a luml experiment IS an MLflow
*run*. So a trace without an active run has no luml home; this module funnels
that case through the shared ``unsupported()`` chokepoint (governed by
``LUML_MLFLOW_ON_UNSUPPORTED``) and never persists orphan spans either way.

Owning-run resolution: the run id is read from the trace's ``mlflow.sourceRun``
request metadata, which MLflow sets when a run is active while tracing. That
metadata reaches the store via ``start_trace`` (``trace.info``), but MLflow's V3
exporter calls ``log_spans`` *first* — so spans whose run is not yet known are
parked in the :mod:`luml_mlflow._span_buffer` and flushed when ``start_trace``
resolves the run. ``start_trace`` also tags the trace ``SPANS_LOCATION =
TRACKING_STORE`` so the exporter does not additionally try to upload trace data
to a (non-existent) luml artifact location.
"""

import json
import logging
import threading
from collections.abc import Callable
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
from mlflow.tracing.constant import (
    TRACE_REQUEST_ID_PREFIX,
    SpansLocation,
    TraceMetadataKey,
    TraceTagKey,
)

from luml_mlflow._span_buffer import get_buffer
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


_INDEX_LOCK = threading.Lock()
"""Serializes every read-modify-write of a run's ``trace_index``.

``update_experiment_metadata`` merges only at the top level, so each writer reads
the whole ``trace_index`` dict, inserts its entry, and writes the dict back. With
async trace logging on, multiple traces of the same run export concurrently; this
lock prevents those read-modify-writes from clobbering each other's entries (which
would make whole traces vanish)."""


def _trace_index(tracker: ThreadSafeTracker, run_id: str) -> dict[str, Any]:
    meta = tracker.get_experiment_metadata(run_id)
    return dict(meta.get(META_TRACE_INDEX) or {})


def _mutate_index(
    tracker: ThreadSafeTracker,
    run_id: str,
    fn: Callable[[dict[str, Any]], None],
) -> None:
    """Atomically read a run's trace index, apply ``fn``, and write it back."""
    with _INDEX_LOCK:
        index = _trace_index(tracker, run_id)
        fn(index)
        tracker.update_experiment_metadata(run_id, {META_TRACE_INDEX: index})


def _write_trace_index_entry(
    tracker: ThreadSafeTracker, run_id: str, trace_id: str, entry: dict[str, Any]
) -> None:
    _mutate_index(tracker, run_id, lambda index: index.__setitem__(trace_id, entry))


def _ensure_trace_index_entry(
    tracker: ThreadSafeTracker, run_id: str, trace_id: str, entry: dict[str, Any]
) -> None:
    """Insert ``entry`` for ``trace_id`` only if the trace has none yet.

    Atomic with respect to a concurrent ``start_trace`` writing the richer entry:
    whichever runs second sees the other's write, so ``start_trace``'s entry always
    wins and is never clobbered by this auto-created placeholder."""
    _mutate_index(tracker, run_id, lambda index: index.setdefault(trace_id, entry))


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
    """Persist a trace's metadata onto its owning run and flush its buffered spans.

    ``start_trace`` is where the owning run first becomes known (via
    ``mlflow.sourceRun``), so it also drains any spans that ``log_spans`` parked
    in the buffer before this point. A trace with no owning run is rejected,
    which evicts any such buffered spans rather than leaking them.
    """
    buffer = get_buffer()
    trace_id = trace_info.trace_id
    run_id = resolve_owning_run_id(trace_info.trace_metadata)
    if run_id is None:
        buffer.resolve(trace_id, None)
        return unsupported(
            "Tracing requires an active MLflow run (luml has no equivalent of "
            "an experiment-only trace). Wrap tracing in `with mlflow.start_run(): ...`",
            default=trace_info,
        )

    if tracker.get_experiment_record(run_id) is None:
        buffer.resolve(trace_id, None)
        return unsupported(
            f"Trace {trace_id!r} references unknown run {run_id!r}; "
            "the run must be created before tracing.",
            default=trace_info,
        )

    # Mark — and persist — that spans live in our tracking store. This both
    # suppresses the exporter's parallel upload of trace data to a (non-existent)
    # luml artifact location and tells the read path to load spans from the store
    # rather than from artifacts, so the tag must be in the stored ``tags``.
    trace_info.tags[TraceTagKey.SPANS_LOCATION] = SpansLocation.TRACKING_STORE.value
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
    _write_trace_index_entry(tracker, run_id, trace_id, entry)
    # Publish the resolution and flush spans parked before the run was known. The
    # index entry above is written first so any log_spans batch that races in
    # *after* this resolve (and so writes directly) still finds the trace indexed.
    for span in buffer.resolve(trace_id, run_id):
        _write_span(tracker, run_id, span)
    return trace_info


def log_spans(
    tracker: ThreadSafeTracker, location: str, spans: list[Span]
) -> list[Span]:
    """Persist a batch of MLflow spans via ``tracker.log_span``.

    Spans are grouped by trace id. If the trace's owning run is already known
    (``start_trace`` has run, or the location itself is a run), the spans are
    written immediately. Otherwise — MLflow's normal order, where ``log_spans``
    precedes ``start_trace`` — they are buffered until ``start_trace`` resolves
    the run. Spans for a trace already rejected as runless are dropped.
    """
    if not spans:
        return []

    buffer = get_buffer()
    by_trace: dict[str, list[Span]] = {}
    for span in spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    written: list[Span] = []
    for trace_id, trace_spans in by_trace.items():
        run_id = _resolve_logged_run(tracker, trace_id, location)
        if run_id is None:
            # The owning run is not known locally yet. Hand the spans to the buffer,
            # which atomically either parks them (start_trace has not resolved the
            # run) or — if start_trace already resolved it on another thread —
            # returns the resolution so we write/drop now with no lost-update window.
            resolved, owning_run = buffer.add(trace_id, trace_spans)
            if not resolved:
                continue
            if owning_run is None:
                unsupported(
                    f"Span batch for trace {trace_id!r} has no owning MLflow run "
                    "(no mlflow.sourceRun in trace metadata). Wrap tracing in "
                    "`with mlflow.start_run(): ...`",
                )
                continue
            run_id = owning_run
        else:
            # Run known via the trace index or the location. Publish the resolution
            # so spans another thread may have parked for this trace are drained and
            # later adds short-circuit instead of buffering forever.
            for span in buffer.resolve(trace_id, run_id):
                _write_span(tracker, run_id, span)
                written.append(span)

        _ensure_trace_index_entry(
            tracker,
            run_id,
            trace_id,
            {
                "tags": {
                    TraceTagKey.SPANS_LOCATION: SpansLocation.TRACKING_STORE.value
                },
                "metadata": {TraceMetadataKey.SOURCE_RUN: run_id},
                "request_preview": None,
                "response_preview": None,
                "client_request_id": None,
                "request_time": min(s.start_time_ns for s in trace_spans) // 1_000_000,
                "execution_duration": None,
                "state": TraceState.IN_PROGRESS.value,
            },
        )
        for span in trace_spans:
            _write_span(tracker, run_id, span)
            written.append(span)
    return written


def _resolve_logged_run(
    tracker: ThreadSafeTracker, trace_id: str, location: str | None
) -> str | None:
    """Return the owning run for a span batch, or ``None`` if not yet known.

    ``None`` means the run cannot be determined *yet* (``start_trace`` has not
    arrived); the caller buffers the spans rather than dropping them.
    """
    indexed_run = find_trace_owner(tracker, trace_id)
    if indexed_run is not None:
        return indexed_run

    if location and tracker.get_experiment_record(location) is not None:
        # location is an MLflow experiment id (= luml group id), not a run id —
        # only treat as a run id when it actually identifies an experiment row.
        return location

    return None


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
        # ``Span.links`` was only added in a later mlflow 3.x; older versions in
        # our supported range (>=3.1) lack it. Degrade gracefully, don't raise.
        links=_serialize_links(getattr(span, "links", None)),
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

    def _set(index: dict[str, Any]) -> None:
        entry = dict(index.get(trace_id) or {})
        tags = dict(entry.get("tags") or {})
        tags[key] = value
        entry["tags"] = tags
        index[trace_id] = entry

    _mutate_index(tracker, run_id, _set)


def delete_trace_tag(tracker: ThreadSafeTracker, trace_id: str, key: str) -> None:
    run_id = find_trace_owner(tracker, trace_id)
    if run_id is None:
        raise MlflowException(f"Trace {trace_id!r} not found")

    def _delete(index: dict[str, Any]) -> None:
        entry = dict(index.get(trace_id) or {})
        tags = dict(entry.get("tags") or {})
        tags.pop(key, None)
        entry["tags"] = tags
        index[trace_id] = entry

    _mutate_index(tracker, run_id, _delete)


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
    # MLflow trace ids are ``tr-<hex>``; the OTel context wants the bare hex int.
    trace_int = int(record.trace_id.removeprefix(TRACE_REQUEST_ID_PREFIX), 16)
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
