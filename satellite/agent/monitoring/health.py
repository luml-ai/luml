"""Whether monitoring itself is working.

Every metric the dashboard shows is produced by the worker in the background, and the
worker is deliberately silent: a failing metric is caught, logged and skipped so it cannot
take the others down with it. That is the right behaviour for inference, and a bad one for
trust — an empty chart looks the same whether the traffic was clean or the metric has been
throwing for an hour. This module keeps the little that is needed to tell those apart.

State lives in memory: it describes the running process, and a restart is exactly the event
after which the previous numbers stop being true.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class MetricFailure:
    metric: str
    error: str
    at: datetime


@dataclass(frozen=True)
class DeploymentHealth:
    """What the worker has managed to do for one deployment."""

    windows_processed: int = 0
    last_window_end: datetime | None = None
    last_processed_at: datetime | None = None
    # Time between the window closing and the worker materializing it.
    last_lag_seconds: float | None = None
    failures: tuple[MetricFailure, ...] = ()


@dataclass(frozen=True)
class HealthSnapshot:
    running: bool
    last_tick_at: datetime | None
    deployment: DeploymentHealth


@dataclass
class WorkerHealth:
    """Live counters for the monitoring worker, read by the Query API."""

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_tick_at: datetime | None = None
    ticks: int = 0
    _deployments: dict[str, DeploymentHealth] = field(default_factory=dict)

    def tick_finished(self, at: datetime) -> None:
        self.ticks += 1
        self.last_tick_at = at

    def window_processed(self, deployment_id: str, window_end: datetime, at: datetime) -> None:
        current = self._deployments.get(deployment_id, DeploymentHealth())
        self._deployments[deployment_id] = DeploymentHealth(
            windows_processed=current.windows_processed + 1,
            last_window_end=window_end,
            last_processed_at=at,
            last_lag_seconds=max(0.0, (at - window_end).total_seconds()),
            failures=current.failures,
        )

    def metric_failed(self, deployment_id: str, metric: str, error: str, at: datetime) -> None:
        """Remember the last failure per metric — the newest message is the useful one."""
        current = self._deployments.get(deployment_id, DeploymentHealth())
        kept = tuple(failure for failure in current.failures if failure.metric != metric)
        self._deployments[deployment_id] = DeploymentHealth(
            windows_processed=current.windows_processed,
            last_window_end=current.last_window_end,
            last_processed_at=current.last_processed_at,
            last_lag_seconds=current.last_lag_seconds,
            failures=(*kept, MetricFailure(metric=metric, error=error[:500], at=at)),
        )

    def metric_recovered(self, deployment_id: str, metric: str) -> None:
        current = self._deployments.get(deployment_id)
        if current is None or not current.failures:
            return
        kept = tuple(failure for failure in current.failures if failure.metric != metric)
        if len(kept) != len(current.failures):
            self._deployments[deployment_id] = DeploymentHealth(
                windows_processed=current.windows_processed,
                last_window_end=current.last_window_end,
                last_processed_at=current.last_processed_at,
                last_lag_seconds=current.last_lag_seconds,
                failures=kept,
            )

    def for_deployment(self, deployment_id: str) -> DeploymentHealth:
        return self._deployments.get(deployment_id, DeploymentHealth())

    def snapshot(self, deployment_id: str) -> HealthSnapshot:
        """Process-level liveness plus what has been done for one deployment."""
        return HealthSnapshot(
            running=self.last_tick_at is not None,
            last_tick_at=self.last_tick_at,
            deployment=self.for_deployment(deployment_id),
        )


# One per process, like the deployment handler: the worker writes it, the API reads it.
worker_health = WorkerHealth()
