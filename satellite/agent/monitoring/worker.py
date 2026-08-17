import asyncio
import logging
import math
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from agent.monitoring.health import WorkerHealth
from agent.monitoring.metric import Metric, MetricInput
from agent.monitoring.models import (
    Alert,
    AlertSignal,
    AlertState,
    DeploymentContext,
    InferenceEvent,
    MetricComputation,
    MetricResult,
    MonitoredDeployment,
    TimeWindow,
)
from agent.monitoring.registry import MetricRegistry
from agent.monitoring.store import MonitoringStore
from agent.schemas import LocalDeployment

logger = logging.getLogger("satellite")

DeploymentProvider = Callable[[], list[MonitoredDeployment]]
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
    ) -> None:
        self._store = store
        self._registry = registry
        self._provider = provider
        self._window_seconds = window_seconds
        self._interval_seconds = interval_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        # The worker swallows per-metric failures on purpose; the counters are what makes
        # that survivable — an empty tab and a broken metric look identical otherwise.
        self._health = health
        # How far back a restarted worker may catch up. Without a bound, an agent that was
        # down over the weekend would replay hundreds of windows on its first tick; the
        # events behind them expire anyway.
        self._max_backfill_windows = max(1, max_backfill_windows)
        self._stopped = False

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
        for deployment in self._provider():
            for window in await self._pending_windows(deployment.deployment_id, latest):
                await self._process_deployment(deployment, window)
        if self._health is not None:
            self._health.tick_finished(moment)

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
            # A deployment that has never been materialized starts from the present rather
            # than replaying however much history the database happens to hold.
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
            # Storage unavailable: skip this deployment's window, retried next interval.
            logger.warning(
                f"[monitoring] storage read failed for {deployment.deployment_id}: {error}"
            )
            if self._health is not None:
                self._health.metric_failed(
                    deployment.deployment_id, "storage", str(error), self._clock()
                )
            return

        context = DeploymentContext(
            deployment_id=deployment.deployment_id,
            profile=deployment.profile,
            has_events=bool(events),
        )
        active_by_metric = {alert.metric: alert for alert in active_alerts}
        if self._health is not None:
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
                # A failing metric is isolated and does not stop the others.
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
            MetricInput(
                context=context, events=events, window=window, open_signals=open_signals
            )
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
        if self._health is None:
            return
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
            profile_status="ready" if context.has_profile else "absent",
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


def monitored_deployments(
    local_deployments: Iterable[LocalDeployment],
) -> list[MonitoredDeployment]:
    """Select the deployments the worker should process — those with monitoring on."""
    return [
        MonitoredDeployment(
            deployment_id=deployment.deployment_id, profile=deployment.reference_profile
        )
        for deployment in local_deployments
        if deployment.monitoring_enabled
    ]
