import uuid

from tests.support import FIXED_NOW, ago

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.query_store import (
    EventStatus,
    InferenceEvent,
    InMemoryMonitoringStore,
    SpanRecord,
    StoredAlert,
)
from agent.schemas.monitoring_query import SectionState, Severity, SeverityFilter, Window


def _service(store: InMemoryMonitoringStore) -> MonitoringQueryService:
    return MonitoringQueryService(store, clock=lambda: FIXED_NOW)


def _dims() -> QueryDimensions:
    return QueryDimensions(window=Window.H24)


def _alerts_store(dep: uuid.UUID) -> InMemoryMonitoringStore:
    store = InMemoryMonitoringStore()
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="feature_drift",
            metric="psi",
            feature="income",
            severity=Severity.CRITICAL,
            current_value=0.31,
            threshold=0.25,
            first_seen=ago(3600),
            last_seen=ago(90),
        )
    )
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="runtime",
            metric="error_rate",
            severity=Severity.CRITICAL,
            current_value=0.44,
            threshold=0.1,
            last_seen=ago(60),
        )
    )
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="data_quality",
            metric="missing_rate",
            feature="age",
            severity=Severity.WARNING,
            current_value=0.2,
            threshold=0.05,
            last_seen=ago(120),
        )
    )
    return store


async def test_alerts_grouped_by_metric_group_in_canonical_order() -> None:
    dep = uuid.uuid4()
    result = await _service(_alerts_store(dep)).alerts(dep, _dims())

    assert result.state is SectionState.OK
    assert [g.group for g in result.groups] == ["runtime", "data_quality", "feature_drift"]
    groups = {g.group: g for g in result.groups}
    assert groups["runtime"].alerts[0].metric == "error_rate"
    assert groups["runtime"].alerts[0].current_value == 0.44
    assert groups["runtime"].alerts[0].threshold == 0.1
    assert groups["feature_drift"].alerts[0].feature == "income"
    assert groups["data_quality"].alerts[0].severity is Severity.WARNING


async def test_alerts_severity_filter_narrows_to_critical() -> None:
    dep = uuid.uuid4()
    svc = _service(_alerts_store(dep))

    critical = await svc.alerts(dep, QueryDimensions(severity=SeverityFilter.CRITICAL))

    assert [g.group for g in critical.groups] == ["runtime", "feature_drift"]  # warning dropped
    assert all(a.severity is Severity.CRITICAL for g in critical.groups for a in g.alerts)


async def test_alerts_excludes_resolved_alerts() -> None:
    dep = uuid.uuid4()
    store = _alerts_store(dep)
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="runtime",
            metric="latency_p95",
            severity=Severity.WARNING,
            state="resolved",
            last_seen=ago(30),
        )
    )

    result = await _service(store).alerts(dep, _dims())

    runtime_metrics = [a.metric for g in result.groups if g.group == "runtime" for a in g.alerts]
    assert runtime_metrics == ["error_rate"]  # only the open alert, resolved one excluded


async def test_alerts_empty_when_none_open_is_ok_not_missing() -> None:
    dep = uuid.uuid4()
    result = await _service(InMemoryMonitoringStore()).alerts(dep, _dims())

    assert result.state is SectionState.OK  # no open alerts is a healthy answer, not "not computed"
    assert result.groups == []


async def test_alerts_scoped_to_deployment() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = _alerts_store(dep_a)  # only dep_a has alerts

    svc = _service(store)
    assert len((await svc.alerts(dep_a, _dims())).groups) == 3
    assert (await svc.alerts(dep_b, _dims())).groups == []


async def test_alerts_store_unavailable_yields_unavailable_state() -> None:
    dep = uuid.uuid4()
    store = _alerts_store(dep)
    store.unavailable = True

    result = await _service(store).alerts(dep, _dims())

    assert result.state is SectionState.UNAVAILABLE


def _trace_event(
    dep: uuid.UUID,
    offset_s: float,
    *,
    status: EventStatus = EventStatus.SUCCESS,
    latency: float = 10.0,
    inputs: str | None = None,
    output: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> InferenceEvent:
    return InferenceEvent(
        event_id=f"evt-{int(offset_s)}",
        deployment_id=dep,
        ts=ago(offset_s),
        status=status,
        status_code=200 if status is EventStatus.SUCCESS else 500,
        latency_ms=latency,
        trace_id=trace_id,
        span_id=span_id,
        inputs=inputs,
        output=output,
    )


def _span(
    span_id: str,
    trace_id: str,
    name: str,
    *,
    start: int,
    end: int,
    parent: str | None = None,
) -> SpanRecord:
    return SpanRecord(
        span_id=span_id,
        trace_id=trace_id,
        parent_span_id=parent,
        name=name,
        kind=1,
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        status_code=1,
    )


async def test_traces_returns_recent_calls_most_recent_first() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 300))
    store.add_event(_trace_event(dep, 100))  # most recent
    store.add_event(_trace_event(dep, 200))

    result = await _service(store).traces(dep, _dims())

    assert result.state is SectionState.OK
    assert result.total == 3
    assert [r.event_id for r in result.rows] == ["evt-100", "evt-200", "evt-300"]


async def test_traces_summarize_features_and_prediction() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(
        _trace_event(
            dep,
            100,
            inputs='{"age": 30, "income": 52000}',
            output='{"prediction": 0.87}',
        )
    )

    row = (await _service(store).traces(dep, _dims())).rows[0]

    assert row.features_summary is not None
    assert "age=30" in row.features_summary
    assert "income=52000" in row.features_summary
    assert row.prediction is not None
    assert "0.87" in row.prediction
    assert row.latency_ms == 10.0
    assert row.status == "success"


async def test_traces_paginate_with_limit_and_offset() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for i in range(1, 6):  # offsets 100..500 (500 is the oldest)
        store.add_event(_trace_event(dep, 100 * i))

    svc = _service(store)
    page1 = await svc.traces(dep, _dims(), limit=2, offset=0)
    page2 = await svc.traces(dep, _dims(), limit=2, offset=2)

    assert page1.total == 5 and page2.total == 5
    assert [r.event_id for r in page1.rows] == ["evt-100", "evt-200"]
    assert [r.event_id for r in page2.rows] == ["evt-300", "evt-400"]
    assert page1.limit == 2 and page1.offset == 0
    assert page2.offset == 2


async def test_traces_offset_beyond_total_is_ok_with_no_rows() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100))

    result = await _service(store).traces(dep, _dims(), limit=10, offset=50)

    assert result.state is SectionState.OK  # data exists, just not on this page
    assert result.rows == []
    assert result.total == 1


async def test_traces_respects_window() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100))  # inside 24h
    store.add_event(_trace_event(dep, 25 * 3600))  # outside 24h, inside 7d

    svc = _service(store)
    assert (await svc.traces(dep, QueryDimensions(window=Window.H24))).total == 1
    assert (await svc.traces(dep, QueryDimensions(window=Window.D7))).total == 2


async def test_traces_empty_shape_when_no_events() -> None:
    dep = uuid.uuid4()
    result = await _service(InMemoryMonitoringStore()).traces(dep, _dims())

    assert result.state is SectionState.EMPTY
    assert result.rows == []
    assert result.total == 0


async def test_trace_detail_returns_full_payloads_not_summaries() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(
        _trace_event(
            dep,
            100,
            inputs='{"sepal.length": [[6.82]], "sepal.width": [[4.12]]}',
            output='{"y_pred": ["Virginica"]}',
        )
    )

    result = await _service(store).trace_detail(dep, _dims(), "evt-100")

    assert result.state is SectionState.OK
    assert result.trace is not None
    # decoded JSON, so the UI can pretty-print it — not the truncated table summary
    assert result.trace.inputs == {"sepal.length": [[6.82]], "sepal.width": [[4.12]]}
    assert result.trace.output == {"y_pred": ["Virginica"]}
    assert result.trace.latency_ms == 10.0
    assert result.trace.status_code == 200


async def test_trace_detail_keeps_non_json_payload_as_text() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100, inputs="not json at all"))

    result = await _service(store).trace_detail(dep, _dims(), "evt-100")

    assert result.trace is not None
    assert result.trace.inputs == "not json at all"
    assert result.trace.output is None


async def test_trace_detail_missing_event_is_empty() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100))

    result = await _service(store).trace_detail(dep, _dims(), "evt-does-not-exist")

    assert result.state is SectionState.EMPTY
    assert result.trace is None


async def test_trace_detail_returns_every_span_of_the_trace() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100, trace_id="trc-1", span_id="root"))
    store.add_span(_span("root", "trc-1", "inference", start=0, end=36_000_000))
    store.add_span(
        _span("child", "trc-1", "model.execute", start=1_000_000, end=2_000_000, parent="root")
    )
    store.add_span(_span("other", "trc-2", "inference", start=0, end=1))  # different trace

    result = await _service(store).trace_detail(dep, _dims(), "evt-100")

    assert result.trace is not None
    spans = result.trace.spans
    assert [s.name for s in spans] == ["inference", "model.execute"]
    assert spans[0].parent_span_id is None
    assert spans[1].parent_span_id == "root"  # the client builds the tree from this
    assert spans[1].end_time_unix_nano - spans[1].start_time_unix_nano == 1_000_000


async def test_trace_detail_attaches_payloads_to_the_root_span_only() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(
        _trace_event(dep, 100, trace_id="trc-1", span_id="root", inputs='{"a": 1}', output='{"b": 2}')
    )
    store.add_span(_span("root", "trc-1", "inference", start=0, end=10))
    store.add_span(_span("child", "trc-1", "model.execute", start=1, end=2, parent="root"))

    spans = (await _service(store).trace_detail(dep, _dims(), "evt-100")).trace.spans

    # the collector keeps payloads on the event, not the raw span
    assert spans[0].attributes["inference.inputs"] == {"a": 1}
    assert spans[0].attributes["inference.output"] == {"b": 2}
    assert "inference.inputs" not in spans[1].attributes


async def test_trace_detail_synthesizes_one_span_when_none_were_collected() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100, latency=25.0))  # no spans stored

    spans = (await _service(store).trace_detail(dep, _dims(), "evt-100")).trace.spans

    assert len(spans) == 1
    assert spans[0].name == "inference"
    assert spans[0].parent_span_id is None
    assert spans[0].end_time_unix_nano - spans[0].start_time_unix_nano == 25_000_000


async def test_traces_only_show_the_sessions_deployment() -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(mine, 100))
    store.add_event(_trace_event(other, 200))
    store.add_event(_trace_event(other, 300))

    result = await _service(store).traces(mine, _dims())

    assert result.total == 1
    assert [r.event_id for r in result.rows] == ["evt-100"]


async def test_trace_detail_cannot_open_another_deployments_call() -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(other, 200, inputs='{"secret": "other tenant"}'))

    # event_ids are guessable, so scoping must come from the session's deployment_id
    result = await _service(store).trace_detail(mine, _dims(), "evt-200")

    assert result.state is SectionState.EMPTY
    assert result.trace is None


async def test_trace_detail_scoped_to_window() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 25 * 3600))  # outside 24h, inside 7d

    svc = _service(store)
    outside = await svc.trace_detail(dep, QueryDimensions(window=Window.H24), "evt-90000")
    inside = await svc.trace_detail(dep, QueryDimensions(window=Window.D7), "evt-90000")

    assert outside.state is SectionState.EMPTY
    assert inside.state is SectionState.OK


async def test_traces_scoped_to_deployment() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    for _ in range(3):
        store.add_event(_trace_event(dep_a, 100))
    for _ in range(7):
        store.add_event(_trace_event(dep_b, 100))

    svc = _service(store)
    assert (await svc.traces(dep_a, _dims())).total == 3
    assert (await svc.traces(dep_b, _dims())).total == 7


async def test_traces_store_unavailable_yields_unavailable_state() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_trace_event(dep, 100))
    store.unavailable = True

    result = await _service(store).traces(dep, _dims())

    assert result.state is SectionState.UNAVAILABLE
