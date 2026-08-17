from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from agent.monitoring.models import (
    Alert,
    AlertState,
    InferenceEvent,
    MetricResult,
    MetricTransition,
    TimeWindow,
)


class MonitoringStore(Protocol):
    """Reads collected data and materializes results / alert state for the worker."""

    async def read_events(self, deployment_id: str, window: TimeWindow) -> list[InferenceEvent]: ...

    async def write_result(self, result: MetricResult) -> None: ...

    async def active_alerts(self, deployment_id: str) -> list[Alert]: ...

    async def save_alert(self, alert: Alert) -> None: ...

    async def record_metric_transition(
        self,
        deployment_id: str,
        metric: str,
        *,
        kind: str,
        error: str,
        window_end: datetime,
        at: datetime,
    ) -> None:
        """Append a ``failed`` / ``recovered`` entry to a metric's history."""
        ...

    async def fetch_metric_transitions(
        self, deployment_id: str, since: datetime
    ) -> list[MetricTransition]: ...

    async def last_materialized_window(self, deployment_id: str) -> datetime | None:
        """End of the newest window already materialized, or ``None`` for a fresh deployment.

        This is what lets the worker catch up after a restart: the answer survives the
        process, the in-memory counters do not.
        """
        ...


class InMemoryMonitoringStore:
    """In-process store used for tests and as a dependency-free default."""

    def __init__(self) -> None:
        self.events: dict[str, list[InferenceEvent]] = {}
        self.results: list[MetricResult] = []
        self.alerts: dict[tuple[str, str], Alert] = {}
        self.transitions: dict[str, list[MetricTransition]] = {}

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

    async def last_materialized_window(self, deployment_id: str) -> datetime | None:
        ends = [r.window_end for r in self.results if r.deployment_id == deployment_id]
        return max(ends, default=None)

    async def record_metric_transition(
        self,
        deployment_id: str,
        metric: str,
        *,
        kind: str,
        error: str,
        window_end: datetime,
        at: datetime,
    ) -> None:
        self.transitions.setdefault(deployment_id, []).append(
            MetricTransition(metric=metric, kind=kind, error=error, at=at)
        )

    async def fetch_metric_transitions(
        self, deployment_id: str, since: datetime
    ) -> list[MetricTransition]:
        return [t for t in self.transitions.get(deployment_id, []) if t.at >= since]

    async def save_alert(self, alert: Alert) -> None:
        self.alerts[(alert.deployment_id, alert.metric)] = alert
