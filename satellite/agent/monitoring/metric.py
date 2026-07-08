from abc import ABC, abstractmethod
from dataclasses import dataclass

from agent.monitoring.models import (
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    TimeWindow,
)


@dataclass(frozen=True)
class MetricInput:
    context: DeploymentContext
    events: list[InferenceEvent]
    window: TimeWindow

    @property
    def profile(self) -> dict | None:
        return self.context.profile


class Metric(ABC):
    """A registered unit of monitoring: declares what it needs, computes over a window.

    ``metric`` is the group id written to ``monitoring_results`` (e.g. ``runtime``).
    ``applies`` is the requirements/applicability check the worker uses for selection;
    ``compute`` produces the metric values, a severity, and any threshold breaches.
    """

    metric: str

    @abstractmethod
    def applies(self, context: DeploymentContext) -> bool: ...

    @abstractmethod
    def compute(self, data: MetricInput) -> MetricComputation: ...
