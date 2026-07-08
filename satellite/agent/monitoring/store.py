from collections.abc import Iterable
from typing import Protocol

from agent.monitoring.models import (
    Alert,
    AlertState,
    InferenceEvent,
    MetricResult,
    TimeWindow,
)


class MonitoringStore(Protocol):
    """Reads collected data and materializes results / alert state for the worker."""

    async def read_events(self, deployment_id: str, window: TimeWindow) -> list[InferenceEvent]: ...

    async def write_result(self, result: MetricResult) -> None: ...

    async def active_alerts(self, deployment_id: str) -> list[Alert]: ...

    async def save_alert(self, alert: Alert) -> None: ...


class InMemoryMonitoringStore:
    """In-process store used for tests and as a dependency-free default."""

    def __init__(self) -> None:
        self.events: dict[str, list[InferenceEvent]] = {}
        self.results: list[MetricResult] = []
        self.alerts: dict[tuple[str, str], Alert] = {}

    def add_events(self, deployment_id: str, events: Iterable[InferenceEvent]) -> None:
        self.events.setdefault(deployment_id, []).extend(events)

    async def read_events(self, deployment_id: str, window: TimeWindow) -> list[InferenceEvent]:
        return [e for e in self.events.get(deployment_id, []) if window.contains(e.timestamp)]

    async def write_result(self, result: MetricResult) -> None:
        self.results.append(result)

    async def active_alerts(self, deployment_id: str) -> list[Alert]:
        return [
            alert
            for (dep_id, _), alert in self.alerts.items()
            if dep_id == deployment_id and alert.state != AlertState.RESOLVED
        ]

    async def save_alert(self, alert: Alert) -> None:
        self.alerts[(alert.deployment_id, alert.metric)] = alert
