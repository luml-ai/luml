from agent.monitoring.data_quality import DataQualityMetric
from agent.monitoring.feature_drift import FeatureDriftMetric
from agent.monitoring.metric import Metric
from agent.monitoring.output_drift import OutputDriftMetric
from agent.monitoring.runtime_health import RuntimeHealthMetric


class MetricRegistry:
    """Holds the metric definitions the worker runs; adding a metric is a new entry."""

    def __init__(self, metrics: list[Metric] | None = None) -> None:
        self._metrics: list[Metric] = list(metrics or [])

    def register(self, metric: Metric) -> None:
        self._metrics.append(metric)

    def metrics(self) -> list[Metric]:
        return list(self._metrics)


def default_registry(*, latency_p95_threshold_ms: float = 1000.0) -> MetricRegistry:
    """The built-in registry. Each metric selects itself out when its requirements are
    unmet: runtime health needs no profile, data quality and feature drift need the
    profile's feature summaries, and output drift needs the output summary and task type.
    """
    return MetricRegistry(
        [
            RuntimeHealthMetric(latency_p95_threshold_ms=latency_p95_threshold_ms),
            DataQualityMetric(),
            FeatureDriftMetric(),
            OutputDriftMetric(),
        ]
    )
