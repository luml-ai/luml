import uuid

from tests.support import FIXED_NOW, ago

from agent.monitoring import (
    EventStatus,
    InferenceEvent,
    InMemoryMonitoringStore,
    MonitoringQueryService,
    QueryDimensions,
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
) -> InferenceEvent:
    return InferenceEvent(
        event_id=f"evt-{int(offset_s)}",
        deployment_id=dep,
        ts=ago(offset_s),
        status=status,
        status_code=200 if status is EventStatus.SUCCESS else 500,
        latency_ms=latency,
        inputs=inputs,
        output=output,
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
