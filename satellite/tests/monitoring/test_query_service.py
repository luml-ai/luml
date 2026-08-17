import uuid

import pytest
from tests.support import FIXED_NOW, ago, now_dt

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.query_store import (
    DeploymentDescriptor,
    EventStatus,
    InferenceEvent,
    InMemoryMonitoringStore,
    StoredAlert,
    StoredMetricResult,
)
from agent.schemas.monitoring_query import (
    Compare,
    Granularity,
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


async def test_series_zooms_to_a_short_burst_of_traffic() -> None:
    """Nine calls inside seven minutes used to land in one window-sized bucket: a single
    point, which a line chart draws as nothing. The layout follows the data instead."""
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):  # ~400 seconds of traffic
        store.add_event(event)

    result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

    requests = next(s for s in result.series if s.key == "requests")
    latency = next(s for s in result.series if s.key == "latency_p95")
    spacing = (requests.points[1].t - requests.points[0].t).total_seconds()

    assert spacing == 30  # smallest ladder step for a ~7-minute span
    assert len(requests.points) == 14
    assert sum(p.value for p in requests.points) == result.request_count
    assert len([p for p in latency.points if p.value is not None]) > 1


async def test_series_keeps_the_window_layout_when_traffic_spans_it() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for hours in range(0, 24, 2):  # traffic across the whole 24h window
        store.add_event(_event(dep, offset_s=hours * 3600, latency=120.0))

    result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

    requests = next(s for s in result.series if s.key == "requests")
    assert len(requests.points) == 96  # 24h at auto (15-minute) granularity
    assert sum(p.value for p in requests.points) == result.request_count


async def test_explicit_granularity_is_never_overridden_by_the_zoom() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for event in _mixed_events(dep):
        store.add_event(event)

    result = await _service(store).runtime(
        dep, QueryDimensions(window=Window.H24, granularity=Granularity.HOUR)
    )

    requests = next(s for s in result.series if s.key == "requests")
    assert len(requests.points) == 24
    assert sum(p.value for p in requests.points) == result.request_count


async def test_bursty_traffic_yields_several_latency_points() -> None:
    """Hourly buckets collapsed a burst into a single point, and one point draws no line —
    the latency chart read as empty while the rollup card showed a value."""
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for offset in (60, 20 * 60, 40 * 60, 80 * 60):  # spread over ~80 minutes
        store.add_event(_event(dep, offset_s=offset, latency=120.0))

    result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

    latency = next(s for s in result.series if s.key == "latency_p95")
    assert len([p for p in latency.points if p.value is not None]) == 4


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


async def test_overview_keeps_the_ten_most_drifted_features() -> None:
    """Models here carry a couple of dozen inputs; five names were too few to see where the
    drift sits, so the card ranks ten."""
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_result(
        StoredMetricResult(
            deployment_id=dep,
            group="feature_drift",
            window=Window.H24.value,
            values={
                "features": {
                    f"f{i:02d}": {"psi": 0.5 - i / 100, "status": "critical"} for i in range(15)
                }
            },
            severity="critical",
        )
    )

    result = await _service(store).overview(dep, QueryDimensions(window=Window.H24))

    assert len(result.top_drifted_features) == 10
    assert [d.feature for d in result.top_drifted_features] == [f"f{i:02d}" for i in range(10)]


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
                    # keys exactly as the data-quality metric writes them
                    "age": {
                        "count": 100,
                        "missing_rate": 0.01,
                        "type_mismatch_rate": 0.0,
                        "range_violation_rate": 0.02,
                        "status": "ok",
                    },
                    "income": {
                        "kind": "numeric",
                        "count": 100,
                        "missing_rate": 0.2,
                        "type_mismatch_rate": 0.05,
                        "range_violation_rate": 0.1,
                        "status": "critical",
                        "invalid": {
                            "missing": {"count": 20},
                            "type_mismatch": {
                                "count": 5,
                                "types": {"str": 5},
                                "examples": ["'n/a'"],
                            },
                            "range_violation": {
                                "count": 10,
                                "below_min": 2,
                                "above_max": 8,
                                "observed_min": -400.0,
                                "observed_max": 980000.0,
                                "reference_min": 0.0,
                                "reference_max": 250000.0,
                            },
                        },
                    },
                    "plan": {
                        "kind": "categorical",
                        "count": 100,
                        "missing_rate": 0.0,
                        "type_mismatch_rate": 0.0,
                        "unseen_category_rate": 0.3,
                        "status": "critical",
                        "invalid": {
                            "unseen_category": {
                                "count": 30,
                                "distinct": 2,
                                "reference_categories": 4,
                                "values": [
                                    {"value": "enterprise", "count": 25},
                                    {"value": "trial", "count": 5},
                                ],
                            },
                        },
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
    assert rows["income"].type_error_rate == 0.05
    assert rows["income"].range_unseen_rate == 0.1
    assert rows["income"].range_violation_rate == 0.1
    assert rows["income"].checked == 100
    assert rows["income"].status is Severity.CRITICAL
    assert rows["age"].status is Severity.OK
    # a categorical feature reports unseen categories in the same column
    assert rows["plan"].range_unseen_rate == 0.3
    assert rows["plan"].unseen_category_rate == 0.3


async def test_data_quality_rows_carry_the_invalid_value_evidence() -> None:
    dep = uuid.uuid4()
    svc = _service(_data_quality_store(dep))
    result = await svc.data_quality(dep, QueryDimensions(window=Window.H24))

    rows = {r.feature: r for r in result.features}
    income = rows["income"].invalid
    assert income is not None
    assert (income.missing_count, income.type_mismatch_count) == (20, 5)
    assert income.observed_types == {"str": 5}
    assert (income.below_min, income.above_max) == (2, 8)
    assert (income.observed_max, income.reference_max) == (980000.0, 250000.0)

    plan = rows["plan"].invalid
    assert plan is not None
    assert plan.unseen_distinct == 2
    assert plan.reference_categories == 4
    assert [(c.value, c.count) for c in plan.unseen_categories] == [
        ("enterprise", 25),
        ("trial", 5),
    ]
    assert rows["plan"].kind == "categorical"
    # a clean feature has nothing to explain
    assert rows["age"].invalid is None


def _quality_window(
    dep: uuid.UUID, *, missing: float, unseen: float, seconds_ago: float
) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="data_quality",
        window=Window.H24.value,
        values={
            "features": {
                "plan": {
                    "kind": "categorical",
                    "count": 100,
                    "missing_rate": missing,
                    "type_mismatch_rate": 0.0,
                    "unseen_category_rate": unseen,
                    "status": "warning",
                }
            }
        },
        severity="warning",
        computed_at=ago(seconds_ago),
    )


async def test_data_quality_trends_come_from_past_windows() -> None:
    """The spec asks for a trend per check; the worker stores one window at a time."""
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    for missing, unseen, ago_seconds in ((0.0, 0.0, 3 * 3600), (0.01, 0.2, 2 * 3600)):
        store.add_result(
            _quality_window(dep, missing=missing, unseen=unseen, seconds_ago=ago_seconds)
        )

    result = await _service(store).data_quality(
        dep, QueryDimensions(window=Window.H24, feature="plan")
    )

    trends = {series.key: series for series in result.trends}
    assert [series.key for series in result.trends] == [
        "missing",
        "type_mismatch",
        "unseen_category",
    ]
    assert [p.value for p in trends["unseen_category"].points] == [0.0, 0.2]
    assert trends["unseen_category"].label == "Unseen categories"
    assert trends["missing"].unit == "ratio"
    # a check that never applied to this feature has no series at all
    assert "range_violation" not in trends


async def test_data_quality_trends_need_a_selected_feature_and_two_windows() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_result(_quality_window(dep, missing=0.01, unseen=0.2, seconds_ago=600))

    whole_tab = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))
    assert whole_tab.trends == []

    one_window = await _service(store).data_quality(
        dep, QueryDimensions(window=Window.H24, feature="plan")
    )
    assert one_window.trends == []


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
