from collections.abc import Sequence

DEFAULT_MONITORING_FEATURES = (
    "runtime",
    "traces",
    "alerts",
    "data_quality",
    "feature_drift",
    "output_drift",
    "multivariate_drift",
)


class FakeMonitoringBundle:
    def __init__(self, features: Sequence[str] = DEFAULT_MONITORING_FEATURES) -> None:
        self._features = tuple(features)

    @property
    def monitoring_features(self) -> tuple[str, ...]:
        return self._features
