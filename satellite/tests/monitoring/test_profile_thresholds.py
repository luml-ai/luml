"""Thresholds are a property of the deployment: its profile's rules beat the defaults."""

import uuid
from datetime import UTC, datetime
from typing import Any

from tests.support import FIXED_NOW, ago

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.data_quality import DataQualityMetric
from agent.monitoring.feature_drift import FeatureDriftMetric
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    TimeWindow,
)
from agent.monitoring.profile import build_reference_profile
from agent.monitoring.query_store import InMemoryMonitoringStore, StoredAlert
from agent.monitoring.runtime_health import RuntimeHealthMetric
from agent.monitoring.thresholds import DEFAULT, PROFILE, Threshold, defines, resolve
from agent.schemas.monitoring_query import Window

WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)

_BINS = {
    "bin_edges": [0.0, 10.0, 20.0],
    "probabilities": [0.5, 0.5],
    "min": 0.0,
    "max": 20.0,
}


def _event(
    inputs: dict[str, Any], *, status: str = "success", latency: float = 10.0
) -> InferenceEvent:
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status=status,
        status_code=200 if status == "success" else 500,
        latency_ms=latency,
        inputs=inputs,
    )


def _compute(
    metric: Metric, events: list[InferenceEvent], profile: dict[str, Any]
) -> MetricComputation:
    context = DeploymentContext("dep", profile=profile, has_events=bool(events))
    return metric.compute(MetricInput(context=context, events=events, window=WINDOW))


def test_profile_rule_replaces_the_default() -> None:
    default = Threshold(warning=0.01, critical=0.05)
    profile = {"thresholds": {"missing_rate": {"warning": 0.2, "critical": 0.5}}}

    resolved = resolve(profile, "missing_rate", default)

    assert (resolved.warning, resolved.critical, resolved.source) == (0.2, 0.5, PROFILE)
    assert defines(profile, "missing_rate")
    assert not defines(profile, "psi")


def test_malformed_rules_are_ignored_rather_than_trusted() -> None:
    default = Threshold(warning=0.01, critical=0.05)

    # critical below warning would make every window critical
    inverted = {"thresholds": {"k": {"warning": 0.5, "critical": 0.1}}}
    assert resolve(inverted, "k", default) == default
    assert resolve({"thresholds": {"k": {"warning": "high"}}}, "k", default) == default
    assert resolve({"thresholds": {"k": [0.1, 0.2]}}, "k", default) == default
    assert resolve(None, "k", default) == default


def test_data_quality_uses_the_profile_bounds() -> None:
    """5% missing is critical by default; a deployment that tolerates it says so."""
    events = [_event({"age": 5.0}) for _ in range(9)] + [_event({})]
    summaries = {"feature_summaries": {"numerical_features": {"age": _BINS}}}

    strict = _compute(DataQualityMetric(), events, summaries)
    assert strict.signals[0].severity is Severity.CRITICAL

    tolerant = _compute(
        DataQualityMetric(),
        events,
        {**summaries, "thresholds": {"missing_rate": {"warning": 0.2, "critical": 0.5}}},
    )
    assert tolerant.signals == []
    assert tolerant.severity is Severity.NORMAL


def test_feature_drift_uses_the_profile_psi_bounds() -> None:
    events = [_event({"age": 15.0}) for _ in range(20)]  # everything in the upper bin
    summaries = {"feature_summaries": {"numerical_features": {"age": _BINS}}}

    default_run = _compute(FeatureDriftMetric(), events, summaries)
    assert default_run.signals[0].severity is Severity.CRITICAL
    assert default_run.signals[0].threshold == 0.25

    relaxed = _compute(
        FeatureDriftMetric(),
        events,
        # this window drifts hard (PSI ≈ 6.9); a deployment that expects it says so
        {**summaries, "thresholds": {"psi": {"warning": 8.0, "critical": 12.0}}},
    )
    assert relaxed.signals == []


def test_runtime_latency_threshold_comes_from_the_deployment() -> None:
    """The spec calls the latency bound deployment-specific; the profile is where it lives."""
    events = [_event({}, latency=2000.0) for _ in range(10)]

    quiet = _compute(RuntimeHealthMetric(), events, {"thresholds": {}})
    assert [s.key for s in quiet.signals] == ["latency_p95"]
    assert quiet.signals[0].severity is Severity.WARNING  # default: warn past 1000 ms

    profiled = _compute(
        RuntimeHealthMetric(),
        events,
        {"thresholds": {"latency_p95_ms": {"warning": 1500, "critical": 1800}}},
    )
    assert profiled.signals[0].severity is Severity.CRITICAL
    assert profiled.signals[0].threshold == 1800


def test_psi_keeps_its_inclusive_warning_band() -> None:
    """The spec reads "0.1 to 0.25 is warning", so 0.1 itself is not normal."""
    psi_bounds = Threshold(warning=0.1, critical=0.25, warning_inclusive=True)
    assert psi_bounds.evaluate(0.1) == (Severity.WARNING, 0.1)

    # data quality says "greater than 1 percent", so the bound itself is still fine
    assert Threshold(warning=0.01, critical=0.05).evaluate(0.01) is None


async def test_alert_says_where_its_threshold_came_from() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="feature_drift",
            metric="feature_drift:income",
            feature="income",
            severity=Severity.CRITICAL,
            current_value=0.42,
            threshold=0.3,
            state="open",
            first_seen=ago(600),
            last_seen=ago(60),
        )
    )
    raw = {
        "feature_summaries": {"numerical_features": {"income": _BINS}},
        "thresholds": {"psi": {"warning": 0.15, "critical": 0.3}},
    }
    store.add_profile(build_reference_profile(dep, raw))
    service = MonitoringQueryService(store, clock=lambda: FIXED_NOW)

    result = await service.alerts(dep, QueryDimensions(window=Window.H24))

    assert result.groups[0].alerts[0].threshold_source == PROFILE


async def test_alert_without_a_profile_rule_says_default() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_alert(
        StoredAlert(
            deployment_id=dep,
            group="multivariate",
            metric="multivariate:centroid_shift",
            severity=Severity.WARNING,
            current_value=1.6,
            threshold=1.0,
            state="open",
            first_seen=ago(600),
            last_seen=ago(60),
        )
    )
    service = MonitoringQueryService(store, clock=lambda: FIXED_NOW)

    result = await service.alerts(dep, QueryDimensions(window=Window.H24))

    assert result.groups[0].alerts[0].threshold_source == DEFAULT
