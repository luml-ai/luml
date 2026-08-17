import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from agent.monitoring.feature_drift import FeatureDriftMetric
from agent.monitoring.metric import MetricInput
from agent.monitoring.models import (
    AlertState,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
    TimeWindow,
)
from agent.monitoring.multivariate_drift import MultivariateDriftMetric
from agent.monitoring.registry import default_registry
from agent.monitoring.store import InMemoryMonitoringStore
from agent.monitoring.worker import MonitoringWorker

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)

SQRT_HALF = math.sqrt(0.5)

# PCA fit on training data where x2 tracks x1: both components kept, identity scaler, and
# a score cloud that is wide along the diagonal (variance 4) and tight across it (0.01).
# A row off the diagonal therefore sits many standard deviations away even when x1 and x2
# are each perfectly ordinary.
PCA_PROFILE: dict[str, Any] = {
    "scaler": {"mean_": [0.0, 0.0], "scale_": [1.0, 1.0], "n_features": 2},
    "pca": {
        "n_components": 2,
        "n_features": 2,
        "components": [[SQRT_HALF, SQRT_HALF], [-SQRT_HALF, SQRT_HALF]],
        "mean_": [0.0, 0.0],
        "feature_names": ["x1", "x2"],
        "explained_variance_ratio": [0.99, 0.01],
    },
    "reference_distribution": {
        "mean": [0.0, 0.0],
        "covariance": [[4.0, 0.0], [0.0, 0.01]],
        "n_samples": 500,
        "n_components": 2,
    },
    "reference_projection": [[1.0, 0.05], [-1.0, -0.05], ["bad", 1.0]],
}

# A plain isotropic reference: distance is just the Euclidean norm of the row, which makes
# the numbers in the assertions easy to follow.
UNIT_PROFILE: dict[str, Any] = {
    "scaler": {"mean_": [0.0, 0.0], "scale_": [1.0, 1.0], "n_features": 2},
    "pca": {
        "n_components": 2,
        "n_features": 2,
        "components": [[1.0, 0.0], [0.0, 1.0]],
        "mean_": [0.0, 0.0],
        "feature_names": ["x1", "x2"],
        "explained_variance_ratio": [0.6, 0.4],
    },
    "reference_distribution": {
        "mean": [0.0, 0.0],
        "covariance": [[1.0, 0.0], [0.0, 1.0]],
        "n_samples": 500,
        "n_components": 2,
    },
    "reference_projection": [[1.0, 1.0], [-1.0, -1.0]],
}

# Marginals of x1 and x2 are identical between the two sets, so per-feature (univariate)
# drift is blind to the difference; only the joint structure changes.
CORRELATED_ROWS = [(-2, -2), (-1, -1), (0, 0), (1, 1), (2, 2)]  # x2 == x1 (as in training)
SHIFTED_ROWS = [(-2, 2), (-1, 1), (0, 0), (1, -1), (2, -2)]  # x2 == -x1 (correlation flipped)


def _profile(pca_profile: dict[str, Any] | None) -> dict[str, Any]:
    profile: dict[str, Any] = {"task_type": "regression", "profile_status": "ready"}
    if pca_profile is not None:
        profile["pca_profile"] = pca_profile
    return profile


def _event(inputs: dict[str, Any]) -> InferenceEvent:
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status="success",
        status_code=200,
        latency_ms=10.0,
        inputs=inputs,
    )


def _events(rows: list[tuple[Any, Any]]) -> list[InferenceEvent]:
    return [_event({"x1": x1, "x2": x2}) for x1, x2 in rows]


def _compute(events: list[InferenceEvent], pca_profile: dict[str, Any] | None) -> MetricComputation:
    context = DeploymentContext("dep", profile=_profile(pca_profile), has_events=bool(events))
    return MultivariateDriftMetric().compute(
        MetricInput(context=context, events=events, window=WINDOW)
    )


def _worker(
    store: InMemoryMonitoringStore, provider: Callable[[], list[MonitoredDeployment]]
) -> MonitoringWorker:
    return MonitoringWorker(
        store=store,
        registry=default_registry(),
        provider=provider,
        window_seconds=300.0,
        interval_seconds=60.0,
    )


def test_applies_requires_events_and_pca_profile() -> None:
    metric = MultivariateDriftMetric()
    profile = _profile(PCA_PROFILE)

    assert metric.applies(DeploymentContext("dep", profile=profile, has_events=True))
    assert not metric.applies(DeploymentContext("dep", profile=profile, has_events=False))
    assert not metric.applies(DeploymentContext("dep", profile=None, has_events=True))
    assert not metric.applies(DeploymentContext("dep", profile=_profile(None), has_events=True))


def test_distance_matches_hand_computed() -> None:
    # identity scaler, identity components, unit covariance: the distance of (3, 4) is 5
    result = _compute(_events([(3.0, 4.0)]), UNIT_PROFILE)

    assert result.values["mean_distance"] == pytest.approx(5.0)
    assert result.values["count"] == 1


def test_in_distribution_data_stays_normal() -> None:
    result = _compute(_events(CORRELATED_ROWS), PCA_PROFILE)

    assert result.values["outlier_rate"] == 0.0
    assert result.severity == Severity.NORMAL
    assert result.signals == []


def test_correlation_shift_raises_critical() -> None:
    result = _compute(_events(SHIFTED_ROWS), PCA_PROFILE)

    assert result.values["outlier_rate"] > 0.10
    assert result.severity == Severity.CRITICAL
    signal = next(s for s in result.signals if s.key == "mahalanobis_outliers")
    assert signal.severity == Severity.CRITICAL


def test_correlation_shift_missed_by_univariate_is_caught_by_multivariate() -> None:
    """The joint structure flips (x2 == -x1) while each feature's marginal is unchanged, so
    univariate PSI stays normal and only the distance in PCA space sees the drift."""
    edges = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
    uniform = [0.2, 0.2, 0.2, 0.2, 0.2]
    feature_profile = {
        "task_type": "regression",
        "profile_status": "ready",
        "feature_summaries": {
            "numerical_features": {
                "x1": {"position": 1, "bin_edges": edges, "probabilities": uniform},
                "x2": {"position": 2, "bin_edges": edges, "probabilities": uniform},
            }
        },
    }
    events = _events(SHIFTED_ROWS)
    context = DeploymentContext("dep", profile=feature_profile, has_events=True)

    univariate = FeatureDriftMetric().compute(
        MetricInput(context=context, events=events, window=WINDOW)
    )
    multivariate = _compute(events, PCA_PROFILE)

    assert univariate.severity == Severity.NORMAL
    assert univariate.values["features"]["x1"]["psi"] < 0.1
    assert univariate.values["features"]["x2"]["psi"] < 0.1
    assert multivariate.severity == Severity.CRITICAL


def test_outlier_line_is_the_reference_chi_square_quantile() -> None:
    """A healthy window leaves about 1% of rows beyond the line, so the line itself is the
    99th percentile of the reference distribution — two components, distance ~3.03."""
    result = _compute(_events(CORRELATED_ROWS), UNIT_PROFILE)

    assert result.values["outlier_threshold"] == pytest.approx(3.03, abs=0.05)


def test_missing_numerical_features_is_skipped() -> None:
    result = _compute([_event({"other": 1.0})], PCA_PROFILE)

    assert result.values == {}
    assert result.signals == []


def test_incomplete_and_non_numeric_rows_are_dropped() -> None:
    events = [
        _event({"x1": 1.0}),  # missing x2
        _event({"x1": "bad", "x2": 1.0}),  # non-numeric
        _event({"x1": float("nan"), "x2": 1.0}),  # nan
        _event({"x1": True, "x2": 1.0}),  # bool is not a number
    ]

    result = _compute(events, PCA_PROFILE)

    assert result.values == {}
    assert result.signals == []


@pytest.mark.parametrize(
    "pca_profile",
    [
        {**PCA_PROFILE, "reference_distribution": {}},  # no mean/covariance
        {
            **PCA_PROFILE,
            "reference_distribution": {"mean": [0.0], "covariance": [[1.0]]},
        },  # size does not match the components
        {
            **PCA_PROFILE,
            "reference_distribution": {
                "mean": [0.0, 0.0],
                "covariance": [[0.0, 0.0], [0.0, 0.0]],
            },
        },  # singular: no spread to measure against
        {**PCA_PROFILE, "pca": {**PCA_PROFILE["pca"], "components": [[SQRT_HALF]]}},  # wrong width
        {**PCA_PROFILE, "scaler": {"mean_": [0.0, 0.0], "scale_": [0.0, 1.0]}},  # zero scale
        {**PCA_PROFILE, "pca": {**PCA_PROFILE["pca"], "feature_names": []}},  # no feature names
    ],
)
def test_malformed_pca_profile_is_skipped(pca_profile: dict[str, Any]) -> None:
    result = _compute(_events(SHIFTED_ROWS), pca_profile)

    assert result.values == {}
    assert result.signals == []


def test_result_carries_what_the_dashboard_panel_draws() -> None:
    """The panel plots both Gaussians and the live rows, and reports the centroid shift;
    without these the card renders as an empty scatter with dashes."""
    result = _compute(_events(SHIFTED_ROWS), PCA_PROFILE)

    assert result.values["shift_metric"] == "centroid shift"
    assert result.values["shift_value"] == result.values["centroid_shift"]
    assert result.values["shift_unit"] == "σ"
    assert result.values["explained_variance"] == [0.99, 0.01]
    # the malformed third point is dropped rather than breaking the payload
    assert result.values["projection"]["reference"] == [[1.0, 0.05], [-1.0, -0.05]]
    for side in ("reference", "current"):
        polygon = result.values["ellipses"][side]
        assert len(polygon) == 49  # closed 48-segment ring
        assert polygon[0] == pytest.approx(polygon[-1])


def test_centroid_shift_measures_the_move_of_the_whole_population() -> None:
    """A window centred two reference sigmas away on PC1 is a population that moved, even
    though every row sits comfortably inside the reference spread of its own cloud."""
    # reference: PC1 variance 4 (sigma 2), so a centre at +4 is two sigmas out
    rows = [(x, x) for x in (2.6, 2.8, 3.0, 3.2, 3.4)]  # projects to PC1 ≈ 4

    result = _compute(_events(rows), PCA_PROFILE)

    assert result.values["centroid_shift"] == pytest.approx(2.1, abs=0.2)
    assert result.severity == Severity.CRITICAL
    assert any(s.key == "centroid_shift" for s in result.signals)


def test_dispersion_ratio_reports_a_widening_cloud() -> None:
    """The centre can stay put while the cloud fans out; the ratio of generalized
    variances is what notices."""
    cross = [(-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0), (0.0, 0.0)]
    tight = _compute(_events([(x / 10, y / 10) for x, y in cross]), UNIT_PROFILE)
    wide = _compute(_events([(x * 3, y * 3) for x, y in cross]), UNIT_PROFILE)

    assert tight.values["dispersion_ratio"] < 1.0 < wide.values["dispersion_ratio"]


def test_a_window_with_no_volume_reports_no_dispersion_ratio() -> None:
    """Rows strung along a line have a singular covariance — there is no volume to
    compare, and the metric says so instead of inventing a number."""
    result = _compute(_events([(-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)]), UNIT_PROFILE)

    assert result.values["dispersion_ratio"] is None
    assert result.values["centroid_shift"] == pytest.approx(0.0, abs=1e-9)


def test_a_handful_of_extreme_rows_moves_the_tail_not_the_centre() -> None:
    """The two summaries answer different questions: four wild calls among three hundred
    barely shift a centroid but light up the outlier rate."""
    rows = [(0.0, 0.0)] * 296 + [(30.0, 30.0)] * 4

    result = _compute(_events(rows), UNIT_PROFILE)

    assert result.values["outlier_rate"] == pytest.approx(4 / 300)
    assert result.values["centroid_shift"] < 1.0


def test_live_window_is_projected_onto_the_first_two_components() -> None:
    result = _compute(_events([(2.0, -1.0), (0.0, 3.0)]), UNIT_PROFILE)

    # identity scaler and identity components: the projection is the row itself
    assert result.values["projection"]["current"] == [[2.0, -1.0], [0.0, 3.0]]
    assert result.values["projection"]["reference"] == [[1.0, 1.0], [-1.0, -1.0]]


async def test_worker_materializes_multivariate_and_opens_alert() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(PCA_PROFILE)
    store.add_events("dep", _events(SHIFTED_ROWS))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "multivariate")
    assert result.severity == Severity.CRITICAL
    assert result.profile_status == "ready"
    assert result.values["outlier_rate"] > 0.10

    alerts = {alert.metric for alert in await store.active_alerts("dep")}
    assert "multivariate:mahalanobis_outliers" in alerts


async def test_worker_multivariate_alert_resolves_when_structure_recovers() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(PCA_PROFILE)
    store.events["dep"] = _events(SHIFTED_ROWS)
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)
    active = {a.metric for a in await store.active_alerts("dep")}
    assert "multivariate:mahalanobis_outliers" in active

    store.events["dep"] = _events(CORRELATED_ROWS)
    await worker.tick(now=LATER)

    active = {a.metric for a in await store.active_alerts("dep")}
    assert "multivariate:mahalanobis_outliers" not in active
    assert store.alerts[("dep", "multivariate:mahalanobis_outliers")].state == AlertState.RESOLVED


async def test_worker_skips_multivariate_without_pca_profile() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", _events(SHIFTED_ROWS))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=_profile(None))])

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert "runtime" in groups
    assert "multivariate" not in groups


def _batched_event(rows: list[tuple[Any, Any]]) -> InferenceEvent:
    return _event({"x1": [x1 for x1, _ in rows], "x2": [x2 for _, x2 in rows]})


def test_recorded_inputs_are_per_feature_batches_not_scalars() -> None:
    """Collected inputs always arrive as ``{feature: [observation, ...]}`` (that is what
    the store's normalization produces), so reading them as scalars found no complete row
    and multivariate drift stayed empty on every real deployment."""
    result = _compute([_batched_event(SHIFTED_ROWS)], PCA_PROFILE)

    assert result.values["count"] == len(SHIFTED_ROWS)
    assert result.severity == Severity.CRITICAL


def test_batched_rows_are_paired_positionally_across_features() -> None:
    correlated = _compute([_batched_event(CORRELATED_ROWS)], PCA_PROFILE)

    assert correlated.values["count"] == len(CORRELATED_ROWS)
    assert correlated.values["outlier_rate"] == 0.0
    assert correlated.severity == Severity.NORMAL


def test_incomplete_observations_inside_a_batch_are_dropped() -> None:
    event = _event({"x1": [1.0, "bad", 3.0], "x2": [1.0, 1.0, None]})

    result = _compute([event], PCA_PROFILE)

    assert result.values["count"] == 1


def test_the_live_gaussian_describes_the_bulk_not_the_wild_rows() -> None:
    """Two rows with a feature far out of range would blow the live covariance up by orders
    of magnitude — the ellipse on the dashboard would then describe those two rows. They
    are excluded from the shape and reported by the outlier rate instead."""
    calm = [(0.4, 0.4), (-0.4, -0.4), (0.3, -0.3), (-0.3, 0.3)] * 12
    wild = [(400.0, -400.0), (-380.0, 380.0)]

    result = _compute(_events(calm + wild), UNIT_PROFILE)

    assert result.values["outlier_rate"] == pytest.approx(2 / 50)
    # without trimming the ratio would run into the thousands
    assert result.values["dispersion_ratio"] < 2.0
    ellipse = result.values["ellipses"]["current"]
    assert max(abs(x) for x, _ in ellipse) < 10.0
