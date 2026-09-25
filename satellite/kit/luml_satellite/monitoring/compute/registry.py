from luml_satellite.monitoring.compute.data_quality import DataQualityMetric
from luml_satellite.monitoring.compute.feature_drift import FeatureDriftMetric
from luml_satellite.monitoring.compute.metric import Metric
from luml_satellite.monitoring.compute.multivariate_drift import MultivariateDriftMetric
from luml_satellite.monitoring.compute.output_drift import OutputDriftMetric
from luml_satellite.monitoring.compute.runtime_health import RuntimeHealthMetric

_UNIVERSAL_FEATURES = ("runtime", "traces", "alerts")
_PROFILE_FEATURE_BY_METRIC = (
    ("data_quality", "data_quality"),
    ("feature_drift", "feature_drift"),
    ("output_drift", "output_drift"),
    ("multivariate", "multivariate_drift"),
)


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
    profile's feature summaries, output drift needs the output summary and task type, and
    multivariate drift needs the PCA profile.
    """
    return MetricRegistry(
        [
            RuntimeHealthMetric(latency_p95_threshold_ms=latency_p95_threshold_ms),
            DataQualityMetric(),
            FeatureDriftMetric(),
            OutputDriftMetric(),
            MultivariateDriftMetric(),
        ]
    )


def monitoring_features(registry: MetricRegistry) -> tuple[str, ...]:
    registered = {metric.metric for metric in registry.metrics()}
    profile_features = tuple(
        feature for metric, feature in _PROFILE_FEATURE_BY_METRIC if metric in registered
    )
    return (*_UNIVERSAL_FEATURES, *profile_features)
