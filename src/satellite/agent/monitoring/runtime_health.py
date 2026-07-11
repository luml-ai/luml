from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    AlertSignal,
    DeploymentContext,
    MetricComputation,
    Severity,
    worst_severity,
)


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

    def applies(self, context: DeploymentContext) -> bool:
        return context.has_events

    def compute(self, data: MetricInput) -> MetricComputation:
        events = data.events
        request_count = len(events)
        success_count = sum(1 for event in events if event.is_success)
        error_count = request_count - success_count
        failed_inference_count = sum(1 for event in events if event.is_failed_inference)
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
        }

        signals = self._signals(error_rate, latency_p95)
        severity = worst_severity(signal.severity for signal in signals)
        return MetricComputation(values=values, severity=severity, signals=signals)

    def _signals(self, error_rate: float, latency_p95: float) -> list[AlertSignal]:
        signals: list[AlertSignal] = []
        if error_rate > self.error_rate_critical:
            signals.append(
                AlertSignal("error_rate", error_rate, self.error_rate_critical, Severity.CRITICAL)
            )
        elif error_rate > self.error_rate_warning:
            signals.append(
                AlertSignal("error_rate", error_rate, self.error_rate_warning, Severity.WARNING)
            )

        if latency_p95 > self.latency_p95_threshold_ms:
            signals.append(
                AlertSignal(
                    "latency_p95", latency_p95, self.latency_p95_threshold_ms, Severity.WARNING
                )
            )
        return signals
