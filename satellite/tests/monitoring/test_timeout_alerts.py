"""Timeouts: any in a window is a warning, repeated windows are an outage."""

from datetime import UTC, datetime

from agent.monitoring.metric import MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    Severity,
    TimeWindow,
)
from agent.monitoring.runtime_health import TIMEOUT_SIGNAL, RuntimeHealthMetric

WINDOW = TimeWindow(
    start=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
    end=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)


def _event(status: str = "success", status_code: int | None = 200) -> InferenceEvent:
    return InferenceEvent(
        event_id="e",
        deployment_id="dep",
        status=status,
        status_code=status_code,
        latency_ms=10.0,
    )


def _compute(
    events: list[InferenceEvent], *, open_signals: frozenset[str] = frozenset()
) -> MetricComputation:
    context = DeploymentContext("dep", profile={}, has_events=bool(events))
    return RuntimeHealthMetric().compute(
        MetricInput(context=context, events=events, window=WINDOW, open_signals=open_signals)
    )


def _timeout_signal(result: MetricComputation) -> AlertSignal | None:
    return next((s for s in result.signals if s.key == TIMEOUT_SIGNAL), None)


def test_a_timeout_is_recognized_by_status_or_gateway_code() -> None:
    events = [
        _event(),
        _event("timeout", None),
        _event("error", 504),
        _event("deadline_exceeded", None),
    ]

    result = _compute(events)

    assert result.values["timeout_count"] == 3
    # a call that never returned is a failed inference too, not just an error
    assert result.values["failed_inference_count"] == 3


def test_a_clean_window_raises_nothing() -> None:
    result = _compute([_event() for _ in range(10)])

    assert result.values["timeout_count"] == 0
    assert _timeout_signal(result) is None


def test_any_timeout_in_a_window_warns() -> None:
    events = [_event() for _ in range(19)] + [_event("timeout", None)]

    signal = _timeout_signal(_compute(events))

    assert signal is not None
    assert signal.severity is Severity.WARNING
    assert signal.current_value == 1.0


def test_timeouts_in_consecutive_windows_escalate() -> None:
    """The previous window's alert is still open, so this window is a repeat."""
    events = [_event("timeout", None)]

    signal = _timeout_signal(_compute(events, open_signals=frozenset({TIMEOUT_SIGNAL})))

    assert signal is not None
    assert signal.severity is Severity.CRITICAL


def test_an_unrelated_open_alert_does_not_escalate_timeouts() -> None:
    events = [_event("timeout", None)]

    signal = _timeout_signal(_compute(events, open_signals=frozenset({"error_rate"})))

    assert signal is not None
    assert signal.severity is Severity.WARNING


def test_worker_reads_the_upstream_status_code() -> None:
    """A gateway timeout is a 504 upstream; the reader used to flatten it to 500."""
    from agent.monitoring.greptime import GreptimeMonitoringStore

    store = GreptimeMonitoringStore(host="gt", port=4000)
    row = {
        "span_attributes": {
            "inference.event_id": "e1",
            "inference.status": "error",
            "inference.status_code": 504,
            "inference.latency_ms": 30000.0,
        }
    }

    event = store._to_event("dep", row)

    assert event.status_code == 504
    assert event.is_timeout
    assert not event.is_success


def test_an_event_without_a_code_still_classifies() -> None:
    """Rows written before the code was read back keep the old success/error split."""
    from agent.monitoring.greptime import GreptimeMonitoringStore

    store = GreptimeMonitoringStore(host="gt", port=4000)

    success = store._to_event("dep", {"span_attributes": {"inference.status": "success"}})
    failure = store._to_event("dep", {"span_attributes": {"inference.status": "error"}})

    assert (success.status_code, failure.status_code) == (200, 500)
    assert not failure.is_timeout
