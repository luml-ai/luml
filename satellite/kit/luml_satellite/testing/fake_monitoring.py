from collections.abc import Sequence

from luml_satellite.wire import Deployment

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
    def __init__(
        self,
        features: Sequence[str] = DEFAULT_MONITORING_FEATURES,
        *,
        link_prefix: str = "/deployments",
    ) -> None:
        self._features = tuple(features)
        self._link_prefix = link_prefix.rstrip("/")
        self.started = False
        self.closed = False

    @property
    def monitoring_features(self) -> tuple[str, ...]:
        return self._features

    def monitoring_link(self, deployment: Deployment) -> str | None:
        if deployment.monitoring_mode.strip().lower() == "off":
            return None
        return f"{self._link_prefix}/{deployment.id}/monitoring"

    async def start(self) -> None:
        self.started = True

    async def aclose(self) -> None:
        self.closed = True
