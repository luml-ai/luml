import uuid

import pytest
from tests.support import FIXED_NOW, ago, now_dt

from agent.monitoring import (
    DeploymentDescriptor,
    EventStatus,
    InferenceEvent,
    InMemoryMonitoringStore,
    MonitoringQueryService,
    QueryDimensions,
    StoredAlert,
    StoredMetricResult,
)
from agent.schemas.monitoring_query import (
    Compare,
    ProfileStatus,
    SectionState,
    Severity,
    SeverityFilter,
    Window,
)


def _service(store: InMemoryMonitoringStore) -> MonitoringQueryService:
    return MonitoringQueryService(store, clock=lambda: FIXED_NOW)


def _event(
    deployment_id: uuid.UUID,
    offset_s: float,
    *,
    status: EventStatus = EventStatus.SUCCESS,
    latency: float = 10.0,
    inputs: str | None = None,
) -> InferenceEvent:
    return InferenceEvent(
        event_id=str(uuid.uuid4()),
        deployment_id=deployment_id,
        ts=ago(offset_s),
        status=status,
        status_code=200 if status is EventStatus.SUCCESS else 500,
        latency_ms=latency,
        inputs=inputs,
    )


def _mixed_events(deployment_id: uuid.UUID) -> list[InferenceEvent]:
    latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    statuses = [EventStatus.SUCCESS] * 5 + [
        EventStatus.ERROR,
        EventStatus.ERROR,
        EventStatus.TIMEOUT,
        EventStatus.FAILED_INFERENCE,
    ]
    return [
        _event(deployment_id, offset_s=100 + 50 * i, status=status, latency=latency)
        for i, (status, latency) in enumerate(zip(statuses, latencies, strict=True))
    ]


async def test_runtime_rollup_aggregates_counts_and_latency() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):
        store.add_event(event)

    result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.OK
    assert result.request_count == 9
    assert result.success_count == 5
    assert result.error_count == 2
    assert result.timeout_count == 1
    assert result.failed_inference_count == 1
    assert result.error_rate == pytest.approx(4 / 9)
    assert result.latency_p50_ms == 50
    assert result.latency_p95_ms == 90
    assert result.latency_max_ms == 90


async def test_runtime_series_covers_the_whole_window() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):
        store.add_event(event)

    result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

    requests = next(s for s in result.series if s.key == "requests")
    assert len(requests.points) == 24  # 24h at auto (hourly) granularity
    assert sum(p.value for p in requests.points) == result.request_count


async def test_window_dimension_changes_the_query() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):  # 9 events inside 24h
        store.add_event(event)
    store.add_event(_event(dep, offset_s=25 * 3600))  # older than 24h, inside 7d

    svc = _service(store)
    day = await svc.runtime(dep, QueryDimensions(window=Window.H24))
    week = await svc.runtime(dep, QueryDimensions(window=Window.D7))

    assert day.request_count == 9
    assert week.request_count == 10


async def test_compare_previous_populates_delta_reference_leaves_it_none() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):  # 9 in current 24h
        store.add_event(event)
    for _ in range(3):  # 3 in the preceding 24h window
        store.add_event(_event(dep, offset_s=30 * 3600))

    svc = _service(store)
    previous = await svc.overview(dep, QueryDimensions(window=Window.H24, compare=Compare.PREVIOUS))
    reference = await svc.overview(
        dep, QueryDimensions(window=Window.H24, compare=Compare.REFERENCE)
    )

    prev_requests = next(c for c in previous.cards if c.key == "requests")
    ref_requests = next(c for c in reference.cards if c.key == "requests")
    assert prev_requests.delta == 6  # 9 current - 3 previous
    assert prev_requests.delta_kind is Compare.PREVIOUS
    assert ref_requests.delta is None


async def test_runtime_never_leaks_raw_inference_io() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_event(_event(dep, offset_s=100, inputs='{"ssn": "SECRET-RAW-ROW"}'))

    result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

    assert "SECRET-RAW-ROW" not in result.model_dump_json()


def _overview_store(dep: uuid.UUID) -> InMemoryMonitoringStore:
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):
        store.add_event(event)
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
            feature="income",
            severity=Severity.WARNING,
            last_seen=ago(120),
        )
    )
    store.add_result(
        StoredMetricResult(
            deployment_id=dep,
            group="feature_drift",
            window=Window.H24.value,
            values={
                "features": {
                    "income": {"psi": 0.3, "status": "critical"},
                    "age": {"psi": 0.1, "status": "ok"},
                }
            },
            severity="critical",
        )
    )
    return store


async def test_overview_cards_summarize_runtime_alerts_and_drift() -> None:
    dep = uuid.uuid4()
    result = await _service(_overview_store(dep)).overview(dep, QueryDimensions(window=Window.H24))

    cards = {c.key: c for c in result.cards}
    assert cards["requests"].value == 9
    assert cards["error_rate"].value == pytest.approx(4 / 9)
    assert cards["latency_p95"].value == 90
    assert cards["active_alerts"].value == 2
    assert cards["active_alerts"].critical_count == 1
    assert cards["drifted_features"].value == 1
    assert cards["drifted_features"].feature_names == ["income"]


async def test_overview_top_drifted_features_ranked_by_psi() -> None:
    dep = uuid.uuid4()
    result = await _service(_overview_store(dep)).overview(dep, QueryDimensions(window=Window.H24))

    assert [d.feature for d in result.top_drifted_features] == ["income", "age"]
    assert result.top_drifted_features[0].psi == 0.3


async def test_severity_filter_narrows_alerts() -> None:
    dep = uuid.uuid4()
    svc = _service(_overview_store(dep))

    all_alerts = await svc.overview(dep, QueryDimensions(severity=SeverityFilter.ALL))
    critical_only = await svc.overview(dep, QueryDimensions(severity=SeverityFilter.CRITICAL))

    assert len(all_alerts.alert_banners) == 2
    assert all_alerts.alert_banners[0].severity is Severity.CRITICAL  # critical sorted first
    assert len(critical_only.alert_banners) == 1
    assert critical_only.alert_banners[0].severity is Severity.CRITICAL
    active_card = next(c for c in critical_only.cards if c.key == "active_alerts")
    assert active_card.value == 1


async def test_runtime_alerts_scoped_to_runtime_group() -> None:
    dep = uuid.uuid4()
    result = await _service(_overview_store(dep)).runtime(dep, QueryDimensions(window=Window.H24))

    assert [a.group for a in result.alerts] == ["runtime"]


def _data_quality_store(dep: uuid.UUID) -> InMemoryMonitoringStore:
    store = InMemoryMonitoringStore()
    store.add_result(
        StoredMetricResult(
            deployment_id=dep,
            group="data_quality",
            window=Window.H24.value,
            values={
                "features": {
                    "age": {
                        "missing_rate": 0.01,
                        "type_error_rate": 0.0,
                        "range_unseen_rate": 0.02,
                        "status": "ok",
                    },
                    "income": {
                        "missing_rate": 0.2,
                        "type_error_rate": 0.05,
                        "range_unseen_rate": 0.1,
                        "status": "critical",
                    },
                }
            },
            severity="critical",
        )
    )
    return store


async def test_data_quality_table_from_result_group() -> None:
    dep = uuid.uuid4()
    svc = _service(_data_quality_store(dep))
    result = await svc.data_quality(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.OK
    rows = {r.feature: r for r in result.features}
    assert rows["income"].missing_rate == 0.2
    assert rows["income"].range_unseen_rate == 0.1
    assert rows["income"].status is Severity.CRITICAL
    assert rows["age"].status is Severity.OK


async def test_feature_filter_narrows_data_quality() -> None:
    dep = uuid.uuid4()
    dims = QueryDimensions(window=Window.H24, feature="income")
    result = await _service(_data_quality_store(dep)).data_quality(dep, dims)

    assert [r.feature for r in result.features] == ["income"]


async def test_data_quality_empty_shape_when_not_computed() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()  # worker has produced nothing for this window

    result = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.EMPTY
    assert result.features == []


async def test_placeholder_profile_status_is_carried() -> None:
    dep = uuid.uuid4()
    store = _data_quality_store(dep)
    store.set_profile_status(dep, "placeholder")

    result = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))

    assert result.profile_status is ProfileStatus.PLACEHOLDER


async def test_header_reports_context_and_timestamps() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_deployment(
        DeploymentDescriptor(
            deployment_id=dep,
            name="fraud-model",
            status="active",
            task_type="classification",
            model_name="xgb-v3",
            environment="prod-orbit",
            satellite="edge-1",
            inference_url="https://sat.example/infer",
        )
    )
    store.add_event(_event(dep, offset_s=100))
    store.add_result(
        StoredMetricResult(
            deployment_id=dep,
            group="runtime",
            window=Window.H24.value,
            values={},
            severity="ok",
            computed_at=ago(3600),
        )
    )

    header = await _service(store).header(dep)

    assert header.state is SectionState.OK
    assert header.name == "fraud-model"
    assert header.task_type == "classification"
    assert header.satellite == "edge-1"
    assert header.last_prediction_at == ago(100)
    assert header.last_monitored_at == ago(3600)
    assert header.profile_status is ProfileStatus.READY


async def test_missing_descriptor_yields_empty_header() -> None:
    dep = uuid.uuid4()
    header = await _service(InMemoryMonitoringStore()).header(dep)

    assert header.state is SectionState.EMPTY
    assert header.deployment_id == dep


async def test_store_unavailable_yields_unavailable_state_not_crash() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.unavailable = True
    svc = _service(store)
    dims = QueryDimensions(window=Window.H24)

    assert (await svc.header(dep)).state is SectionState.UNAVAILABLE
    assert (await svc.overview(dep, dims)).state is SectionState.UNAVAILABLE
    assert (await svc.runtime(dep, dims)).state is SectionState.UNAVAILABLE
    assert (await svc.data_quality(dep, dims)).state is SectionState.UNAVAILABLE


async def test_deployment_scope_isolates_data() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = InMemoryMonitoringStore()
    for _ in range(3):
        store.add_event(_event(dep_a, offset_s=100))
    for _ in range(7):
        store.add_event(_event(dep_b, offset_s=100))

    svc = _service(store)
    dims = QueryDimensions(window=Window.H24)
    assert (await svc.runtime(dep_a, dims)).request_count == 3
    assert (await svc.runtime(dep_b, dims)).request_count == 7


def test_fixed_clock_anchors_window_to_now() -> None:
    # guards the helper contract the other tests lean on
    assert now_dt().timestamp() == FIXED_NOW
