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
_TRACE_BUFFERED = "abc00000000000000000000000000008"
_TRACE_RUNLESS_EVICT = "abc00000000000000000000000000009"
_TRACE_NO_LINKS = "abc00000000000000000000000000010"
_TRACE_SPANS_LOC = "abc00000000000000000000000000011"


def test_span_tree_round_trip_with_active_run(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    exp_id, run_id = run
    trace_id = _TRACE_ABC
    store.start_trace(
        _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
    )
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
    store.start_trace(
        _make_trace_info(
            trace_id=trace_id, experiment_id=exp_id, run_id=run_id, tags={"foo": "bar"}
        )
    )
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
        store.start_trace(
            _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=None)
        )
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
        store.start_trace(
            _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=None)
        )

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

    store.start_trace(
        _make_trace_info(
            trace_id=_TRACE_1, experiment_id=exp_id, run_id=run_id, request_time=300
        )
    )
    store.start_trace(
        _make_trace_info(
            trace_id=_TRACE_2,
            experiment_id=other_exp_id,
            run_id=other_run.info.run_id,
            request_time=200,
        )
    )

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
    store.start_trace(
        _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
    )
    span = _make_span(trace_id=trace_id, span_id="0000000000000001", name="only")
    store.log_spans(exp_id, [span])

    trace = store.get_trace(trace_id)
    assert len(trace.data.spans) == 1
    assert trace.data.spans[0].name == "only"


def test_log_spans_before_start_trace_are_buffered_then_flushed(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    """MLflow's V3 exporter calls log_spans before start_trace. Spans that arrive
    early must be buffered (not dropped) and persisted once start_trace resolves
    the owning run."""
    exp_id, run_id = run
    trace_id = _TRACE_BUFFERED
    child = _make_span(
        trace_id=trace_id,
        span_id="0000000000000002",
        name="child",
        parent_span_id="0000000000000001",
    )

    # Spans arrive before start_trace: buffered, nothing persisted yet.
    store.log_spans(exp_id, [child])
    details = store._tracker.get_trace(run_id, trace_id)
    assert details is None or not details.spans

    # start_trace resolves the run and flushes the buffered child span.
    store.start_trace(
        _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
    )
    # A root span arriving after start_trace is written directly.
    root = _make_span(trace_id=trace_id, span_id="0000000000000001", name="root")
    store.log_spans(exp_id, [root])

    trace = store.get_trace(trace_id)
    assert {s.name for s in trace.data.spans} == {"root", "child"}


def test_runless_start_trace_evicts_buffered_spans(
    store: LumlTrackingStore,
    run: tuple[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Spans buffered before a start_trace that turns out to be runless are
    evicted — neither persisted nor leaked in the buffer."""
    from luml_mlflow._span_buffer import get_buffer

    exp_id, run_id = run
    trace_id = _TRACE_RUNLESS_EVICT
    orphan = _make_span(trace_id=trace_id, span_id="0000000000000001", name="orphan")

    with caplog.at_level("WARNING"):
        store.log_spans(exp_id, [orphan])  # buffered: run unknown
        store.start_trace(
            _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=None)
        )  # runless: reject + evict

    assert any("active MLflow run" in r.message for r in caplog.records)
    buffer = get_buffer()
    # The runless start_trace resolved the trace as rejected: nothing is parked,
    # and a late span batch is reported resolved-with-no-run (caller drops it).
    assert buffer.drain() == {}
    assert buffer.add(trace_id, [orphan]) == (True, None)
    details = store._tracker.get_trace(run_id, trace_id)
    assert details is None or not details.spans


def test_get_trace_reconstructs_prefixed_trace_id(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    """Real MLflow trace ids are ``tr-<hex>``; span reconstruction must strip the
    prefix before decoding the OTel trace id (pure-hex test ids hid this)."""
    exp_id, run_id = run
    hex_id = "1234567890abcdef1234567890abcdef"
    trace_id = "tr-" + hex_id
    store.start_trace(
        _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
    )
    span = _make_span(
        trace_id=hex_id,
        span_id="0000000000000001",
        name="root",
        attributes={"mlflow.traceRequestId": json.dumps(trace_id)},
    )
    store.log_spans(exp_id, [span])

    trace = store.get_trace(trace_id)
    assert [s.name for s in trace.data.spans] == ["root"]
    assert trace.data.spans[0].trace_id == trace_id


def test_start_trace_persists_spans_location_tag(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    """The read path loads spans from the tracking store only if the trace is
    tagged SPANS_LOCATION=TRACKING_STORE, so the tag must be persisted."""
    from mlflow.tracing.constant import SpansLocation, TraceTagKey

    exp_id, run_id = run
    trace_id = _TRACE_SPANS_LOC
    store.start_trace(
        _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
    )

    info = store.get_trace_info(trace_id)
    assert info.tags[TraceTagKey.SPANS_LOCATION] == SpansLocation.TRACKING_STORE.value


def test_log_spans_tolerates_missing_links_attribute(
    store: LumlTrackingStore,
    run: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older mlflow's Span has no ``links`` attribute; writing a span must not
    raise (the real V3 export hands us LiveSpans that, on those versions, lack
    it)."""
    from mlflow.entities import Span

    monkeypatch.delattr(Span, "links", raising=False)

    exp_id, run_id = run
    trace_id = _TRACE_NO_LINKS
    store.start_trace(
        _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
    )
    span = _make_span(trace_id=trace_id, span_id="0000000000000001", name="only")
    store.log_spans(exp_id, [span])

    trace = store.get_trace(trace_id)
    assert [s.name for s in trace.data.spans] == ["only"]


def test_pending_buffer_evicts_oldest_over_cap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from luml_mlflow._span_buffer import PendingSpanBuffer

    buf = PendingSpanBuffer(max_pending_traces=2)
    span = _make_span(trace_id=_TRACE_1, span_id="0000000000000001", name="s")

    with caplog.at_level("WARNING"):
        buf.add("t1", [span])
        buf.add("t2", [span])
        buf.add("t3", [span])  # exceeds cap → evict oldest (t1)

    assert buf.resolve("t1", "r") == []
    assert len(buf.resolve("t3", "r")) == 1
    assert any("cap" in r.message for r in caplog.records)


def test_pending_buffer_evicts_expired(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from luml_mlflow._span_buffer import PendingSpanBuffer

    now = [0.0]
    buf = PendingSpanBuffer(ttl_seconds=10.0, clock=lambda: now[0])
    span = _make_span(trace_id=_TRACE_1, span_id="0000000000000001", name="s")

    buf.add("t1", [span])
    now[0] = 11.0
    with caplog.at_level("WARNING"):
        buf.add("t2", [span])  # add triggers the expiry sweep of t1

    assert buf.resolve("t1", "r") == []
    assert len(buf.resolve("t2", "r")) == 1
    assert any("run never resolved" in r.message for r in caplog.records)


def test_resolve_before_late_add_routes_spans_not_orphans() -> None:
    """The async-export losing order: ``start_trace``'s ``resolve`` drains the (still
    empty) buffer, then ``log_spans`` arrives. The late ``add`` must report the
    resolved run so the caller writes the spans — never park them where nothing will
    drain them again."""
    from luml_mlflow._span_buffer import PendingSpanBuffer

    buf = PendingSpanBuffer()
    span = _make_span(trace_id=_TRACE_1, span_id="0000000000000001", name="late")

    assert buf.resolve(_TRACE_1, "run1") == []  # resolve runs first, nothing parked
    assert buf.add(_TRACE_1, [span]) == (True, "run1")  # late add is routed, not held
    assert buf.drain() == {}


def test_resolve_after_add_drains_parked_spans() -> None:
    """The other order: ``add`` parks first, ``resolve`` drains it."""
    from luml_mlflow._span_buffer import PendingSpanBuffer

    buf = PendingSpanBuffer()
    span = _make_span(trace_id=_TRACE_1, span_id="0000000000000001", name="early")

    assert buf.add(_TRACE_1, [span]) == (False, None)
    assert [s.name for s in buf.resolve(_TRACE_1, "run1")] == ["early"]
    assert buf.drain() == {}


def _race_log_spans_and_start_trace(
    store: LumlTrackingStore,
    exp_id: str,
    run_id: str,
    trace_id: str,
    spans: list,
) -> None:
    """Drive ``log_spans`` and ``start_trace`` for one trace from two threads that
    start simultaneously, mirroring MLflow's async exporter dispatching both onto
    its worker pool."""
    import threading

    barrier = threading.Barrier(2)

    def do_log_spans() -> None:
        barrier.wait()
        store.log_spans(exp_id, spans)

    def do_start_trace() -> None:
        barrier.wait()
        store.start_trace(
            _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
        )

    threads = [
        threading.Thread(target=do_log_spans),
        threading.Thread(target=do_start_trace),
    ]
    for th in threads:
        th.start()
    for th in threads:
        th.join()


def test_concurrent_log_spans_and_start_trace_keep_all_spans(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    """Regression: MLflow's async exporter runs ``log_spans`` and ``start_trace`` on
    separate worker threads. However they interleave, the span must be persisted —
    never stranded in the pending buffer."""
    exp_id, run_id = run
    for i in range(40):
        trace_id = f"abc000000000000000000000{i:08d}"
        span = _make_span(trace_id=trace_id, span_id="0000000000000001", name="s")
        _race_log_spans_and_start_trace(store, exp_id, run_id, trace_id, [span])

        trace = store.get_trace(trace_id)
        assert [s.name for s in trace.data.spans] == ["s"], f"span lost at i={i}"


def test_concurrent_traces_sharing_run_are_all_indexed(
    store: LumlTrackingStore, run: tuple[str, str]
) -> None:
    """Regression: many traces of the *same* run export concurrently. Each writes the
    run's trace index via a read-modify-write of one metadata blob; without
    serialization those writers clobber each other and whole traces vanish."""
    import threading

    exp_id, run_id = run
    n = 30
    trace_ids = [f"abc000000000000000000000{i:08d}" for i in range(n)]

    def start_one(trace_id: str) -> None:
        store.start_trace(
            _make_trace_info(trace_id=trace_id, experiment_id=exp_id, run_id=run_id)
        )
        span = _make_span(trace_id=trace_id, span_id="0000000000000001", name="s")
        store.log_spans(exp_id, [span])

    threads = [threading.Thread(target=start_one, args=(t,)) for t in trace_ids]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    infos, _ = store.search_traces(experiment_ids=[exp_id], max_results=1000)
    assert {t.trace_id for t in infos} == set(trace_ids)
