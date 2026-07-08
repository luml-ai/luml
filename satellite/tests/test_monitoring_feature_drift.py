from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from agent.monitoring.feature_drift import FeatureDriftMetric
from agent.monitoring.metric import MetricInput
from agent.monitoring.models import (
    AlertSignal,
    AlertState,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MonitoredDeployment,
    Severity,
    TimeWindow,
)
from agent.monitoring.registry import default_registry
from agent.monitoring.store import InMemoryMonitoringStore
from agent.monitoring.worker import MonitoringWorker

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)

# Four equal reference bins over [0, 40) and four equal reference categories.
NUM_REF = {"age": {"position": 1, "bin_edges": [0, 10, 20, 30, 40], "probabilities": [0.25] * 4}}
CAT_REF = {
    "region": {"position": 2, "categories": ["a", "b"], "probabilities": {"a": 0.5, "b": 0.5}}
}


def _profile(
    *, numerical: dict[str, Any] | None = None, categorical: dict[str, Any] | None = None
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    if numerical is not None:
        summaries["numerical_features"] = numerical
    if categorical is not None:
        summaries["categorical_features"] = categorical
    return {"task_type": "regression", "profile_status": "ready", "feature_summaries": summaries}


def _event(inputs: dict[str, Any]) -> InferenceEvent:
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status="success",
        status_code=200,
        latency_ms=10.0,
        inputs=inputs,
    )


def _events(name: str, values: list[Any]) -> list[InferenceEvent]:
    return [_event({name: value}) for value in values]


def _compute(events: list[InferenceEvent], profile: dict[str, Any]) -> MetricComputation:
    context = DeploymentContext("dep", profile=profile, has_events=bool(events))
    return FeatureDriftMetric().compute(MetricInput(context=context, events=events, window=WINDOW))


def _signal(result: MetricComputation, key: str) -> AlertSignal:
    return next(signal for signal in result.signals if signal.key == key)


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


def test_applies_requires_events_and_feature_summaries() -> None:
    metric = FeatureDriftMetric()
    profile = _profile(numerical=NUM_REF)

    assert metric.applies(DeploymentContext("dep", profile=profile, has_events=True))
    assert not metric.applies(DeploymentContext("dep", profile=profile, has_events=False))
    assert not metric.applies(DeploymentContext("dep", profile=None, has_events=True))


def test_stable_numerical_stays_normal() -> None:
    values = ([5] * 25) + ([15] * 25) + ([25] * 25) + ([35] * 25)  # one bin each

    result = _compute(_events("age", values), _profile(numerical=NUM_REF))

    assert result.severity == Severity.NORMAL
    assert result.signals == []
    assert result.values["features"]["age"]["psi"] == pytest.approx(0.0, abs=1e-9)
    assert result.values["features"]["age"]["count"] == 100


def test_shifted_numerical_raises_critical() -> None:
    result = _compute(_events("age", [5] * 100), _profile(numerical=NUM_REF))

    assert result.values["features"]["age"]["psi"] > 0.25
    assert result.severity == Severity.CRITICAL
    signal = _signal(result, "age")
    assert (signal.severity, signal.threshold) == (Severity.CRITICAL, 0.25)


def test_moderate_numerical_shift_warns() -> None:
    values = ([5] * 40) + ([15] * 25) + ([25] * 25) + ([35] * 10)  # props 0.40/0.25/0.25/0.10

    result = _compute(_events("age", values), _profile(numerical=NUM_REF))

    psi = result.values["features"]["age"]["psi"]
    assert 0.1 <= psi <= 0.25
    signal = _signal(result, "age")
    assert (signal.severity, signal.threshold) == (Severity.WARNING, 0.1)


def test_stable_categorical_stays_normal() -> None:
    values = (["a"] * 50) + (["b"] * 50)

    result = _compute(_events("region", values), _profile(categorical=CAT_REF))

    assert result.severity == Severity.NORMAL
    assert result.values["features"]["region"]["psi"] == pytest.approx(0.0, abs=1e-9)


def test_shifted_categorical_raises_critical() -> None:
    result = _compute(_events("region", ["a"] * 100), _profile(categorical=CAT_REF))

    assert result.values["features"]["region"]["psi"] > 0.25
    assert _signal(result, "region").severity == Severity.CRITICAL


def test_unseen_categories_contribute_to_psi() -> None:
    profile = _profile(categorical=CAT_REF)
    known = _compute(_events("region", (["a"] * 50) + (["b"] * 50)), profile)
    with_unseen = _compute(_events("region", (["a"] * 45) + (["b"] * 45) + (["z"] * 10)), profile)

    assert known.severity == Severity.NORMAL
    unseen_psi = with_unseen.values["features"]["region"]["psi"]
    assert unseen_psi > known.values["features"]["region"]["psi"]
    assert unseen_psi > 0.25
    assert with_unseen.severity == Severity.CRITICAL


def test_feature_without_reference_distribution_is_skipped() -> None:
    # Only min/max (as data-quality uses); no bins/probabilities to score against.
    profile = _profile(numerical={"age": {"position": 1, "min": 0, "max": 40}})

    result = _compute(_events("age", [5] * 100), profile)

    assert result.values["features"] == {}
    assert result.signals == []


def test_feature_with_no_valid_live_values_is_skipped() -> None:
    profile = _profile(numerical=NUM_REF)
    events = [_event({"age": None}) for _ in range(5)] + [_event({"age": "x"}) for _ in range(5)]

    result = _compute(events, profile)

    assert "age" not in result.values["features"]
    assert result.severity == Severity.NORMAL


async def test_worker_materializes_feature_drift_and_opens_alert() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(numerical=NUM_REF)
    store.add_events("dep", _events("age", [5] * 100))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "feature_drift")
    assert result.severity == Severity.CRITICAL
    assert result.profile_status == "ready"
    assert result.values["features"]["age"]["psi"] > 0.25

    alerts = {alert.metric for alert in await store.active_alerts("dep")}
    assert "feature_drift:age" in alerts


async def test_worker_feature_drift_alert_resolves_when_data_recovers() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(numerical=NUM_REF)
    store.events["dep"] = _events("age", [5] * 100)
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)
    assert "feature_drift:age" in {a.metric for a in await store.active_alerts("dep")}

    store.events["dep"] = _events("age", ([5] * 25) + ([15] * 25) + ([25] * 25) + ([35] * 25))
    await worker.tick(now=LATER)

    assert "feature_drift:age" not in {a.metric for a in await store.active_alerts("dep")}
    assert store.alerts[("dep", "feature_drift:age")].state == AlertState.RESOLVED


async def test_worker_skips_feature_drift_without_profile() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", _events("age", [5] * 10))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=None)])

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert "runtime" in groups
    assert "feature_drift" not in groups


async def test_worker_runs_applicable_subset_with_feature_summaries() -> None:
    # A profile with feature summaries but no output summary or PCA profile: the
    # applicable subset (runtime, data quality, feature drift) runs while metrics whose
    # requirements are unmet select themselves out — here output drift (no output summary).
    store = InMemoryMonitoringStore()
    store.add_events("dep", _events("age", [5] * 100))
    worker = _worker(
        store, lambda: [MonitoredDeployment("dep", profile=_profile(numerical=NUM_REF))]
    )

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert {"runtime", "data_quality", "feature_drift"} <= groups
    assert "output_drift" not in groups
