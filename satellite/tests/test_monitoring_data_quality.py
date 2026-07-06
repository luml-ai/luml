from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from agent.monitoring.data_quality import DataQualityMetric
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

NUMERICAL = {"age": {"position": 1, "min": 18.0, "max": 75.0}}
CATEGORICAL = {"region": {"position": 2, "categories": ["north", "south", "east", "west"]}}


def _profile(
    *,
    numerical: dict[str, Any] | None = None,
    categorical: dict[str, Any] | None = None,
    status: str = "ready",
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    if numerical is not None:
        summaries["numerical_features"] = numerical
    if categorical is not None:
        summaries["categorical_features"] = categorical
    return {"task_type": "regression", "profile_status": status, "feature_summaries": summaries}


def _event(inputs: dict[str, Any]) -> InferenceEvent:
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status="success",
        status_code=200,
        latency_ms=10.0,
        inputs=inputs,
    )


def _compute(events: list[InferenceEvent], profile: dict[str, Any]) -> MetricComputation:
    context = DeploymentContext("dep", profile=profile, has_events=bool(events))
    return DataQualityMetric().compute(MetricInput(context=context, events=events, window=WINDOW))


def _signal(result: MetricComputation, key: str) -> AlertSignal:
    return next(signal for signal in result.signals if signal.key == key)


def _worker(
    store: InMemoryMonitoringStore,
    provider: Callable[[], list[MonitoredDeployment]],
) -> MonitoringWorker:
    return MonitoringWorker(
        store=store,
        registry=default_registry(),
        provider=provider,
        window_seconds=300.0,
        interval_seconds=60.0,
    )


def test_applies_requires_events_and_feature_summaries() -> None:
    metric = DataQualityMetric()
    profile = _profile(numerical=NUMERICAL)

    assert metric.applies(DeploymentContext("dep", profile=profile, has_events=True))
    assert not metric.applies(DeploymentContext("dep", profile=profile, has_events=False))
    assert not metric.applies(DeploymentContext("dep", profile=None, has_events=True))
    empty = {"task_type": "regression", "feature_summaries": {}}
    assert not metric.applies(DeploymentContext("dep", profile=empty, has_events=True))


def test_clean_inputs_stay_normal() -> None:
    events = [_event({"age": 30, "region": "north"}) for _ in range(10)]

    result = _compute(events, _profile(numerical=NUMERICAL, categorical=CATEGORICAL))

    assert result.severity == Severity.NORMAL
    assert result.signals == []
    age = result.values["features"]["age"]
    assert age == {
        "count": 10,
        "missing_rate": 0.0,
        "type_mismatch_rate": 0.0,
        "range_violation_rate": 0.0,
    }
    assert result.values["features"]["region"]["unseen_category_rate"] == 0.0


def test_missing_values_raise_critical_alert() -> None:
    events = [_event({"age": 30}) for _ in range(9)] + [_event({})]

    result = _compute(events, _profile(numerical=NUMERICAL))

    assert result.values["features"]["age"]["missing_rate"] == 0.1
    signal = _signal(result, "age.missing")
    assert (signal.severity, signal.threshold, signal.current_value) == (
        Severity.CRITICAL,
        0.05,
        0.1,
    )


def test_numeric_type_mismatch_warns_within_one_percent() -> None:
    events = [_event({"age": 30}) for _ in range(99)] + [_event({"age": "oops"})]

    result = _compute(events, _profile(numerical=NUMERICAL))

    assert result.values["features"]["age"]["type_mismatch_rate"] == 0.01
    signal = _signal(result, "age.type_mismatch")
    assert (signal.severity, signal.threshold) == (Severity.WARNING, 0.0)


def test_bool_counts_as_numeric_type_mismatch() -> None:
    events = [_event({"age": True}) for _ in range(10)]

    result = _compute(events, _profile(numerical=NUMERICAL))

    assert result.values["features"]["age"]["type_mismatch_rate"] == 1.0
    assert result.values["features"]["age"]["range_violation_rate"] == 0.0


def test_out_of_range_numeric_raises_critical_alert() -> None:
    events = [_event({"age": 30}) for _ in range(8)]
    events.append(_event({"age": 200}))  # above max
    events.append(_event({"age": 5}))  # below min

    result = _compute(events, _profile(numerical=NUMERICAL))

    assert result.values["features"]["age"]["range_violation_rate"] == 0.2
    signal = _signal(result, "age.range_violation")
    assert (signal.severity, signal.threshold) == (Severity.CRITICAL, 0.05)


def test_range_violation_warns_between_one_and_five_percent() -> None:
    events = [_event({"age": 30}) for _ in range(98)]
    events += [_event({"age": 200}), _event({"age": 200})]

    result = _compute(events, _profile(numerical=NUMERICAL))

    assert result.values["features"]["age"]["range_violation_rate"] == 0.02
    signal = _signal(result, "age.range_violation")
    assert (signal.severity, signal.threshold) == (Severity.WARNING, 0.01)


def test_unseen_category_raises_critical_alert() -> None:
    events = [_event({"region": "north"}) for _ in range(9)] + [_event({"region": "mars"})]

    result = _compute(events, _profile(categorical=CATEGORICAL))

    assert result.values["features"]["region"]["unseen_category_rate"] == 0.1
    signal = _signal(result, "region.unseen_category")
    assert (signal.severity, signal.threshold) == (Severity.CRITICAL, 0.01)


def test_non_string_category_is_type_mismatch_not_unseen() -> None:
    events = [_event({"region": "north"}) for _ in range(9)] + [_event({"region": 123})]

    result = _compute(events, _profile(categorical=CATEGORICAL))

    region = result.values["features"]["region"]
    assert region["type_mismatch_rate"] == 0.1
    assert region["unseen_category_rate"] == 0.0
    assert _signal(result, "region.type_mismatch").severity == Severity.CRITICAL


async def test_worker_materializes_data_quality_and_opens_alerts() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(numerical=NUMERICAL, categorical=CATEGORICAL)
    events = [_event({"age": 30, "region": "north"}) for _ in range(8)]
    events.append(_event({"age": 200, "region": "north"}))  # out-of-range numeric
    events.append(_event({"age": 30, "region": "mars"}))  # unseen category
    store.add_events("dep", events)
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)

    result = next(r for r in store.results if r.metric == "data_quality")
    assert result.severity == Severity.CRITICAL
    assert result.profile_status == "ready"
    assert result.values["features"]["age"]["range_violation_rate"] == 0.1
    assert result.values["features"]["region"]["unseen_category_rate"] == 0.1

    alerts = {alert.metric for alert in await store.active_alerts("dep")}
    assert "data_quality:age.range_violation" in alerts
    assert "data_quality:region.unseen_category" in alerts


async def test_worker_skips_data_quality_without_profile() -> None:
    store = InMemoryMonitoringStore()
    store.add_events("dep", [_event({"age": 30, "region": "north"})])
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=None)])

    await worker.tick(now=NOW)

    groups = {result.metric for result in store.results}
    assert "runtime" in groups
    assert "data_quality" not in groups


async def test_data_quality_alert_resolves_when_inputs_recover() -> None:
    store = InMemoryMonitoringStore()
    profile = _profile(categorical=CATEGORICAL)
    store.events["dep"] = [_event({"region": "north"}) for _ in range(9)] + [
        _event({"region": "mars"})
    ]
    worker = _worker(store, lambda: [MonitoredDeployment("dep", profile=profile)])

    await worker.tick(now=NOW)
    opened = {alert.metric for alert in await store.active_alerts("dep")}
    assert "data_quality:region.unseen_category" in opened

    store.events["dep"] = [_event({"region": "north"}) for _ in range(10)]
    await worker.tick(now=LATER)

    active = {alert.metric for alert in await store.active_alerts("dep")}
    assert "data_quality:region.unseen_category" not in active
    resolved = store.alerts[("dep", "data_quality:region.unseen_category")]
    assert resolved.state == AlertState.RESOLVED
