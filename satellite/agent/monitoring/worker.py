import asyncio
import logging
import math
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

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
    ) -> None:
        self._store = store
        self._registry = registry
        self._provider = provider
        self._window_seconds = window_seconds
        self._interval_seconds = interval_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
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
        window = self.latest_window(now or self._clock())
        for deployment in self._provider():
            await self._process_deployment(deployment, window)

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
            return

        context = DeploymentContext(
            deployment_id=deployment.deployment_id,
            profile=deployment.profile,
            has_events=bool(events),
        )
        active_by_metric = {alert.metric: alert for alert in active_alerts}

        for metric in self._registry.metrics():
            if not metric.applies(context):
                continue
            try:
                await self._run_metric(
                    metric, deployment, context, events, window, active_by_metric
                )
            except Exception as error:
                # A failing metric is isolated and does not stop the others.
                logger.warning(
                    f"[monitoring] metric '{metric.metric}' failed for "
                    f"{deployment.deployment_id}: {error}"
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
        computation = metric.compute(MetricInput(context=context, events=events, window=window))
        await self._materialize(deployment, metric.metric, computation, window, context)
        await self._reconcile_alerts(
            deployment.deployment_id, metric.metric, computation.signals, window, active_by_metric
        )

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
