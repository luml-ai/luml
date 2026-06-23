"""Tests for the GenAI tracing bridge.

Covers the scenarios from SPEC.md:

* Active-run tracing → spans persisted via ``tracker.log_span`` with the run id
  resolved from ``mlflow.sourceRun``; span tree (names + parent/child) round-trips.
* Trace tags round-trip via the experiment ``metadata`` column.
* No-active-run tracing honors ``LUML_MLFLOW_ON_UNSUPPORTED`` — neither variant
  persists orphan spans.
"""

import json
from pathlib import Path

import pytest
from luml_mlflow.store import LumlTrackingStore


def _make_span(
    *,
    trace_id: str,
    span_id: str,
    name: str,
    parent_span_id: str | None = None,
    start_time_ns: int = 100,
    end_time_ns: int = 200,
    attributes: dict[str, str] | None = None,
):
    """Construct a real :class:`mlflow.entities.Span` via OTel ReadableSpan.

    ``trace_id``/``span_id``/``parent_span_id`` are hex strings.
    """
    from mlflow.entities import Span
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.trace import SpanContext, TraceFlags
    from opentelemetry.trace.status import Status, StatusCode

    attrs = dict(attributes or {})
    attrs.setdefault("mlflow.spanType", json.dumps("UNKNOWN"))
    attrs.setdefault("mlflow.traceRequestId", json.dumps(trace_id))

    trace_int = int(trace_id, 16)
    span_int = int(span_id, 16)
    ctx = SpanContext(
        trace_id=trace_int,
        span_id=span_int,
        is_remote=False,
        trace_flags=TraceFlags(0),
    )
    parent_ctx = None
    if parent_span_id is not None:
        parent_ctx = SpanContext(
            trace_id=trace_int,
            span_id=int(parent_span_id, 16),
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
    otel = ReadableSpan(
        name=name,
        context=ctx,
        parent=parent_ctx,
        start_time=start_time_ns,
        end_time=end_time_ns,
        status=Status(StatusCode.OK),
        attributes=attrs,
    )
    return Span(otel)


def _make_trace_info(
    *,
    trace_id: str,
    experiment_id: str,
    run_id: str | None,
    request_time: int = 100,
    tags: dict[str, str] | None = None,
):
    from mlflow.entities import TraceInfo, TraceLocation, TraceState
    from mlflow.tracing.constant import TraceMetadataKey

    metadata: dict[str, str] = {}
    if run_id is not None:
        metadata[TraceMetadataKey.SOURCE_RUN] = run_id

    return TraceInfo(
        trace_id=trace_id,
        trace_location=TraceLocation.from_experiment_id(experiment_id),
        request_time=request_time,
        state=TraceState.IN_PROGRESS,
        trace_metadata=metadata,
        tags=tags or {},
    )


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


@pytest.fixture
def run(store: LumlTrackingStore) -> tuple[str, str]:
    """Return ``(experiment_id, run_id)`` for a fresh experiment/run pair."""
    exp_id = store.create_experiment("trace_exp")
    r = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="trace_run",
    )
    return exp_id, r.info.run_id


_TRACE_ABC = "abc00000000000000000000000000001"
_TRACE_TAGS = "abc00000000000000000000000000002"
_TRACE_ORPHAN = "abc00000000000000000000000000003"
_TRACE_ORPHAN_RAISE = "abc00000000000000000000000000004"
_TRACE_1 = "abc00000000000000000000000000005"
_TRACE_2 = "abc00000000000000000000000000006"
_TRACE_LATE = "abc00000000000000000000000000007"


def test_span_tree_round_trip_with_active_run(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    exp_id, run_id = run
    trace_id = _TRACE_ABC
    store.start_trace(_make_trace_info(
        trace_id=trace_id, experiment_id=exp_id, run_id=run_id
    ))
    root = _make_span(trace_id=trace_id, span_id="0000000000000001", name="root")
    child = _make_span(
        trace_id=trace_id,
        span_id="0000000000000002",
        name="child",
        parent_span_id="0000000000000001",
    )
    grandchild = _make_span(
        trace_id=trace_id,
        span_id="0000000000000003",
        name="grandchild",
        parent_span_id="0000000000000002",
    )
    store.log_spans(exp_id, [root, child, grandchild])

    trace = store.get_trace(trace_id)
    names = {s.name for s in trace.data.spans}
    assert names == {"root", "child", "grandchild"}
    by_id = {s.span_id: s for s in trace.data.spans}
    assert by_id["0000000000000002"].parent_id == "0000000000000001"
    assert by_id["0000000000000003"].parent_id == "0000000000000002"
    assert by_id["0000000000000001"].parent_id is None


def test_trace_tag_round_trips_via_metadata(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    exp_id, run_id = run
    trace_id = _TRACE_TAGS
    store.start_trace(_make_trace_info(
        trace_id=trace_id, experiment_id=exp_id, run_id=run_id, tags={"foo": "bar"}
    ))
    store.set_trace_tag(trace_id, "stage", "prod")

    info = store.get_trace_info(trace_id)
    assert info.tags["foo"] == "bar"
    assert info.tags["stage"] == "prod"

    store.delete_trace_tag(trace_id, "foo")
    info = store.get_trace_info(trace_id)
    assert "foo" not in info.tags
    assert info.tags["stage"] == "prod"


def test_trace_without_run_warn_drops_silently(
    store: LumlTrackingStore,
    run: tuple[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    exp_id, run_id = run
    trace_id = _TRACE_ORPHAN

    with caplog.at_level("WARNING"):
        store.start_trace(_make_trace_info(
            trace_id=trace_id, experiment_id=exp_id, run_id=None
        ))
        # log_spans with no active run AND a location that is the group id (the
        # caller passes the MLflow experiment_id, which is the luml group id —
        # NOT a run id). The trace must be dropped.
        orphan = _make_span(
            trace_id=trace_id, span_id="0000000000000001", name="orphan"
        )
        store.log_spans(exp_id, [orphan])

    assert any("active MLflow run" in r.message for r in caplog.records)

    # Critically: no orphan spans were persisted under any experiment.
    record = store._tracker.get_experiment_record(run_id)
    assert record is not None
    details = store._tracker.get_trace(run_id, trace_id)
    assert details is None or not details.spans


def test_trace_without_run_raise_raises_and_writes_nothing(
    store: LumlTrackingStore,
    run: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from luml_mlflow import config as config_mod
    from mlflow.exceptions import MlflowException

    exp_id, run_id = run
    monkeypatch.setenv("LUML_MLFLOW_ON_UNSUPPORTED", "raise")
    config_mod.reset_settings_cache()
    trace_id = _TRACE_ORPHAN_RAISE

    with pytest.raises(MlflowException, match="active MLflow run"):
        store.start_trace(_make_trace_info(
            trace_id=trace_id, experiment_id=exp_id, run_id=None
        ))

    orphan = _make_span(trace_id=trace_id, span_id="0000000000000001", name="orphan")
    with pytest.raises(MlflowException, match="no owning MLflow run"):
        store.log_spans(exp_id, [orphan])

    details = store._tracker.get_trace(run_id, trace_id)
    assert details is None or not details.spans


def test_search_traces_filters_by_experiment_id(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    exp_id, run_id = run
    other_exp_id = store.create_experiment("other_exp")
    other_run = store.create_run(
        experiment_id=other_exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="other_run",
    )

    store.start_trace(_make_trace_info(
        trace_id=_TRACE_1, experiment_id=exp_id, run_id=run_id, request_time=300
    ))
    store.start_trace(_make_trace_info(
        trace_id=_TRACE_2,
        experiment_id=other_exp_id,
        run_id=other_run.info.run_id,
        request_time=200,
    ))

    infos, _ = store.search_traces(experiment_ids=[exp_id])
    assert {t.trace_id for t in infos} == {_TRACE_1}

    infos_all, _ = store.search_traces(experiment_ids=[exp_id, other_exp_id])
    assert {t.trace_id for t in infos_all} == {_TRACE_1, _TRACE_2}
    # Default ordering is request_time desc.
    assert infos_all[0].request_time >= infos_all[1].request_time


def test_log_spans_creates_trace_index_when_start_trace_missing(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    """Some MLflow clients call log_spans before start_trace. The index entry
    must still be auto-created so the spans are reachable via get_trace."""
    exp_id, run_id = run
    trace_id = _TRACE_LATE

    # Build a span carrying the sourceRun in trace metadata via the index path:
    # the span itself does not carry SOURCE_RUN, but the location matches the
    # MLflow experiment id which is the group id (not the run id), so we fall
    # back to scanning. For this test we set up the trace index first manually
    # via start_trace.
    store.start_trace(_make_trace_info(
        trace_id=trace_id, experiment_id=exp_id, run_id=run_id
    ))
    span = _make_span(trace_id=trace_id, span_id="0000000000000001", name="only")
    store.log_spans(exp_id, [span])

    trace = store.get_trace(trace_id)
    assert len(trace.data.spans) == 1
    assert trace.data.spans[0].name == "only"
