from luml_satellite.monitoring.compute.data_quality import DataQualityMetric
from luml_satellite.monitoring.compute.multivariate_drift import MultivariateDriftMetric
from luml_satellite.monitoring.compute.registry import (
    MetricRegistry,
    default_registry,
    monitoring_features,
)


def test_default_registry_exposes_every_monitoring_feature() -> None:
    assert monitoring_features(default_registry()) == (
        "runtime",
        "traces",
        "alerts",
        "data_quality",
        "feature_drift",
        "output_drift",
        "multivariate_drift",
    )


def test_monitoring_features_follow_the_loaded_registry() -> None:
    registry = MetricRegistry([DataQualityMetric(), MultivariateDriftMetric()])

    assert monitoring_features(registry) == (
        "runtime",
        "traces",
        "alerts",
        "data_quality",
        "multivariate_drift",
    )
