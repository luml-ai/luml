from datetime import UTC, datetime

from agent.monitoring.metric import MetricInput
from agent.monitoring.models import (
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    TimeWindow,
)
from agent.monitoring.runtime_health import RuntimeHealthMetric, quantile

WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    end=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
)


def _event(
    status: str = "success", code: int | None = 200, latency: float | None = 10.0
) -> InferenceEvent:
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status=status,
        status_code=code,
        latency_ms=latency,
    )


def _input(events: list[InferenceEvent]) -> MetricInput:
    context = DeploymentContext(deployment_id="dep", profile=None, has_events=bool(events))
    return MetricInput(context=context, events=events, window=WINDOW)


def _compute(events: list[InferenceEvent], **kwargs: float) -> MetricComputation:
    return RuntimeHealthMetric(**kwargs).compute(_input(events))


def test_quantile_linear_interpolation() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert quantile(values, 0.50) == 30.0
    assert quantile(values, 0.95) == 48.0
    assert quantile([], 0.5) == 0.0
    assert quantile([7.0], 0.9) == 7.0


def test_counts_and_error_rate() -> None:
    events = [_event() for _ in range(9)] + [_event(status="error", code=400)]
    result = _compute(events)

    assert result.values["request_count"] == 10
    assert result.values["success_count"] == 9
    assert result.values["error_count"] == 1
    assert result.values["error_rate"] == 0.1


def test_failed_inference_counts_only_incomplete_inferences() -> None:
    events = [
        _event(status="success", code=200),
        _event(status="error", code=400),  # client error, not a failed inference
        _event(status="error", code=500),  # server error -> failed inference
        _event(status="failed", code=None),  # explicit failure
    ]
    result = _compute(events)

    assert result.values["error_count"] == 3
    assert result.values["failed_inference_count"] == 2


def test_latency_percentiles() -> None:
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
    events = [_event(latency=latency) for latency in latencies]
    result = _compute(events)

    assert result.values["latency_p50"] == 30.0
    assert result.values["latency_p95"] == 48.0
    assert result.values["latency_max"] == 50.0


def test_healthy_window_has_no_signals() -> None:
    result = _compute([_event() for _ in range(100)], latency_p95_threshold_ms=1000.0)

    assert result.severity == Severity.NORMAL
    assert result.signals == []


def test_error_rate_warning_threshold() -> None:
    events = [_event() for _ in range(97)] + [_event(status="error", code=400) for _ in range(3)]
    result = _compute(events)

    assert result.severity == Severity.WARNING
    signal = next(s for s in result.signals if s.key == "error_rate")
    assert signal.severity == Severity.WARNING
    assert signal.threshold == 0.01


def test_error_rate_critical_threshold() -> None:
    events = [_event() for _ in range(90)] + [_event(status="error", code=500) for _ in range(10)]
    result = _compute(events)

    assert result.severity == Severity.CRITICAL
    signal = next(s for s in result.signals if s.key == "error_rate")
    assert signal.severity == Severity.CRITICAL
    assert signal.current_value == 0.1


def test_latency_p95_over_threshold_warns() -> None:
    events = [_event(latency=2000.0) for _ in range(20)]
    result = _compute(events, latency_p95_threshold_ms=1000.0)

    signal = next(s for s in result.signals if s.key == "latency_p95")
    assert signal.severity == Severity.WARNING
    assert signal.threshold == 1000.0


def test_applies_requires_events() -> None:
    metric = RuntimeHealthMetric()
    with_events = DeploymentContext(deployment_id="dep", profile=None, has_events=True)
    without_events = DeploymentContext(deployment_id="dep", profile=None, has_events=False)

    assert metric.applies(with_events) is True
    assert metric.applies(without_events) is False
