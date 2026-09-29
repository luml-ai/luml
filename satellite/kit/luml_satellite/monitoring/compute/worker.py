import asyncio
import inspect
import logging
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from luml_satellite.monitoring.compute.health import WorkerHealth
from luml_satellite.monitoring.compute.heartbeat import WorkerHeartbeat, deployment_shard
from luml_satellite.monitoring.compute.metric import Metric, MetricInput
from luml_satellite.monitoring.compute.models import (
    Alert,
    AlertSignal,
    AlertState,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MetricResult,
    MonitoredDeployment,
    TimeWindow,
    monitored_deployments as monitored_deployments,
)
from luml_satellite.monitoring.compute.registry import MetricRegistry
from luml_satellite.monitoring.storage.store import MonitoringStore

logger = logging.getLogger("satellite")

type DeploymentProvider = Callable[
    [], list[MonitoredDeployment] | Awaitable[list[MonitoredDeployment]]
]
Clock = Callable[[], datetime]


class MonitoringWorker:
    """Shared per-Satellite loop: each tick, run the applicable registry metrics for
    every monitored deployment over its latest completed window and materialize the
    results and alert state. Strictly off the inference path and best-effort — a
    failing metric is isolated and a storage failure only skips that window.
    """

    def __init__(
        self,
        *,
        store: MonitoringStore,
        registry: MetricRegistry,
        provider: DeploymentProvider,
        window_seconds: float,
        interval_seconds: float,
        clock: Clock | None = None,
        health: WorkerHealth | None = None,
        max_backfill_windows: int = 12,
        shard_index: int = 0,
        shard_count: int = 1,
        heartbeat_file: Path | str | None = None,
    ) -> None:
        if shard_count <= 0:
            raise ValueError("shard_count must be greater than zero")
        if not 0 <= shard_index < shard_count:
            raise ValueError("shard_index must be within shard_count")
        self._store = store
        self._registry = registry
        self._provider = provider
        self._window_seconds = window_seconds
        self._interval_seconds = interval_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._health = health or WorkerHealth()
        self._max_backfill_windows = max(1, max_backfill_windows)
        self._shard_index = shard_index
        self._shard_count = shard_count
        self._heartbeat_file = Path(heartbeat_file) if heartbeat_file is not None else None
        self._stopped = False

    @property
    def health(self) -> WorkerHealth:
        return self._health

    def stop(self) -> None:
        self._stopped = True

    def latest_window(self, now: datetime) -> TimeWindow:
        """The most recent fully-elapsed window, aligned to the window grid."""
        width = self._window_seconds
        boundary = math.floor(now.timestamp() / width) * width
        return TimeWindow(
            start=datetime.fromtimestamp(boundary - width, UTC),
            end=datetime.fromtimestamp(boundary, UTC),
        )

    async def tick(self, now: datetime | None = None) -> None:
        moment = now or self._clock()
        latest = self.latest_window(moment)
        deployments = await self._load_deployments()
        selected = [
            deployment
            for deployment in deployments
            if deployment_shard(deployment.deployment_id, self._shard_count) == self._shard_index
        ]
        for deployment in selected:
            for window in await self._pending_windows(deployment.deployment_id, latest):
                await self._process_deployment(deployment, window)
        self._health.tick_finished(moment)
        heartbeat = WorkerHeartbeat(
            shard_index=self._shard_index,
            shard_count=self._shard_count,
            tick_at=moment,
            window_seconds=self._window_seconds,
            interval_seconds=self._interval_seconds,
            deployments={
                deployment.deployment_id: self._health.for_deployment(deployment.deployment_id)
                for deployment in selected
            },
        )
        try:
            await self._store.write_worker_heartbeat(heartbeat)
        except Exception as error:  # noqa: BLE001 - a stale probe must expose this failure
            logger.warning(f"[monitoring] heartbeat write failed: {error}")
        else:
            self._touch_heartbeat_file()

    async def _load_deployments(self) -> list[MonitoredDeployment]:
        result = self._provider()
        if inspect.isawaitable(result):
            return await result
        return result

    def _touch_heartbeat_file(self) -> None:
        if self._heartbeat_file is None:
            return
        self._heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        self._heartbeat_file.touch()

    async def _pending_windows(self, deployment_id: str, latest: TimeWindow) -> list[TimeWindow]:
        """Every complete window still missing for this deployment, oldest first.

        Normally that is just the latest one. After a gap — the agent was down, or a tick
        took longer than an interval — the windows in between are still worth computing:
        the events are there, and nothing else will ever go back for them.
        """
        try:
            done_through = await self._store.last_materialized_window(deployment_id)
        except Exception as error:  # noqa: BLE001 — catching up is best-effort
            logger.warning(f"[monitoring] backfill check failed for {deployment_id}: {error}")
            return [latest]
        if done_through is None or done_through >= latest.end:
            return [] if done_through is not None and done_through >= latest.end else [latest]

        width = self._window_seconds
        missing: list[TimeWindow] = []
        end = latest.end
        while end > done_through and len(missing) < self._max_backfill_windows:
            missing.append(
                TimeWindow(start=datetime.fromtimestamp(end.timestamp() - width, UTC), end=end)
            )
            end = datetime.fromtimestamp(end.timestamp() - width, UTC)
        return list(reversed(missing))

    async def run_forever(self) -> None:
        logger.info("[monitoring] starting monitoring worker...")
        while not self._stopped:
            try:
                await self.tick()
            except Exception as error:
                logger.warning(f"[monitoring] tick error: {error}")
            await asyncio.sleep(self._interval_seconds)

    async def _process_deployment(
        self, deployment: MonitoredDeployment, window: TimeWindow
    ) -> None:
        try:
            events = await self._store.read_events(deployment.deployment_id, window)
            active_alerts = await self._store.active_alerts(deployment.deployment_id)
        except Exception as error:
            logger.warning(
                f"[monitoring] storage read failed for {deployment.deployment_id}: {error}"
            )
            self._health.metric_failed(
                deployment.deployment_id, "storage", str(error), self._clock()
            )
            return

        context = DeploymentContext(
            deployment_id=deployment.deployment_id,
            profile=deployment.profile,
            has_events=bool(events),
            profile_status=deployment.effective_profile_status,
        )
        active_by_metric = {alert.metric: alert for alert in active_alerts}
        self._health.metric_recovered(deployment.deployment_id, "storage")
        self._health.window_processed(deployment.deployment_id, window.end, self._clock())

        for metric in self._registry.metrics():
            if not metric.applies(context):
                continue
            try:
                await self._run_metric(
                    metric, deployment, context, events, window, active_by_metric
                )
                await self._note_transition(
                    deployment.deployment_id, metric.metric, window, failing=False
                )
            except Exception as error:
                logger.warning(
                    f"[monitoring] metric '{metric.metric}' failed for "
                    f"{deployment.deployment_id}: {error}"
                )
                await self._note_transition(
                    deployment.deployment_id,
                    metric.metric,
                    window,
                    failing=True,
                    error=str(error),
                )

    async def _run_metric(
        self,
        metric: Metric,
        deployment: MonitoredDeployment,
        context: DeploymentContext,
        events: list[InferenceEvent],
        window: TimeWindow,
        active_by_metric: dict[str, Alert],
    ) -> None:
        prefix = f"{metric.metric}:"
        open_signals = frozenset(
            key[len(prefix) :]
            for key, alert in active_by_metric.items()
            if key.startswith(prefix) and alert.state != AlertState.RESOLVED
        )
        computation = metric.compute(
            MetricInput(context=context, events=events, window=window, open_signals=open_signals)
        )
        await self._materialize(deployment, metric.metric, computation, window, context)
        await self._reconcile_alerts(
            deployment.deployment_id, metric.metric, computation.signals, window, active_by_metric
        )

    async def _note_transition(
        self,
        deployment_id: str,
        metric: str,
        window: TimeWindow,
        *,
        failing: bool,
        error: str = "",
    ) -> None:
        """Keep the metric's live state, and persist the moment it changes.

        Only the change is written: a metric broken all day is one row, not one per tick,
        and the rows then read as incidents. The in-memory state is what makes that
        possible — after a restart it is empty, so the first failure that follows opens a
        new incident, which is the honest reading of a process that just came back.
        """
        was_failing = any(
            failure.metric == metric
            for failure in self._health.for_deployment(deployment_id).failures
        )
        at = self._clock()
        if failing:
            self._health.metric_failed(deployment_id, metric, error, at)
        else:
            self._health.metric_recovered(deployment_id, metric)
        if failing == was_failing:
            return
        try:
            await self._store.record_metric_transition(
                deployment_id,
                metric,
                kind="failed" if failing else "recovered",
                error=error,
                window_end=window.end,
                at=at,
            )
        except Exception as write_error:  # noqa: BLE001 — history must not break the tick
            logger.warning(f"[monitoring] could not record metric history: {write_error}")

    async def _materialize(
        self,
        deployment: MonitoredDeployment,
        group: str,
        computation: MetricComputation,
        window: TimeWindow,
        context: DeploymentContext,
    ) -> None:
        result = MetricResult(
            deployment_id=deployment.deployment_id,
            metric=group,
            window_start=window.start,
            window_end=window.end,
            values=computation.values,
            severity=computation.severity,
            profile_status=context.effective_profile_status,
        )
        await self._store.write_result(result)

    async def _reconcile_alerts(
        self,
        deployment_id: str,
        group: str,
        signals: list[AlertSignal],
        window: TimeWindow,
        active_by_metric: dict[str, Alert],
    ) -> None:
        prefix = f"{group}:"
        signaled: set[str] = set()

        for signal in signals:
            metric_key = f"{group}:{signal.key}"
            signaled.add(metric_key)
            alert = self._open_or_update(
                deployment_id, metric_key, signal, window, active_by_metric
            )
            active_by_metric[metric_key] = alert
            await self._store.save_alert(alert)

        for metric_key, alert in list(active_by_metric.items()):
            if not metric_key.startswith(prefix) or metric_key in signaled:
                continue
            if alert.state != AlertState.RESOLVED:
                alert.state = AlertState.RESOLVED
                alert.last_seen = window.end
                await self._store.save_alert(alert)

    @staticmethod
    def _open_or_update(
        deployment_id: str,
        metric_key: str,
        signal: AlertSignal,
        window: TimeWindow,
        active_by_metric: dict[str, Alert],
    ) -> Alert:
        existing = active_by_metric.get(metric_key)
        if existing is None or existing.state == AlertState.RESOLVED:
            return Alert(
                deployment_id=deployment_id,
                metric=metric_key,
                current_value=signal.current_value,
                threshold=signal.threshold,
                severity=signal.severity,
                state=AlertState.OPEN,
                first_seen=window.end,
                last_seen=window.end,
            )
        existing.current_value = signal.current_value
        existing.threshold = signal.threshold
        existing.severity = signal.severity
        existing.last_seen = window.end
        if existing.state != AlertState.ACKNOWLEDGED:
            existing.state = AlertState.OPEN
        return existing
