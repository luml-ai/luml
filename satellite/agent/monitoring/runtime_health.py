import math
from typing import Any

from agent.monitoring import thresholds
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    MetricComputation,
    Severity,
    worst_severity,
)
from agent.monitoring.thresholds import Threshold

# The signal key is also the key its count has in the window, so the dashboard can plot it.
TIMEOUT_SIGNAL = "timeout_count"


def quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated quantile of an already-sorted, non-empty list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


class RuntimeHealthMetric(Metric):
    """Request counts, error rate, latency percentiles and failed inferences.

    Derived from ``inference_events`` alone, so it needs no reference profile.
    """

    metric = "runtime"

    def __init__(
        self,
        *,
        latency_p95_threshold_ms: float = 1000.0,
        error_rate_warning: float = 0.01,
        error_rate_critical: float = 0.05,
    ) -> None:
        self.latency_p95_threshold_ms = latency_p95_threshold_ms
        self.error_rate_warning = error_rate_warning
        self.error_rate_critical = error_rate_critical

    def _bounds(self, profile: dict[str, Any] | None) -> tuple[Threshold, Threshold]:
        """Error-rate and latency bounds for this deployment.

        The spec calls the latency threshold deployment-specific, and the reference profile
        is where a deployment states it; without a rule the metric keeps its own default
        and, as before, only warns on latency.
        """
        error_rate = thresholds.resolve(
            profile,
            thresholds.ERROR_RATE,
            Threshold(warning=self.error_rate_warning, critical=self.error_rate_critical),
        )
        latency = thresholds.resolve(
            profile,
            thresholds.LATENCY_P95_MS,
            Threshold(
                warning=self.latency_p95_threshold_ms,
                critical=math.inf,  # no critical latency bound unless the profile sets one
            ),
        )
        return error_rate, latency

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events

    def compute(self, data: MetricInput) -> MetricComputation:
        events = data.events
        request_count = len(events)
        success_count = sum(1 for event in events if event.is_success)
        error_count = request_count - success_count
        failed_inference_count = sum(1 for event in events if event.is_failed_inference)
        timeout_count = sum(1 for event in events if event.is_timeout)
        error_rate = error_count / request_count if request_count else 0.0

        latencies = sorted(e.latency_ms for e in events if e.latency_ms is not None)
        latency_p50 = quantile(latencies, 0.50)
        latency_p95 = quantile(latencies, 0.95)
        latency_max = latencies[-1] if latencies else 0.0

        values: dict[str, float | int] = {
            "request_count": request_count,
            "success_count": success_count,
            "error_count": error_count,
            "error_rate": error_rate,
            "latency_p50": latency_p50,
            "latency_p95": latency_p95,
            "latency_max": latency_max,
            "failed_inference_count": failed_inference_count,
            "timeout_count": timeout_count,
        }

        signals = self._signals(
            error_rate,
            latency_p95,
            *self._bounds(data.profile),
            timeout_count=timeout_count,
            timeouts_already_open=TIMEOUT_SIGNAL in data.open_signals,
        )
        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values=values, severity=severity, signals=signals)

    @staticmethod
    def _signals(
        error_rate: float,
        latency_p95: float,
        error_bounds: Threshold,
        latency_bounds: Threshold,
        *,
        timeout_count: int = 0,
        timeouts_already_open: bool = False,
    ) -> list[AlertSignal]:
        signals: list[AlertSignal] = []
        evaluated = error_bounds.evaluate(error_rate)
        if evaluated is not None:
            severity, breached = evaluated
            signals.append(AlertSignal("error_rate", error_rate, breached, severity))

        evaluated = latency_bounds.evaluate(latency_p95)
        if evaluated is not None:
            severity, breached = evaluated
            signals.append(AlertSignal("latency_p95", latency_p95, breached, severity))

        # The spec asks for two levels here: any timeout in a window deserves attention,
        # timeouts that keep coming window after window are an outage. "Repeated" is read
        # off the alert itself — it is still open only if an earlier window raised it.
        if timeout_count > 0:
            severity = Severity.CRITICAL if timeouts_already_open else Severity.WARNING
            signals.append(AlertSignal(TIMEOUT_SIGNAL, float(timeout_count), 0.0, severity))
        return signals
