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

# PCA fit on training where x2 == x1: one component along (1, 1)/sqrt(2), identity
# scaler, and a reference reconstruction error of ~0 (correlated rows reconstruct
# perfectly onto the single component).
PCA_PROFILE: dict[str, Any] = {
    "scaler": {"mean_": [0.0, 0.0], "scale_": [1.0, 1.0], "n_features": 2},
    "pca": {
        "n_components": 1,
        "n_features": 2,
        "components": [[SQRT_HALF, SQRT_HALF]],
        "mean_": [0.0, 0.0],
        "feature_names": ["x1", "x2"],
    },
    "reconstruction_error_reference": {"mean": 0.0, "std": 0.1, "n_chunks": 5},
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


def test_reconstruction_error_matches_hand_computed() -> None:
    # scaler standardizes [12, 28] to [1, 2]; projecting onto (1,1)/sqrt(2) and back gives
    # [1.5, 1.5], so the error is sqrt(0.5^2 + 0.5^2) = sqrt(0.5). std is wide enough to
    # stay normal, isolating the numeric check from the threshold.
    profile = {
        "scaler": {"mean_": [10.0, 20.0], "scale_": [2.0, 4.0], "n_features": 2},
        "pca": {
            "n_components": 1,
            "n_features": 2,
            "components": [[SQRT_HALF, SQRT_HALF]],
            "mean_": [0.0, 0.0],
            "feature_names": ["x1", "x2"],
        },
        "reconstruction_error_reference": {"mean": 0.0, "std": 0.5, "n_chunks": 5},
    }

    result = _compute([_event({"x1": 12, "x2": 28})], profile)

    assert result.values["mean_reconstruction_error"] == pytest.approx(math.sqrt(0.5))
    assert result.values["count"] == 1
    assert result.severity == Severity.NORMAL
    assert result.signals == []


def test_in_distribution_data_stays_normal() -> None:
    result = _compute(_events(CORRELATED_ROWS), PCA_PROFILE)

    assert result.values["mean_reconstruction_error"] == pytest.approx(0.0, abs=1e-9)
    assert result.severity == Severity.NORMAL
    assert result.signals == []


def test_correlation_shift_raises_critical() -> None:
    result = _compute(_events(SHIFTED_ROWS), PCA_PROFILE)

    threshold = result.values["threshold"]
    assert result.values["mean_reconstruction_error"] > threshold
    assert result.severity == Severity.CRITICAL
    signal = result.signals[0]
    assert signal.key == "reconstruction_error"
    assert (signal.severity, signal.threshold) == (Severity.CRITICAL, threshold)


def test_correlation_shift_missed_by_univariate_is_caught_by_multivariate() -> None:
    # The joint structure flips (x2 == -x1) while each feature's marginal is unchanged,
    # so univariate PSI stays normal but reconstruction error flags the drift.
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


def test_missing_numerical_features_is_skipped() -> None:
    result = _compute([_event({"other": 1.0}) for _ in range(5)], PCA_PROFILE)

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
        {**PCA_PROFILE, "reconstruction_error_reference": {}},  # no reference mean/std
        {**PCA_PROFILE, "pca": {**PCA_PROFILE["pca"], "components": [[SQRT_HALF]]}},  # wrong width
        {**PCA_PROFILE, "scaler": {"mean_": [0.0, 0.0], "scale_": [0.0, 1.0]}},  # zero scale
        {**PCA_PROFILE, "pca": {**PCA_PROFILE["pca"], "feature_names": []}},  # no feature names
    ],
)
def test_malformed_pca_profile_is_skipped(pca_profile: dict[str, Any]) -> None:
    result = _compute(_events(SHIFTED_ROWS), pca_profile)

    assert result.values == {}
    assert result.signals == []


async def test_worker_materializes_multivariate_and_opens_alert() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(PCA_PROFILE)
    store.add_events("dep", _events(SHIFTED_ROWS))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "multivariate")
    assert result.severity == Severity.CRITICAL
    assert result.profile_status == "ready"
    assert result.values["mean_reconstruction_error"] > result.values["threshold"]

    alerts = {alert.metric for alert in await store.active_alerts("dep")}
    assert "multivariate:reconstruction_error" in alerts


async def test_worker_multivariate_alert_resolves_when_structure_recovers() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(PCA_PROFILE)
    store.events["dep"] = _events(SHIFTED_ROWS)
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)
    active = {a.metric for a in await store.active_alerts("dep")}
    assert "multivariate:reconstruction_error" in active

    store.events["dep"] = _events(CORRELATED_ROWS)
    await worker.tick(now=LATER)

    active = {a.metric for a in await store.active_alerts("dep")}
    assert "multivariate:reconstruction_error" not in active
    assert store.alerts[("dep", "multivariate:reconstruction_error")].state == AlertState.RESOLVED


async def test_worker_skips_multivariate_without_pca_profile() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", _events(SHIFTED_ROWS))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=_profile(None))])

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert "runtime" in groups
    assert "multivariate" not in groups
