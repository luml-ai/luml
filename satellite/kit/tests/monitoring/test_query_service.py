import uuid
from datetime import datetime

import pytest

from luml_satellite.monitoring import MonitoringQueryService, QueryDimensions
from luml_satellite.monitoring.dashboard.schemas import (
    Compare,
    Granularity,
    ProfileStatus,
    SectionState,
    Severity,
    SeverityFilter,
    Window,
)
from luml_satellite.monitoring.storage.query_store import (
    DeploymentDescriptor,
    EventStatus,
    InferenceEvent,
    InMemoryMonitoringStore,
    StoredAlert,
    StoredMetricResult,
)
from tests.support import FIXED_NOW, ago, now_dt


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


def _dq_result(dep: uuid.UUID, computed_at: datetime | None) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="data_quality",
        window=Window.H24.value,
        values={"features": {"income": {"missing_rate": 0.0, "checked": 10}}},
        severity="ok",
        computed_at=computed_at,
    )


def _output_result(
    dep: uuid.UUID, *, at: datetime | None = None, psi: float = 0.42
) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="output_drift",
        window=Window.H24.value,
        values={
            "psi": psi,
            "count": 120,
            "name": "y_pred",
            "kind": "numeric",
            "status": "critical",
            "trend": {"mean": 12.0, "median": 11.5, "p05": 8.0, "p95": 16.0},
            "distribution": {
                "kind": "numeric",
                "bins": [
                    {"label": "0–10", "reference": 0.5, "current": 0.2},
                    {"label": "10–20", "reference": 0.5, "current": 0.8},
                ],
            },
        },
        severity="critical",
        computed_at=at or ago(300),
    )


def _categorical_output_result(
    dep: uuid.UUID, *, at: datetime | None = None, setosa: float = 0.2
) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="output_drift",
        window=Window.H24.value,
        values={
            "psi": 0.3,
            "count": 90,
            "name": "y",
            "kind": "categorical",
            "status": "critical",
            "distribution": {
                "kind": "categorical",
                "bins": [
                    {"label": "setosa", "reference": 0.34, "current": setosa},
                    {"label": "virginica", "reference": 0.33, "current": 0.6},
                    {"label": "versicolor", "reference": 0.33, "current": 1 - 0.6 - setosa},
                ],
            },
        },
        severity="critical",
        computed_at=at or ago(300),
    )


class TestQueryService:
    async def test_runtime_rollup_aggregates_counts_and_latency(self) -> None:
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
        assert result.success_rate == pytest.approx(5 / 9)
        assert result.latency_p50_ms == 50
        assert result.latency_p95_ms == 90
        assert result.latency_max_ms == 90

    async def test_success_rate_of_an_empty_window_is_zero_not_perfect(self) -> None:
        """Nothing succeeded, so nothing is the answer — 100% would read as a healthy window."""
        dep = uuid.uuid4()

        result = await _service(InMemoryMonitoringStore()).runtime(
            dep, QueryDimensions(window=Window.H24)
        )

        assert result.request_count == 0
        assert result.success_rate == 0.0
        assert result.status_breakdown == []

    async def test_status_breakdown_groups_by_outcome_and_code(self) -> None:
        """A 504 and a 500 are both errors; the breakdown is what tells them apart."""
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for event in _mixed_events(dep):
            store.add_event(event)

        result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

        rows = {(row.status, row.status_code): row for row in result.status_breakdown}
        assert rows[("success", 200)].count == 5
        assert rows[("success", 200)].share == pytest.approx(5 / 9)
        assert rows[("error", 500)].count == 2
        assert rows[("timeout", 500)].count == 1
        assert rows[("failed_inference", 500)].count == 1
        # busiest first, so the table opens on what dominated the window
        assert result.status_breakdown[0].status == "success"
        assert sum(row.count for row in result.status_breakdown) == result.request_count

    async def test_series_zooms_to_a_short_burst_of_traffic(self) -> None:
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
        assert sum(p.value for p in requests.points if p.value is not None) == result.request_count
        assert len([p for p in latency.points if p.value is not None]) > 1

    async def test_series_keeps_the_window_layout_when_traffic_spans_it(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for hours in range(0, 24, 2):  # traffic across the whole 24h window
            store.add_event(_event(dep, offset_s=hours * 3600, latency=120.0))

        result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

        requests = next(s for s in result.series if s.key == "requests")
        assert len(requests.points) == 96  # 24h at auto (15-minute) granularity
        assert sum(p.value for p in requests.points if p.value is not None) == result.request_count

    async def test_explicit_granularity_is_never_overridden_by_the_zoom(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for event in _mixed_events(dep):
            store.add_event(event)

        result = await _service(store).runtime(
            dep, QueryDimensions(window=Window.H24, granularity=Granularity.HOUR)
        )

        requests = next(s for s in result.series if s.key == "requests")
        assert len(requests.points) == 24
        assert sum(p.value for p in requests.points if p.value is not None) == result.request_count

    async def test_bursty_traffic_yields_several_latency_points(self) -> None:
        """Hourly buckets collapsed a burst into a single point, and one point draws no line —
        the latency chart read as empty while the rollup card showed a value."""
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for offset in (60, 20 * 60, 40 * 60, 80 * 60):  # spread over ~80 minutes
            store.add_event(_event(dep, offset_s=offset, latency=120.0))

        result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

        latency = next(s for s in result.series if s.key == "latency_p95")
        assert len([p for p in latency.points if p.value is not None]) == 4

    async def test_window_dimension_changes_the_query(self) -> None:
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

    async def test_compare_previous_populates_delta_reference_leaves_it_none(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for event in _mixed_events(dep):  # 9 in current 24h
            store.add_event(event)
        for _ in range(3):  # 3 in the preceding 24h window
            store.add_event(_event(dep, offset_s=30 * 3600))

        svc = _service(store)
        previous = await svc.overview(
            dep, QueryDimensions(window=Window.H24, compare=Compare.PREVIOUS)
        )
        reference = await svc.overview(
            dep, QueryDimensions(window=Window.H24, compare=Compare.REFERENCE)
        )

        prev_requests = next(c for c in previous.cards if c.key == "requests")
        ref_requests = next(c for c in reference.cards if c.key == "requests")
        assert prev_requests.delta == 6  # 9 current - 3 previous
        assert prev_requests.delta_kind is Compare.PREVIOUS
        assert ref_requests.delta is None

    async def test_runtime_never_leaks_raw_inference_io(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_event(_event(dep, offset_s=100, inputs='{"ssn": "SECRET-RAW-ROW"}'))

        result = await _service(store).runtime(dep, QueryDimensions(window=Window.H24))

        assert "SECRET-RAW-ROW" not in result.model_dump_json()

    async def test_overview_cards_summarize_runtime_alerts_and_drift(self) -> None:
        dep = uuid.uuid4()
        result = await _service(_overview_store(dep)).overview(
            dep, QueryDimensions(window=Window.H24)
        )

        cards = {c.key: c for c in result.cards}
        assert cards["requests"].value == 9
        assert cards["error_rate"].value == pytest.approx(4 / 9)
        assert cards["latency_p95"].value == 90
        assert cards["active_alerts"].value == 2
        assert cards["active_alerts"].critical_count == 1
        assert cards["drifted_features"].value == 1
        assert cards["drifted_features"].feature_names == ["income"]

    async def test_overview_top_drifted_features_ranked_by_psi(self) -> None:
        dep = uuid.uuid4()
        result = await _service(_overview_store(dep)).overview(
            dep, QueryDimensions(window=Window.H24)
        )

        assert [d.feature for d in result.top_drifted_features] == ["income", "age"]
        assert result.top_drifted_features[0].psi == 0.3

    async def test_overview_keeps_the_ten_most_drifted_features(self) -> None:
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

    async def test_severity_filter_narrows_alerts(self) -> None:
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

    async def test_runtime_alerts_scoped_to_runtime_group(self) -> None:
        dep = uuid.uuid4()
        result = await _service(_overview_store(dep)).runtime(
            dep, QueryDimensions(window=Window.H24)
        )

        assert [a.group for a in result.alerts] == ["runtime"]

    async def test_data_quality_table_from_result_group(self) -> None:
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

    async def test_data_quality_rows_carry_the_invalid_value_evidence(self) -> None:
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

    async def test_data_quality_trends_come_from_past_windows(self) -> None:
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

    async def test_data_quality_trends_need_a_selected_feature_and_two_windows(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_quality_window(dep, missing=0.01, unseen=0.2, seconds_ago=600))

        whole_tab = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))
        assert whole_tab.trends == []

        one_window = await _service(store).data_quality(
            dep, QueryDimensions(window=Window.H24, feature="plan")
        )
        assert one_window.trends == []

    async def test_feature_filter_narrows_data_quality(self) -> None:
        dep = uuid.uuid4()
        dims = QueryDimensions(window=Window.H24, feature="income")
        result = await _service(_data_quality_store(dep)).data_quality(dep, dims)

        assert [r.feature for r in result.features] == ["income"]

    async def test_data_quality_empty_shape_when_not_computed(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()  # worker has produced nothing for this window

        result = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))

        assert result.state is SectionState.EMPTY
        assert result.features == []

    @pytest.mark.parametrize(
        "profile_status",
        [
            ProfileStatus.READY,
            ProfileStatus.PLACEHOLDER,
            ProfileStatus.ABSENT,
            ProfileStatus.UNSUPPORTED,
        ],
    )
    async def test_profile_status_is_carried_by_section_responses(
        self,
        profile_status: ProfileStatus,
    ) -> None:
        dep = uuid.uuid4()
        store = _data_quality_store(dep)
        store.set_profile_status(dep, profile_status)

        result = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))

        assert result.profile_status is profile_status

    async def test_unsupported_profile_status_is_carried_by_every_profile_aware_response(
        self,
    ) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.set_profile_status(dep, ProfileStatus.UNSUPPORTED)
        service = _service(store)
        dimensions = QueryDimensions(window=Window.H24)

        responses = (
            await service.header(dep),
            await service.overview(dep, dimensions),
            await service.runtime(dep, dimensions),
            await service.data_quality(dep, dimensions),
            await service.feature_drift(dep, dimensions),
            await service.output_drift(dep, dimensions),
            await service.reference_profile(dep, dimensions),
            await service.alerts(dep, dimensions),
            await service.traces(dep, dimensions),
            await service.trace_detail(dep, dimensions, "missing-event"),
        )

        assert all(response.profile_status is ProfileStatus.UNSUPPORTED for response in responses)

    async def test_header_reports_context_and_timestamps(self) -> None:
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
        assert header.profile_status is ProfileStatus.ABSENT

    async def test_missing_descriptor_yields_empty_header(self) -> None:
        dep = uuid.uuid4()
        header = await _service(InMemoryMonitoringStore()).header(dep)

        assert header.state is SectionState.EMPTY
        assert header.deployment_id == dep
        assert header.model_kind.value == "unknown"

    async def test_store_unavailable_yields_unavailable_state_not_crash(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.unavailable = True
        svc = _service(store)
        dims = QueryDimensions(window=Window.H24)

        assert (await svc.header(dep)).state is SectionState.UNAVAILABLE
        assert (await svc.overview(dep, dims)).state is SectionState.UNAVAILABLE
        assert (await svc.runtime(dep, dims)).state is SectionState.UNAVAILABLE
        assert (await svc.data_quality(dep, dims)).state is SectionState.UNAVAILABLE

    async def test_deployment_scope_isolates_data(self) -> None:
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

    def test_fixed_clock_anchors_window_to_now(self) -> None:
        # guards the helper contract the other tests lean on
        assert now_dt().timestamp() == FIXED_NOW

    async def test_snapshot_inside_the_range_is_not_marked_stale(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_dq_result(dep, ago(600)))

        result = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))

        assert result.state is SectionState.OK
        assert result.stale is False
        assert result.computed_at == ago(600)

    async def test_snapshot_older_than_the_range_is_still_served_but_marked_stale(self) -> None:
        """A stand idle for two days keeps its last reading — and has to say how old it is.

        The snapshot tabs read the newest stored window with no time bound, so without the
        flag a two-day-old window is indistinguishable from a live one.
        """
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_dq_result(dep, ago(2 * 24 * 3600)))

        service = _service(store)
        day = await service.data_quality(dep, QueryDimensions(window=Window.H24))

        assert day.state is SectionState.OK
        assert day.features  # the reading is served, not hidden
        assert day.stale is True

        # Widening the range brings the same window back inside it.
        week = await service.data_quality(dep, QueryDimensions(window=Window.D7))
        assert week.stale is False

    async def test_feature_drift_snapshot_reports_its_window_age(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(
            StoredMetricResult(
                deployment_id=dep,
                group="feature_drift",
                window=Window.H24.value,
                values={"features": {"income": {"psi": 0.3, "status": "critical"}}},
                severity="critical",
                computed_at=ago(3 * 24 * 3600),
            )
        )

        result = await _service(store).feature_drift(dep, QueryDimensions(window=Window.H24))

        assert result.state is SectionState.OK
        assert result.features
        assert result.stale is True
        assert result.computed_at == ago(3 * 24 * 3600)

    async def test_snapshot_without_a_timestamp_is_not_guessed_stale(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_dq_result(dep, None))

        result = await _service(store).data_quality(dep, QueryDimensions(window=Window.H24))

        assert result.stale is False
        assert result.computed_at is None

    async def test_output_drift_snapshot_reads_the_latest_window(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_output_result(dep))

        result = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        assert result.state is SectionState.OK
        assert result.name == "y_pred"
        assert result.kind == "numeric"
        assert result.psi == pytest.approx(0.42)
        assert result.severity is Severity.CRITICAL
        assert result.count == 120
        assert result.distribution is not None
        assert [b.label for b in result.distribution.bins] == ["0–10", "10–20"]
        assert result.stale is False

    async def test_output_drift_series_come_from_the_window_history(self) -> None:
        """PSI over time and the prediction band are assembled from materialized windows."""
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_output_result(dep, at=ago(600), psi=0.10))
        store.add_result(_output_result(dep, at=ago(300), psi=0.42))

        result = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        assert result.psi_over_time is not None
        assert [p.value for p in result.psi_over_time.points] == [
            pytest.approx(0.10),
            pytest.approx(0.42),
        ]
        keys = {series.key for series in result.trend}
        assert keys == {
            "prediction_median",
            "prediction_p05",
            "prediction_p95",
            "prediction_mean",
        }
        median = next(s for s in result.trend if s.key == "prediction_median")
        assert len(median.points) == 2

    async def test_output_drift_without_windows_is_empty_not_broken(self) -> None:
        dep = uuid.uuid4()

        result = await _service(InMemoryMonitoringStore()).output_drift(
            dep, QueryDimensions(window=Window.H24)
        )

        assert result.state is SectionState.EMPTY

    async def test_overview_carries_the_output_drift_card(self) -> None:
        """The spec puts an output drift summary on Overview; it rides as a scored card."""
        dep = uuid.uuid4()
        store = _overview_store(dep)
        store.add_result(_output_result(dep))

        result = await _service(store).overview(dep, QueryDimensions(window=Window.H24))

        card = next(c for c in result.cards if c.key == "output_drift")
        assert card.value == pytest.approx(0.42)
        assert card.severity is Severity.CRITICAL

    async def test_overview_without_output_windows_has_no_output_card(self) -> None:
        dep = uuid.uuid4()

        result = await _service(_overview_store(dep)).overview(
            dep, QueryDimensions(window=Window.H24)
        )

        assert all(card.key != "output_drift" for card in result.cards)

    async def test_classification_windows_rank_the_classes_that_moved(self) -> None:
        """The label-based adapter: which predicted classes drifted, by share delta."""
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_categorical_output_result(dep))

        result = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        assert result.kind == "categorical"
        assert [shift.label for shift in result.top_changed] == [
            "virginica",  # +0.27, the biggest move
            "setosa",  # -0.14
            "versicolor",  # -0.13
        ]
        assert result.top_changed[0].delta == pytest.approx(0.27)
        # a categorical output has no numeric band
        assert result.trend == []

    async def test_class_shares_are_assembled_across_windows(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_categorical_output_result(dep, at=ago(600), setosa=0.34))
        store.add_result(_categorical_output_result(dep, at=ago(300), setosa=0.2))

        result = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        setosa = next(s for s in result.class_share_trend if s.label == "setosa")
        assert [p.value for p in setosa.points] == [
            pytest.approx(0.34),
            pytest.approx(0.2),
        ]
        assert all(series.unit == "ratio" for series in result.class_share_trend)

    async def test_the_confidence_block_rides_with_its_mean_history(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        for offset, mean in ((600, 0.93), (300, 0.71)):
            stored_result = _categorical_output_result(dep, at=ago(offset))
            stored_result.values["confidence"] = {
                "psi": 0.4,
                "mean": mean,
                "low_confidence_rate": 0.3,
                "low_confidence_threshold": 0.88,
                "distribution": {
                    "kind": "numeric",
                    "bins": [{"label": "0.9–1", "reference": 0.7, "current": 0.2}],
                },
            }
            store.add_result(stored_result)

        served = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        confidence = served.confidence
        assert confidence is not None
        assert confidence.psi == pytest.approx(0.4)
        assert confidence.low_confidence_threshold == pytest.approx(0.88)
        assert confidence.mean_over_time is not None
        assert [p.value for p in confidence.mean_over_time.points] == [
            pytest.approx(0.93),
            pytest.approx(0.71),
        ]

    async def test_without_scores_the_confidence_block_is_absent(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(_categorical_output_result(dep))

        result = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        assert result.confidence is None

    async def test_probability_and_horizon_blocks_pass_through(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        result = _categorical_output_result(dep)
        result.values["probabilities"] = {
            "per_class": [{"label": "dog", "psi": 0.4, "mean": 0.6}],
            "near_threshold": {
                "rate": 0.5,
                "reference_rate": 0.02,
                "threshold": 0.5,
                "positive_class": "dog",
            },
        }
        store.add_result(result)

        served = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        assert served.probabilities is not None
        assert served.probabilities.per_class[0].label == "dog"
        assert served.probabilities.near_threshold is not None
        assert served.probabilities.near_threshold.rate == pytest.approx(0.5)

    async def test_forecast_horizons_pass_through(self) -> None:
        dep = uuid.uuid4()
        store = InMemoryMonitoringStore()
        store.add_result(
            StoredMetricResult(
                deployment_id=dep,
                group="output_drift",
                window=Window.H24.value,
                values={
                    "psi": 0.6,
                    "count": 40,
                    "name": "y[h7]",
                    "kind": "forecast",
                    "status": "critical",
                    "horizons": [
                        {"label": "h1", "psi": 0.05, "mean": 20.0, "count": 20},
                        {"label": "h7", "psi": 0.6, "mean": 37.0, "count": 20},
                    ],
                },
                severity="critical",
                computed_at=ago(300),
            )
        )

        served = await _service(store).output_drift(dep, QueryDimensions(window=Window.H24))

        assert served.kind == "forecast"
        assert [h.label for h in served.horizons] == ["h1", "h7"]
        assert served.horizons[1].psi == pytest.approx(0.6)
