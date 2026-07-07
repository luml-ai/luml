import uuid

from tests.support import FIXED_NOW, ago

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.query_store import (
    InMemoryMonitoringStore,
    ReferenceFeatureProfile,
    ReferenceProfile,
    StoredAlert,
    StoredMetricResult,
)
from agent.schemas.monitoring_query import (
    ProfileStatus,
    SectionState,
    Severity,
    SeverityFilter,
    Window,
)


def _service(store: InMemoryMonitoringStore) -> MonitoringQueryService:
    return MonitoringQueryService(store, clock=lambda: FIXED_NOW)


def _dims() -> QueryDimensions:
    return QueryDimensions(window=Window.H24)


def _feature_drift_result(
    dep: uuid.UUID, window: Window = Window.H24, income_psi: float = 0.31
) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="feature_drift",
        window=window.value,
        values={
            "features": {
                "income": {
                    "psi": income_psi,
                    "status": "critical",
                    "psi_series": [
                        {"t": ago(3 * 3600), "value": 0.10},
                        {"t": ago(2 * 3600), "value": 0.22},
                        {"t": ago(3600), "value": income_psi},
                    ],
                    "distribution": {
                        "kind": "numeric",
                        "bins": [
                            {"label": "[0,10k)", "reference": 0.5, "current": 0.2},
                            {"label": "[10k,20k)", "reference": 0.3, "current": 0.3},
                            {"label": "[20k,inf)", "reference": 0.2, "current": 0.5},
                        ],
                    },
                },
                "age": {"psi": 0.05, "status": "ok"},
            }
        },
        severity="critical",
    )


def _multivariate_result(dep: uuid.UUID) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="multivariate",
        window=Window.H24.value,
        values={
            "shift_value": 3.4,
            "shift_metric": "reconstruction_error",
            "status": "warning",
            "explained_variance": [0.6, 0.25, 0.15],
            "features": {
                "income": {"psi": 0.31, "status": "critical"},
                "age": {"psi": 0.05, "status": "ok"},
            },
            "projection": {
                "reference": [[0.1, 0.2], [-0.3, 0.4]],
                "current": [[1.1, 1.2], [0.9, -0.4]],
            },
        },
        severity="warning",
    )


def _reference_profile(dep: uuid.UUID, status: str = "ready") -> ReferenceProfile:
    return ReferenceProfile(
        deployment_id=dep,
        status=status,
        baseline_label="training set (2026-01-05)",
        computed_at=ago(30 * 24 * 3600),
        features={
            "income": ReferenceFeatureProfile(
                feature="income",
                kind="numeric",
                summary={"mean": 52000.0, "std": 12000.0, "min": 10000.0, "max": 200000.0},
                bin_edges=[0.0, 10000.0, 20000.0, 200000.0],
                histogram=[0.5, 0.3, 0.2],
            ),
            "region": ReferenceFeatureProfile(
                feature="region",
                kind="categorical",
                summary={"distinct": 3.0},
                categories=["north", "south", "east"],
                category_probabilities=[0.5, 0.3, 0.2],
            ),
        },
    )


def _drift_store(dep: uuid.UUID) -> InMemoryMonitoringStore:
    store = InMemoryMonitoringStore()
    store.add_result(_feature_drift_result(dep))
    store.add_result(_multivariate_result(dep))
    return store


async def test_feature_drift_ranked_by_psi_with_status() -> None:
    dep = uuid.uuid4()
    result = await _service(_drift_store(dep)).feature_drift(dep, _dims())

    assert result.state is SectionState.OK
    assert [f.feature for f in result.features] == ["income", "age"]  # ranked PSI desc
    assert result.features[0].psi == 0.31
    assert result.features[0].severity is Severity.CRITICAL
    assert result.features[1].severity is Severity.OK


async def test_feature_drift_selected_feature_returns_distribution_and_psi_over_time() -> None:
    dep = uuid.uuid4()
    dims = QueryDimensions(window=Window.H24, feature="income")
    result = await _service(_drift_store(dep)).feature_drift(dep, dims)

    selected = result.selected
    assert selected is not None
    assert selected.feature == "income"
    assert selected.status is Severity.CRITICAL
    assert selected.distribution is not None
    assert selected.distribution.kind == "numeric"
    assert [b.label for b in selected.distribution.bins] == ["[0,10k)", "[10k,20k)", "[20k,inf)"]
    assert selected.distribution.bins[0].reference == 0.5
    assert selected.distribution.bins[0].current == 0.2
    assert selected.psi_over_time is not None
    assert [p.value for p in selected.psi_over_time.points] == [0.10, 0.22, 0.31]


async def test_feature_drift_no_selected_feature_when_filter_unset() -> None:
    dep = uuid.uuid4()
    result = await _service(_drift_store(dep)).feature_drift(dep, _dims())

    assert result.selected is None


async def test_feature_drift_unknown_selected_feature_is_none() -> None:
    dep = uuid.uuid4()
    dims = QueryDimensions(window=Window.H24, feature="not_a_feature")
    result = await _service(_drift_store(dep)).feature_drift(dep, dims)

    assert result.selected is None
    assert [f.feature for f in result.features] == ["income", "age"]  # list still returned


async def test_multivariate_panel_returns_shift_variance_and_projection() -> None:
    dep = uuid.uuid4()
    result = await _service(_drift_store(dep)).feature_drift(dep, _dims())

    panel = result.multivariate
    assert panel.state is SectionState.OK
    assert panel.status is Severity.WARNING
    assert panel.shift_value == 3.4
    assert panel.shift_metric == "reconstruction_error"
    assert panel.explained_variance == [0.6, 0.25, 0.15]
    assert [f.feature for f in panel.feature_psi] == ["income", "age"]  # ranked
    assert [(p.x, p.y) for p in panel.reference_projection] == [(0.1, 0.2), (-0.3, 0.4)]
    assert [(p.x, p.y) for p in panel.current_projection] == [(1.1, 1.2), (0.9, -0.4)]


async def test_multivariate_panel_empty_when_only_univariate_computed() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_result(_feature_drift_result(dep))  # no multivariate result

    result = await _service(store).feature_drift(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.OK
    assert result.multivariate.state is SectionState.EMPTY
    assert result.multivariate.shift_value is None


async def test_feature_drift_empty_shape_when_not_computed() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()  # worker has produced nothing for this window

    result = await _service(store).feature_drift(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.EMPTY
    assert result.features == []
    assert result.selected is None
    assert result.multivariate.state is SectionState.EMPTY


async def test_feature_drift_window_dimension_changes_the_query() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_result(_feature_drift_result(dep, window=Window.H24, income_psi=0.31))
    store.add_result(_feature_drift_result(dep, window=Window.D7, income_psi=0.12))

    svc = _service(store)
    day = await svc.feature_drift(dep, QueryDimensions(window=Window.H24))
    week = await svc.feature_drift(dep, QueryDimensions(window=Window.D7))

    assert day.features[0].psi == 0.31
    assert week.features[0].psi == 0.12


async def test_feature_drift_scoped_to_deployment() -> None:
    dep_a, dep_b = uuid.uuid4(), uuid.uuid4()
    store = _drift_store(dep_a)  # only dep_a has materialized drift

    svc = _service(store)
    dims = QueryDimensions(window=Window.H24)
    assert (await svc.feature_drift(dep_a, dims)).state is SectionState.OK
    assert (await svc.feature_drift(dep_b, dims)).state is SectionState.EMPTY


async def test_feature_drift_severity_filter_narrows_alerts_not_features() -> None:
    dep = uuid.uuid4()
    store = _drift_store(dep)
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="feature_drift",
            metric="psi",
            feature="income",
            severity=Severity.CRITICAL,
            current_value=0.31,
            threshold=0.25,
            last_seen=ago(60),
        )
    )
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="feature_drift",
            metric="psi",
            feature="age",
            severity=Severity.WARNING,
            last_seen=ago(120),
        )
    )

    svc = _service(store)
    all_alerts = await svc.feature_drift(dep, QueryDimensions(severity=SeverityFilter.ALL))
    critical = await svc.feature_drift(dep, QueryDimensions(severity=SeverityFilter.CRITICAL))

    assert len(all_alerts.alerts) == 2
    assert len(critical.alerts) == 1
    assert critical.alerts[0].severity is Severity.CRITICAL
    assert len(critical.features) == 2  # the ranked list is unfiltered by severity


async def test_feature_drift_placeholder_profile_degrades_gracefully() -> None:
    dep = uuid.uuid4()
    store = _drift_store(dep)
    store.set_profile_status(dep, "placeholder")

    result = await _service(store).feature_drift(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.OK  # data still returned, not an error
    assert result.profile_status is ProfileStatus.PLACEHOLDER


async def test_feature_drift_store_unavailable_yields_unavailable_state() -> None:
    dep = uuid.uuid4()
    store = _drift_store(dep)
    store.unavailable = True

    result = await _service(store).feature_drift(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.UNAVAILABLE


async def test_reference_profile_selected_numeric_feature() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_profile(_reference_profile(dep))
    dims = QueryDimensions(feature="income")

    result = await _service(store).reference_profile(dep, dims)

    assert result.state is SectionState.OK
    assert result.baseline_label == "training set (2026-01-05)"
    assert result.features == ["income", "region"]  # sorted available names
    feature = result.feature
    assert feature is not None
    assert feature.kind == "numeric"
    assert feature.summary["mean"] == 52000.0
    assert feature.bin_edges == [0.0, 10000.0, 20000.0, 200000.0]
    assert feature.histogram == [0.5, 0.3, 0.2]
    assert feature.categories is None


async def test_reference_profile_selected_categorical_feature() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_profile(_reference_profile(dep))
    dims = QueryDimensions(feature="region")

    result = await _service(store).reference_profile(dep, dims)

    feature = result.feature
    assert feature is not None
    assert feature.kind == "categorical"
    assert feature.categories == ["north", "south", "east"]
    assert feature.category_probabilities == [0.5, 0.3, 0.2]
    assert feature.bin_edges is None


async def test_reference_profile_lists_features_without_selection() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_profile(_reference_profile(dep))

    result = await _service(store).reference_profile(dep, QueryDimensions())

    assert result.state is SectionState.OK
    assert result.feature is None
    assert result.features == ["income", "region"]


async def test_reference_profile_empty_shape_when_absent() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()  # no profile loaded

    result = await _service(store).reference_profile(dep, QueryDimensions(feature="income"))

    assert result.state is SectionState.EMPTY
    assert result.feature is None


async def test_reference_profile_placeholder_degrades_gracefully() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_profile(_reference_profile(dep, status="placeholder"))
    dims = QueryDimensions(feature="income")

    result = await _service(store).reference_profile(dep, dims)

    assert result.state is SectionState.OK  # degrades, does not error
    assert result.profile_status is ProfileStatus.PLACEHOLDER
    assert result.feature is not None


async def test_reference_profile_store_unavailable_yields_unavailable_state() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_profile(_reference_profile(dep))
    store.unavailable = True

    result = await _service(store).reference_profile(dep, QueryDimensions(feature="income"))

    assert result.state is SectionState.UNAVAILABLE
