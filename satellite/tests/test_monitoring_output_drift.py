from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

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
from agent.monitoring.output_drift import OutputDriftMetric
from agent.monitoring.registry import default_registry
from agent.monitoring.store import InMemoryMonitoringStore
from agent.monitoring.worker import MonitoringWorker

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)

NUM_OUT = {
    "type": "numerical",
    "summary": {"bin_edges": [0, 10, 20, 30, 40], "probabilities": [0.25] * 4},
}
CAT_OUT = {"type": "categorical", "summary": {"probabilities": {"cat": 0.5, "dog": 0.5}}}


def _profile(output_summary: dict[str, Any] | None, *, task_type: str = "regression") -> dict:
    profile: dict[str, Any] = {"task_type": task_type, "profile_status": "ready"}
    if output_summary is not None:
        profile["output_summary"] = output_summary
    return profile


def _event(output: Any) -> InferenceEvent:  # noqa: ANN401
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status="success",
        status_code=200,
        latency_ms=10.0,
        output=output,
    )


def _events(outputs: list[Any]) -> list[InferenceEvent]:
    return [_event(output) for output in outputs]


def _compute(events: list[InferenceEvent], profile: dict[str, Any]) -> MetricComputation:
    context = DeploymentContext("dep", profile=profile, has_events=bool(events))
    return OutputDriftMetric().compute(MetricInput(context=context, events=events, window=WINDOW))


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


def test_applies_requires_events_output_summary_and_task_type() -> None:
    metric = OutputDriftMetric()
    ready = _profile(NUM_OUT)

    assert metric.applies(DeploymentContext("dep", profile=ready, has_events=True))
    assert not metric.applies(DeploymentContext("dep", profile=ready, has_events=False))
    assert not metric.applies(DeploymentContext("dep", profile=None, has_events=True))
    no_task = {"profile_status": "ready", "output_summary": NUM_OUT}
    assert not metric.applies(DeploymentContext("dep", profile=no_task, has_events=True))


def test_stable_regression_predictions_normal_with_trend() -> None:
    outputs = ([5] * 25) + ([15] * 25) + ([25] * 25) + ([35] * 25)

    result = _compute(_events(outputs), _profile(NUM_OUT))

    assert result.severity == Severity.NORMAL
    assert result.signals == []
    assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)
    assert result.values["trend"] == {"mean": 20.0, "median": 20.0, "p05": 5.0, "p95": 35.0}


def test_shifted_regression_predictions_raise_critical_with_trend() -> None:
    result = _compute(_events([5.0] * 100), _profile(NUM_OUT))

    assert result.values["psi"] > 0.25
    assert result.severity == Severity.CRITICAL
    signal = _signal(result, "prediction")
    assert (signal.severity, signal.threshold) == (Severity.CRITICAL, 0.25)
    assert result.values["trend"]["mean"] == 5.0


def test_stable_classification_predictions_normal() -> None:
    outputs = (["cat"] * 50) + (["dog"] * 50)

    result = _compute(_events(outputs), _profile(CAT_OUT, task_type="classification"))

    assert result.severity == Severity.NORMAL
    assert result.values["psi"] == pytest.approx(0.0, abs=1e-9)


def test_shifted_classification_predictions_raise_critical() -> None:
    result = _compute(_events(["cat"] * 100), _profile(CAT_OUT, task_type="classification"))

    assert result.values["psi"] > 0.25
    assert _signal(result, "prediction").severity == Severity.CRITICAL


def test_no_numeric_predictions_produces_no_signal() -> None:
    result = _compute(_events([None, "oops"]), _profile(NUM_OUT))

    assert result.values == {}
    assert result.signals == []


async def test_worker_materializes_output_drift_and_opens_alert() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(NUM_OUT)
    store.add_events("dep", _events([5.0] * 100))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "output_drift")
    assert result.severity == Severity.CRITICAL
    assert result.values["psi"] > 0.25
    assert "trend" in result.values

    alerts = {alert.metric for alert in await store.active_alerts("dep")}
    assert "output_drift:prediction" in alerts


async def test_worker_output_drift_alert_resolves_when_data_recovers() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(NUM_OUT)
    store.events["dep"] = _events([5.0] * 100)
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)
    assert "output_drift:prediction" in {a.metric for a in await store.active_alerts("dep")}

    store.events["dep"] = _events(([5.0] * 25) + ([15.0] * 25) + ([25.0] * 25) + ([35.0] * 25))
    await worker.tick(now=LATER)

    assert "output_drift:prediction" not in {a.metric for a in await store.active_alerts("dep")}
    assert store.alerts[("dep", "output_drift:prediction")].state == AlertState.RESOLVED


async def test_worker_skips_output_drift_without_output_summary() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", _events([5.0] * 10))
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=_profile(None))])

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert "runtime" in groups
    assert "output_drift" not in groups
