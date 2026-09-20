"""Chart-ready read logic for the Monitoring Query API.

Turns the store's rows into already-aggregated, render-ready contracts — the UI does no
metric math. ``deployment_id`` always comes from the caller (the dashboard session), never
from client input.
"""

import json
import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import time
from typing import Any
from uuid import UUID

from luml_satellite.monitoring.compute import thresholds
from luml_satellite.monitoring.compute.health import HealthSnapshot
from luml_satellite.monitoring.compute.heartbeat import WorkerHeartbeat
from luml_satellite.monitoring.dashboard.alerts import (
    COUNT,
    format_value,
    history_value,
    parse_alert_key,
    threshold_key,
)
from luml_satellite.monitoring.dashboard.schemas import (
    AlertBanner,
    AlertGroup,
    AlertsResponse,
    Card,
    ClassShift,
    Compare,
    ConfidenceBlock,
    DataQualityFeatureRow,
    DataQualityResponse,
    DistributionBin,
    DriftedFeature,
    FeatureDistribution,
    FeatureDriftDetail,
    FeatureDriftResponse,
    Granularity,
    HeaderResponse,
    HorizonDrift,
    InvalidValueSummary,
    MetricFailure,
    MetricIncident,
    ModelKind,
    MultivariatePanel,
    OutputDriftResponse,
    OverviewResponse,
    PcaPoint,
    ProbabilityBlock,
    ProfileStatus,
    ReferenceProfileFeature,
    ReferenceProfileResponse,
    RuntimeBaseline,
    RuntimeResponse,
    SectionState,
    Series,
    SeriesPoint,
    Severity,
    SeverityFilter,
    SortOrder,
    StatusBreakdownRow,
    TraceDetail,
    TraceDetailResponse,
    TraceRow,
    TraceSort,
    TraceSpan,
    TracesResponse,
    UnseenCategoryCount,
    Window,
    WorkerHealthResponse,
)
from luml_satellite.monitoring.storage.query_store import (
    EventStatus,
    InferenceEvent,
    MonitoringStore,
    MonitoringStoreUnavailable,
    ReferenceFeatureProfile,
    SpanRecord,
    StoredAlert,
    StoredMetricResult,
)

# Reads the worker's counters for one deployment plus its (window, interval) cadence.
HealthSource = Callable[[UUID], tuple["HealthSnapshot", tuple[float, float]]]

GROUP_RUNTIME = "runtime"
GROUP_DATA_QUALITY = "data_quality"

# Checks in the order the detail panel lists them, with the wording the table uses.
_QUALITY_CHECKS: tuple[tuple[str, str], ...] = (
    ("missing", "Missing"),
    ("type_mismatch", "Type errors"),
    ("range_violation", "Out of range"),
    ("unseen_category", "Unseen categories"),
)
GROUP_FEATURE_DRIFT = "feature_drift"
GROUP_OUTPUT_DRIFT = "output_drift"
GROUP_MULTIVARIATE = "multivariate"

_WINDOW_SECONDS: dict[Window, int] = {
    Window.H24: 24 * 3600,
    Window.D7: 7 * 24 * 3600,
    Window.D30: 30 * 24 * 3600,
}

_AUTO_BUCKET_SECONDS: dict[Window, int] = {
    Window.H24: 900,
    Window.D7: 6 * 3600,
    Window.D30: 24 * 3600,
}

_BUCKET_LADDER = (30, 60, 120, 300, 900, 1800, 3600, 6 * 3600, 12 * 3600, 24 * 3600)

_TARGET_BUCKETS = 40
_ZOOM_SPAN_SHARE = 0.5

_BANNER_LIMIT = 5
_TOP_DRIFTED_LIMIT = 10

_INCIDENT_WINDOW = 7 * 24 * 3600
_ALERT_GROUP_ORDER = (
    GROUP_RUNTIME,
    GROUP_DATA_QUALITY,
    GROUP_FEATURE_DRIFT,
    GROUP_OUTPUT_DRIFT,
    GROUP_MULTIVARIATE,
)

TRACES_DEFAULT_LIMIT = 50
TRACES_MAX_LIMIT = 200
_TRACE_SUMMARY_MAX_LEN = 200
_TRACE_SUMMARY_MAX_KEYS = 8


@dataclass(frozen=True)
class QueryDimensions:
    window: Window = Window.H24
    compare: Compare = Compare.REFERENCE
    severity: SeverityFilter = SeverityFilter.ALL
    granularity: Granularity = Granularity.AUTO
    feature: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    compare_start: datetime | None = None
    compare_end: datetime | None = None

    @property
    def is_custom_range(self) -> bool:
        return self.start is not None and self.end is not None

    def span_seconds(self) -> int:
        if self.start is not None and self.end is not None:
            return max(1, int((self.end - self.start).total_seconds()))
        return _WINDOW_SECONDS[self.window]


@dataclass(frozen=True)
class _Rollup:
    request_count: int
    success_count: int
    error_count: int
    timeout_count: int
    failed_inference_count: int
    error_rate: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_max_ms: float | None
    status_breakdown: tuple[StatusBreakdownRow, ...] = ()

    @property
    def success_rate(self) -> float:
        """Kept beside ``error_rate`` rather than derived in the UI, which does no math.

        An empty window is 0%, not 100%: nothing succeeded, and reading it as a perfect
        window would be the wrong headline for a deployment nobody called.
        """
        return self.success_count / self.request_count if self.request_count else 0.0


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _rollup(events: list[InferenceEvent]) -> _Rollup:
    total = len(events)
    success = sum(1 for e in events if e.status == EventStatus.SUCCESS)
    latencies = [e.latency_ms for e in events]
    return _Rollup(
        request_count=total,
        success_count=success,
        error_count=sum(1 for e in events if e.status == EventStatus.ERROR),
        timeout_count=sum(1 for e in events if e.status == EventStatus.TIMEOUT),
        failed_inference_count=sum(1 for e in events if e.status == EventStatus.FAILED_INFERENCE),
        error_rate=(total - success) / total if total else 0.0,
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        latency_max_ms=max(latencies) if latencies else None,
        status_breakdown=_status_breakdown(events),
    )


def _status_breakdown(events: list[InferenceEvent]) -> tuple[StatusBreakdownRow, ...]:
    """Group the window's calls by outcome and HTTP code, busiest row first.

    Outcome and code are kept as separate columns rather than one label: the same code
    carries different meaning per outcome (a 504 is a timeout, a 500 a failed inference),
    and a reader scanning for what broke wants both.
    """
    counts: dict[tuple[str, int | None], int] = defaultdict(int)
    for event in events:
        counts[(str(event.status), event.status_code)] += 1
    total = len(events)
    rows = [
        StatusBreakdownRow(
            status=status,
            status_code=code,
            count=count,
            share=count / total if total else 0.0,
        )
        for (status, code), count in counts.items()
    ]
    rows.sort(key=lambda row: (-row.count, row.status, row.status_code or 0))
    return tuple(rows)


def _bucket_seconds(dims: QueryDimensions) -> int:
    span = dims.span_seconds()
    if dims.granularity is Granularity.HOUR:
        bucket = 3600
    elif dims.granularity is Granularity.DAY:
        bucket = 24 * 3600
    elif dims.is_custom_range:
        bucket = next((b for b in _BUCKET_LADDER if span / b <= 96), _BUCKET_LADDER[-1])
    else:
        bucket = _AUTO_BUCKET_SECONDS[dims.window]
    return min(bucket, span)


def _series_layout(
    events: list[InferenceEvent],
    window_start: datetime,
    dims: QueryDimensions,
) -> tuple[datetime, int, int]:
    """Where the runtime series starts, how wide its buckets are, and how many there are.

    On automatic granularity the layout follows the data, not just the selected window: a
    deployment that served a burst of traffic ten minutes ago, or serves a handful of calls
    a day, would otherwise land entirely in one window-sized bucket — a single point, which
    a line chart cannot draw. When the events cover only a small part of the window the
    series zooms to their span and picks the smallest bucket from :data:`_BUCKET_LADDER`
    that keeps the point count sane; traffic spread across the window keeps the plain
    window-wide layout, and an explicitly chosen granularity is always honoured.
    """
    window_seconds = dims.span_seconds()
    bucket = _bucket_seconds(dims)
    full_window = (window_start, bucket, math.ceil(window_seconds / bucket))

    if dims.granularity is not Granularity.AUTO:
        return full_window

    stamps = sorted(event.ts for event in events if event.ts is not None)
    if not stamps:
        return full_window

    span = (stamps[-1] - stamps[0]).total_seconds()
    if span >= window_seconds * _ZOOM_SPAN_SHARE:
        return full_window

    zoom = _ladder_bucket(max(span, 1.0) / _TARGET_BUCKETS)
    if zoom >= bucket:
        return full_window

    start = _floor_to(stamps[0], zoom)
    n_buckets = math.floor((stamps[-1] - start).total_seconds() / zoom) + 1
    return start, zoom, n_buckets


def _ladder_bucket(seconds: float) -> int:
    """Smallest human-readable bucket at least ``seconds`` wide."""
    for candidate in _BUCKET_LADDER:
        if candidate >= seconds:
            return candidate
    return _BUCKET_LADDER[-1]


def _floor_to(moment: datetime, bucket_seconds: int) -> datetime:
    epoch_seconds = moment.timestamp()
    return datetime.fromtimestamp(
        epoch_seconds - (epoch_seconds % bucket_seconds), tz=moment.tzinfo or UTC
    )


def _runtime_series(
    events: list[InferenceEvent], start: datetime, bucket_seconds: int, n_buckets: int
) -> list[Series]:
    buckets: list[list[InferenceEvent]] = [[] for _ in range(n_buckets)]
    for event in events:
        index = int((event.ts - start).total_seconds() // bucket_seconds)
        buckets[min(max(index, 0), n_buckets - 1)].append(event)

    stamps = [start + timedelta(seconds=i * bucket_seconds) for i in range(n_buckets)]
    requests, error_rate, latency = [], [], []
    for stamp, bucket in zip(stamps, buckets, strict=True):
        count = len(bucket)
        successes = sum(1 for e in bucket if e.status == EventStatus.SUCCESS)
        requests.append(SeriesPoint(t=stamp, value=float(count)))
        error_rate.append(
            SeriesPoint(t=stamp, value=(count - successes) / count if count else None)
        )
        latency.append(SeriesPoint(t=stamp, value=_percentile([e.latency_ms for e in bucket], 95)))
    return [
        Series(key="requests", label="Requests", points=requests),
        Series(key="error_rate", label="Error rate", unit="ratio", points=error_rate),
        Series(key="latency_p95", label="Latency p95", unit="ms", points=latency),
    ]


def _severity_matches(severity: str, chosen: SeverityFilter) -> bool:
    if chosen is SeverityFilter.ALL:
        return True
    return severity == chosen.value


def _alert_banner(
    alert: StoredAlert,
    history: Series | None = None,
    profile: dict[str, Any] | None = None,
) -> AlertBanner:
    """One alert as the dashboard shows it: what fired, by how much, for how long."""
    parsed = parse_alert_key(alert.metric)
    key = threshold_key(parsed)
    source = thresholds.PROFILE if key and thresholds.defines(profile, key) else thresholds.DEFAULT
    value_label = format_value(alert.current_value, parsed.unit)
    threshold_label = format_value(alert.threshold, parsed.unit)
    message = alert.message or (
        f"{value_label} in this window"
        if parsed.unit == COUNT
        else f"{parsed.label} {value_label} vs threshold {threshold_label}"
    )
    return AlertBanner(
        group=alert.group,
        metric=alert.metric,
        feature=alert.feature,
        severity=Severity(alert.severity),
        current_value=alert.current_value,
        threshold=alert.threshold,
        message=message,
        first_seen=alert.first_seen,
        last_seen=alert.last_seen,
        label=parsed.label,
        unit=parsed.unit,
        value_label=value_label,
        threshold_label=threshold_label,
        state=alert.state,
        duration_seconds=_alert_duration(alert),
        threshold_source=source,
        history=history,
    )


def _alert_duration(alert: StoredAlert) -> float | None:
    if alert.first_seen is None or alert.last_seen is None:
        return None
    return max(0.0, (alert.last_seen - alert.first_seen).total_seconds())


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


class MonitoringQueryService:
    """Assembles the Query API contracts from a :class:`MonitoringStore`."""

    def __init__(
        self,
        store: MonitoringStore,
        clock: Callable[[], float] = time,
        health_source: HealthSource | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._health_source = health_source

    def _window_bounds(self, dims: QueryDimensions) -> tuple[datetime, datetime]:
        if dims.start is not None and dims.end is not None:
            return dims.start, dims.end
        end = datetime.fromtimestamp(self._clock(), tz=UTC)
        return end - timedelta(seconds=_WINDOW_SECONDS[dims.window]), end

    def _baseline_bounds(self, dims: QueryDimensions) -> tuple[datetime, datetime] | None:
        """The comparison period, or None when no comparison is on.

        PREVIOUS is the same span butted right up against the current window's start;
        CUSTOM is whatever the caller chose. REFERENCE (and OFF) carry no period: the
        training reference is a distribution, not a stretch of runtime.
        """
        if dims.compare is Compare.PREVIOUS:
            start, _ = self._window_bounds(dims)
            span = timedelta(seconds=dims.span_seconds())
            return start - span, start
        if dims.compare is Compare.CUSTOM and dims.compare_start and dims.compare_end:
            return dims.compare_start, dims.compare_end
        return None

    async def header(self, deployment_id: UUID) -> HeaderResponse:
        try:
            descriptor = await self._store.describe_deployment(deployment_id)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return HeaderResponse(state=SectionState.UNAVAILABLE, deployment_id=deployment_id)
        if descriptor is None:
            return HeaderResponse(
                state=SectionState.EMPTY, deployment_id=deployment_id, profile_status=profile
            )
        return HeaderResponse(
            state=SectionState.OK,
            deployment_id=deployment_id,
            name=descriptor.name,
            status=descriptor.status,
            task_type=descriptor.task_type,
            model_kind=ModelKind(descriptor.model_kind),
            model_name=descriptor.model_name,
            environment=descriptor.environment,
            satellite=descriptor.satellite,
            inference_url=descriptor.inference_url,
            last_prediction_at=descriptor.last_prediction_at,
            last_monitored_at=descriptor.last_monitored_at,
            profile_status=profile,
        )

    async def runtime(self, deployment_id: UUID, dims: QueryDimensions) -> RuntimeResponse:
        try:
            rollup, series = await self._runtime(deployment_id, dims)
            baseline_rollup = await self._previous_rollup(deployment_id, dims)
            alerts = await self._banners(
                deployment_id, dims.severity, group=GROUP_RUNTIME, dims=dims
            )
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return RuntimeResponse(state=SectionState.UNAVAILABLE)
        return RuntimeResponse(
            state=SectionState.OK,
            profile_status=profile,
            request_count=rollup.request_count,
            success_count=rollup.success_count,
            success_rate=rollup.success_rate,
            error_count=rollup.error_count,
            error_rate=rollup.error_rate,
            latency_p50_ms=rollup.latency_p50_ms,
            latency_p95_ms=rollup.latency_p95_ms,
            latency_max_ms=rollup.latency_max_ms,
            timeout_count=rollup.timeout_count,
            failed_inference_count=rollup.failed_inference_count,
            status_breakdown=list(rollup.status_breakdown),
            baseline=self._runtime_baseline(baseline_rollup, dims),
            series=series,
            alerts=alerts,
        )

    async def overview(self, deployment_id: UUID, dims: QueryDimensions) -> OverviewResponse:
        try:
            rollup, series = await self._runtime(deployment_id, dims)
            previous = await self._previous_rollup(deployment_id, dims)
            alerts = await self._store.fetch_alerts(deployment_id)
            drift = await self._store.fetch_result(
                deployment_id, GROUP_FEATURE_DRIFT, dims.window.value
            )
            output = await self._store.fetch_result(
                deployment_id, GROUP_OUTPUT_DRIFT, dims.window.value
            )
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return OverviewResponse(state=SectionState.UNAVAILABLE)

        matching = [a for a in alerts if _severity_matches(a.severity, dims.severity)]
        criticals = [a for a in matching if a.severity == Severity.CRITICAL]

        shown = sorted(matching, key=_banner_order)[:_BANNER_LIMIT]
        histories = await self._alert_histories(deployment_id, dims, shown)
        document = await self._profile_document(deployment_id)
        banners = [_alert_banner(a, histories.get(a.metric), document) for a in shown]

        drifted = _drifted_features(drift.values if drift else {})
        top_drifted = sorted(drifted, key=lambda d: d.psi, reverse=True)[:_TOP_DRIFTED_LIMIT]
        drifted_names = [d.feature for d in drifted if d.severity is not Severity.OK]

        cards = _overview_cards(rollup, previous, dims, matching, criticals, drifted_names)
        output_card = _output_drift_card(output)
        if output_card is not None:
            cards.append(output_card)

        return OverviewResponse(
            state=SectionState.OK,
            profile_status=profile,
            cards=cards,
            alert_banners=banners,
            series=series,
            top_drifted_features=top_drifted,
        )

    async def data_quality(self, deployment_id: UUID, dims: QueryDimensions) -> DataQualityResponse:
        try:
            result = await self._store.fetch_result(
                deployment_id, GROUP_DATA_QUALITY, dims.window.value
            )
            alerts = await self._banners(
                deployment_id, dims.severity, group=GROUP_DATA_QUALITY, dims=dims
            )
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return DataQualityResponse(state=SectionState.UNAVAILABLE)
        if result is None:
            return DataQualityResponse(
                state=SectionState.EMPTY, profile_status=profile, alerts=alerts
            )
        rows = _data_quality_rows(result.values, dims.feature)
        baseline_rows = await self._baseline_history(deployment_id, GROUP_DATA_QUALITY, dims)
        if baseline_rows:
            missing = _mean_feature_values(baseline_rows, "missing_rate")
            type_mismatch = _mean_feature_values(baseline_rows, "type_mismatch_rate")
            range_violation = _mean_feature_values(baseline_rows, "range_violation_rate")
            unseen = _mean_feature_values(baseline_rows, "unseen_category_rate")

            def _delta_of(current: float | None, base: float | None) -> float | None:
                return current - base if current is not None and base is not None else None

            rows = [
                row.model_copy(
                    update={
                        "missing_delta": _delta_of(row.missing_rate, missing.get(row.feature)),
                        "type_error_delta": _delta_of(
                            row.type_error_rate, type_mismatch.get(row.feature)
                        ),
                        "range_unseen_delta": _delta_of(
                            row.range_unseen_rate,
                            (
                                max(
                                    v
                                    for v in (
                                        range_violation.get(row.feature),
                                        unseen.get(row.feature),
                                    )
                                    if v is not None
                                )
                                if range_violation.get(row.feature) is not None
                                or unseen.get(row.feature) is not None
                                else None
                            ),
                        ),
                    }
                )
                for row in rows
            ]
        trends = await self._data_quality_trends(deployment_id, dims)
        return DataQualityResponse(
            state=SectionState.OK,
            profile_status=profile,
            features=rows,
            trends=trends,
            alerts=alerts,
            computed_at=result.computed_at,
            stale=self._is_stale(result.computed_at, dims),
        )

    def _is_stale(self, computed_at: datetime | None, dims: QueryDimensions) -> bool:
        """Whether a snapshot's window closed before the selected range began.

        The snapshot tabs read the newest stored window outright, with no time bound —
        deliberately, so a quiet deployment still shows its last known state instead of an
        empty table that reads like "never monitored". The cost is that the reading can be
        older than the range the rest of the page is drawn from, so it has to say so.
        """
        if computed_at is None:
            return False
        start, _ = self._window_bounds(dims)

        if computed_at.tzinfo is None:
            computed_at = computed_at.replace(tzinfo=UTC)
        return computed_at < start

    async def _data_quality_trends(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> list[Series]:
        """Each check of the selected feature across the materialized windows.

        The table answers "is the input broken right now"; these answer "since when" — the
        spec asks for a trend per check, and the worker already stores one result per window.
        """
        feature = dims.feature
        if feature is None:
            return []
        start, _ = self._window_bounds(dims)
        history = await self._store.fetch_result_history(
            deployment_id, GROUP_DATA_QUALITY, dims.window.value, since=start
        )
        series: list[Series] = []
        for check, label in _QUALITY_CHECKS:
            points = [
                SeriesPoint(
                    t=result.computed_at,
                    value=_maybe_float(
                        (result.values.get("features") or {}).get(feature, {}).get(f"{check}_rate")
                    ),
                )
                for result in history
                if result.computed_at is not None
            ]
            measured = [point for point in points if point.value is not None]

            if len(measured) < 2:
                continue
            series.append(Series(key=check, label=label, unit="ratio", points=points))
        return series

    async def feature_drift(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> FeatureDriftResponse:
        try:
            drift = await self._store.fetch_result(
                deployment_id, GROUP_FEATURE_DRIFT, dims.window.value
            )
            multivariate = await self._store.fetch_result(
                deployment_id, GROUP_MULTIVARIATE, dims.window.value
            )
            alerts = await self._banners(
                deployment_id, dims.severity, group=GROUP_FEATURE_DRIFT, dims=dims
            )
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return FeatureDriftResponse(state=SectionState.UNAVAILABLE)

        panel = _multivariate_panel(multivariate, drift)
        if drift is None:
            return FeatureDriftResponse(
                state=SectionState.EMPTY,
                profile_status=profile,
                multivariate=panel,
                alerts=alerts,
            )
        ranked = sorted(_drifted_features(drift.values), key=lambda d: d.psi, reverse=True)
        baseline_psi = _mean_feature_values(
            await self._baseline_history(deployment_id, GROUP_FEATURE_DRIFT, dims), "psi"
        )
        if baseline_psi:
            ranked = [
                one.model_copy(
                    update={
                        "baseline_psi": baseline_psi.get(one.feature),
                        "psi_delta": (
                            one.psi - baseline_psi[one.feature]
                            if one.feature in baseline_psi
                            else None
                        ),
                    }
                )
                for one in ranked
            ]
        selected = _feature_detail(drift.values, dims.feature)
        if selected is not None and selected.psi_over_time is None:
            history = await self._psi_history(deployment_id, dims)
            if history is not None:
                selected = selected.model_copy(update={"psi_over_time": history})
        return FeatureDriftResponse(
            state=SectionState.OK,
            profile_status=profile,
            features=ranked,
            selected=selected,
            multivariate=panel,
            alerts=alerts,
            computed_at=drift.computed_at,
            stale=self._is_stale(drift.computed_at, dims),
        )

    async def output_drift(self, deployment_id: UUID, dims: QueryDimensions) -> OutputDriftResponse:
        try:
            result = await self._store.fetch_result(
                deployment_id, GROUP_OUTPUT_DRIFT, dims.window.value
            )
            alerts = await self._banners(
                deployment_id, dims.severity, group=GROUP_OUTPUT_DRIFT, dims=dims
            )
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return OutputDriftResponse(state=SectionState.UNAVAILABLE)
        if result is None:
            return OutputDriftResponse(
                state=SectionState.EMPTY, profile_status=profile, alerts=alerts
            )

        start, _ = self._window_bounds(dims)
        try:
            history = await self._store.fetch_result_history(
                deployment_id, GROUP_OUTPUT_DRIFT, dims.window.value, since=start
            )
        except MonitoringStoreUnavailable:
            history = []

        values = result.values
        current_psi = _maybe_float(values.get("psi"))
        baseline_rows = await self._baseline_history(deployment_id, GROUP_OUTPUT_DRIFT, dims)
        baseline_psis = [
            value
            for row in baseline_rows
            if (value := _maybe_float(row.values.get("psi"))) is not None
        ]
        baseline_psi = sum(baseline_psis) / len(baseline_psis) if baseline_psis else None
        return OutputDriftResponse(
            state=SectionState.OK,
            profile_status=profile,
            name=values.get("name"),
            kind=values.get("kind"),
            psi=current_psi,
            baseline_psi=baseline_psi,
            psi_delta=(
                current_psi - baseline_psi
                if current_psi is not None and baseline_psi is not None
                else None
            ),
            severity=Severity(values.get("status", result.severity or Severity.OK)),
            count=int(values.get("count") or 0),
            distribution=_distribution(values.get("distribution")),
            psi_over_time=_output_psi_series(history),
            trend=_output_trend_series(history),
            top_changed=_top_changed_classes(values.get("distribution")),
            class_share_trend=_class_share_series(values.get("distribution"), history),
            confidence=_confidence_block(values.get("confidence"), history),
            probabilities=(
                ProbabilityBlock.model_validate(values["probabilities"])
                if values.get("probabilities")
                else None
            ),
            horizons=[HorizonDrift.model_validate(entry) for entry in values.get("horizons") or []],
            alerts=alerts,
            computed_at=result.computed_at,
            stale=self._is_stale(result.computed_at, dims),
        )

    async def _psi_history(self, deployment_id: UUID, dims: QueryDimensions) -> Series | None:
        """PSI of the selected feature across the materialized windows of the time range.

        The worker stores one feature-drift result per window, so the trend is assembled
        from those rows here rather than duplicated into every window's payload.
        """
        feature = dims.feature
        if feature is None:
            return None
        start, _ = self._window_bounds(dims)
        history = await self._store.fetch_result_history(
            deployment_id, GROUP_FEATURE_DRIFT, dims.window.value, since=start
        )
        points = [
            SeriesPoint(
                t=result.computed_at,
                value=_maybe_float(
                    (result.values.get("features") or {}).get(feature, {}).get("psi")
                ),
            )
            for result in history
            if result.computed_at is not None
        ]
        if len(points) < 2:
            return None
        return Series(key="psi", label=f"PSI · {feature}", points=points)

    async def reference_profile(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> ReferenceProfileResponse:
        try:
            profile = await self._store.fetch_profile(deployment_id)
            status = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return ReferenceProfileResponse(state=SectionState.UNAVAILABLE)
        if profile is None:
            return ReferenceProfileResponse(state=SectionState.EMPTY, profile_status=status)
        selected = None
        if dims.feature is not None:
            entry = profile.features.get(dims.feature)
            if entry is not None:
                selected = _reference_feature(entry)
        return ReferenceProfileResponse(
            state=SectionState.OK,
            profile_status=status,
            baseline_label=profile.baseline_label,
            computed_at=profile.computed_at,
            features=sorted(profile.features),
            feature=selected,
            document=profile.document,
        )

    async def worker_health(self, deployment_id: UUID) -> WorkerHealthResponse:
        if self._health_source is not None:
            snapshot, cadence = self._health_source(deployment_id)
        else:
            try:
                heartbeats = await self._store.read_worker_heartbeats()
            except MonitoringStoreUnavailable:
                return WorkerHealthResponse(state=SectionState.UNAVAILABLE)
            merged = WorkerHeartbeat.merge(
                heartbeats,
                deployment_id,
                now=datetime.fromtimestamp(self._clock(), tz=UTC),
            )
            if merged is None:
                return WorkerHealthResponse(state=SectionState.UNAVAILABLE)
            snapshot = merged.snapshot
            cadence = (merged.window_seconds, merged.interval_seconds)
        deployment = snapshot.deployment
        incidents = await self._metric_incidents(deployment_id)
        return WorkerHealthResponse(
            state=SectionState.OK,
            running=snapshot.running,
            last_tick_at=snapshot.last_tick_at,
            windows_processed=deployment.windows_processed,
            last_window_end=deployment.last_window_end,
            last_lag_seconds=deployment.last_lag_seconds,
            window_seconds=cadence[0],
            interval_seconds=cadence[1],
            failures=[
                MetricFailure(metric=f.metric, error=f.error, at=f.at) for f in deployment.failures
            ],
            incidents=incidents,
        )

    async def _metric_incidents(self, deployment_id: UUID) -> list[MetricIncident]:
        """Pair the stored transitions into stretches of "this metric was broken".

        The worker writes one row when a metric starts failing and one when it recovers,
        so an incident is a ``failed`` row closed by the next ``recovered`` row — or still
        open if none followed.
        """
        since = datetime.fromtimestamp(self._clock(), tz=UTC) - timedelta(seconds=_INCIDENT_WINDOW)
        try:
            transitions = await self._store.fetch_metric_transitions(deployment_id, since)
        except MonitoringStoreUnavailable:
            return []

        open_by_metric: dict[str, MetricIncident] = {}
        incidents: list[MetricIncident] = []
        for transition in sorted(transitions, key=lambda t: t.at):
            current = open_by_metric.pop(transition.metric, None)
            if transition.kind == "failed":
                if current is not None:  # a restart re-opened it; keep the earlier stretch
                    incidents.append(current)
                open_by_metric[transition.metric] = MetricIncident(
                    metric=transition.metric,
                    error=transition.error,
                    started_at=transition.at,
                    ongoing=True,
                )
            elif current is not None:
                incidents.append(
                    current.model_copy(update={"ended_at": transition.at, "ongoing": False})
                )
        incidents.extend(open_by_metric.values())
        return sorted(incidents, key=lambda i: i.started_at, reverse=True)

    async def alerts(self, deployment_id: UUID, dims: QueryDimensions) -> AlertsResponse:
        try:
            stored = await self._store.fetch_alerts(deployment_id)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return AlertsResponse(state=SectionState.UNAVAILABLE)
        matching = [a for a in stored if _severity_matches(a.severity, dims.severity)]
        histories = await self._alert_histories(deployment_id, dims, matching)
        document = await self._profile_document(deployment_id)
        return AlertsResponse(
            state=SectionState.OK,
            profile_status=profile,
            groups=_group_alerts(matching, histories, document),
        )

    async def acknowledge_alert(
        self, deployment_id: UUID, metric: str, dims: QueryDimensions
    ) -> AlertsResponse:
        """Acknowledge one alert and answer with the list as it now stands.

        The dashboard reloads the whole section anyway, so returning it here saves a round
        trip and guarantees the button and the list never disagree.
        """
        try:
            await self._store.acknowledge_alert(deployment_id, metric)
        except MonitoringStoreUnavailable:
            return AlertsResponse(state=SectionState.UNAVAILABLE)
        return await self.alerts(deployment_id, dims)

    async def _profile_document(self, deployment_id: UUID) -> dict[str, Any] | None:
        """The artifact profile, for reading the deployment's own threshold rules."""
        try:
            reference = await self._store.fetch_profile(deployment_id)
        except MonitoringStoreUnavailable:
            return None
        return reference.document if reference else None

    async def _alert_histories(
        self, deployment_id: UUID, dims: QueryDimensions, alerts: list[StoredAlert]
    ) -> dict[str, Series]:
        """The metric behind each alert across the materialized windows.

        One query per metric group, not per alert: every alert of a group reads its own
        value out of the same windows.
        """
        start, _ = self._window_bounds(dims)
        histories: dict[str, Series] = {}
        for group in {alert.group for alert in alerts}:
            try:
                windows = await self._store.fetch_result_history(
                    deployment_id, group, dims.window.value, since=start
                )
            except MonitoringStoreUnavailable:
                return histories
            if not windows:
                continue
            for alert in alerts:
                if alert.group != group:
                    continue
                parsed = parse_alert_key(alert.metric)
                points = [
                    SeriesPoint(t=window.computed_at, value=history_value(parsed, window.values))
                    for window in windows
                    if window.computed_at is not None
                ]
                if sum(1 for point in points if point.value is not None) < 2:
                    continue
                histories[alert.metric] = Series(
                    key=alert.metric, label=parsed.label, unit=parsed.unit, points=points
                )
        return histories

    async def traces(
        self,
        deployment_id: UUID,
        dims: QueryDimensions,
        *,
        limit: int = TRACES_DEFAULT_LIMIT,
        offset: int = 0,
        sort: TraceSort = TraceSort.TS,
        order: SortOrder = SortOrder.DESC,
    ) -> TracesResponse:
        try:
            start, end = self._window_bounds(dims)
            events = await self._store.fetch_events(deployment_id, start, end)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return TracesResponse(state=SectionState.UNAVAILABLE, limit=limit, offset=offset)

        keys = {
            TraceSort.TS: lambda e: e.ts,
            TraceSort.LATENCY: lambda e: e.latency_ms,
            TraceSort.STATUS: lambda e: (e.status_code, e.ts),
        }
        ordered = sorted(events, key=keys[sort], reverse=order is SortOrder.DESC)
        page = ordered[offset : offset + limit]
        return TracesResponse(
            state=SectionState.OK if ordered else SectionState.EMPTY,
            profile_status=profile,
            rows=[_trace_row(e) for e in page],
            total=len(ordered),
            limit=limit,
            offset=offset,
        )

    async def trace_detail(
        self, deployment_id: UUID, dims: QueryDimensions, event_id: str
    ) -> TraceDetailResponse:
        """One call from the traces table, with its full inputs/output payloads.

        Scoped to the same window as the table it was opened from: an event that
        scrolled out of the window is reported as missing (`trace=None` -> 404).
        """
        try:
            start, end = self._window_bounds(dims)
            events = await self._store.fetch_events(deployment_id, start, end)
            profile = await self._profile_status(deployment_id)
        except MonitoringStoreUnavailable:
            return TraceDetailResponse(state=SectionState.UNAVAILABLE)
        event = next((e for e in events if e.event_id == event_id), None)
        if event is None:
            return TraceDetailResponse(state=SectionState.EMPTY, profile_status=profile)

        spans: list[SpanRecord] = []
        if event.trace_id:
            try:
                spans = await self._store.fetch_spans(event.trace_id)
            except MonitoringStoreUnavailable:
                return TraceDetailResponse(state=SectionState.UNAVAILABLE)

        return TraceDetailResponse(
            state=SectionState.OK,
            profile_status=profile,
            trace=_trace_detail(event, spans),
        )

    async def _runtime(
        self, deployment_id: UUID, dims: QueryDimensions
    ) -> tuple[_Rollup, list[Series]]:
        start, end = self._window_bounds(dims)
        events = await self._store.fetch_events(deployment_id, start, end)
        baseline_bounds = self._baseline_bounds(dims)
        if baseline_bounds is None:
            series_start, bucket, n_buckets = _series_layout(events, start, dims)
            return _rollup(events), _runtime_series(events, series_start, bucket, n_buckets)

        bucket = _bucket_seconds(dims)
        n_buckets = math.ceil(dims.span_seconds() / bucket)
        series = _runtime_series(events, start, bucket, n_buckets)
        base_events = await self._store.fetch_events(deployment_id, *baseline_bounds)
        base_series = _runtime_series(base_events, baseline_bounds[0], bucket, n_buckets)

        shift = start - baseline_bounds[0]
        base_by_key = {one.key: one for one in base_series}
        for one in series:
            base = base_by_key.get(one.key)
            if base is not None:
                one.baseline = [
                    SeriesPoint(t=point.t + shift, value=point.value) for point in base.points
                ]
        return _rollup(events), series

    def _runtime_baseline(
        self, rollup: _Rollup | None, dims: QueryDimensions
    ) -> RuntimeBaseline | None:
        bounds = self._baseline_bounds(dims)
        if rollup is None or bounds is None:
            return None
        return RuntimeBaseline(
            start=bounds[0],
            end=bounds[1],
            request_count=rollup.request_count,
            success_rate=rollup.success_rate,
            error_rate=rollup.error_rate,
            latency_p50_ms=rollup.latency_p50_ms,
            latency_p95_ms=rollup.latency_p95_ms,
            latency_max_ms=rollup.latency_max_ms,
            timeout_count=rollup.timeout_count,
            failed_inference_count=rollup.failed_inference_count,
        )

    async def _baseline_history(
        self, deployment_id: UUID, group: str, dims: QueryDimensions
    ) -> list[StoredMetricResult]:
        """The materialized windows of one group inside the comparison period."""
        bounds = self._baseline_bounds(dims)
        if bounds is None:
            return []
        try:
            return await self._store.fetch_result_history(
                deployment_id, group, dims.window.value, since=bounds[0], until=bounds[1]
            )
        except MonitoringStoreUnavailable:
            return []

    async def _previous_rollup(self, deployment_id: UUID, dims: QueryDimensions) -> _Rollup | None:
        bounds = self._baseline_bounds(dims)
        if bounds is None:
            return None
        return _rollup(await self._store.fetch_events(deployment_id, bounds[0], bounds[1]))

    async def _banners(
        self,
        deployment_id: UUID,
        severity: SeverityFilter,
        *,
        group: str,
        dims: QueryDimensions | None = None,
    ) -> list[AlertBanner]:
        """The open alerts of one metric group, as its own tab shows them.

        With ``dims`` the banners carry the same detail the Alerts tab has — metric history
        and threshold provenance — so opening one from a section panel is not a poorer
        view of the same alert. It costs one history query for the single group involved.
        """
        alerts = await self._store.fetch_alerts(deployment_id)
        matching = [
            a
            for a in sorted(alerts, key=_banner_order)
            if a.group == group and _severity_matches(a.severity, severity)
        ]
        if dims is None or not matching:
            return [_alert_banner(a) for a in matching]
        histories = await self._alert_histories(deployment_id, dims, matching)
        document = await self._profile_document(deployment_id)
        return [_alert_banner(a, histories.get(a.metric), document) for a in matching]

    async def _profile_status(self, deployment_id: UUID) -> ProfileStatus:
        raw = await self._store.profile_status(deployment_id)
        try:
            return ProfileStatus(raw)
        except TypeError, ValueError:
            return ProfileStatus.ABSENT


def _banner_order(alert: StoredAlert) -> tuple[int, float]:
    rank = 0 if alert.severity == Severity.CRITICAL else 1
    last_seen = alert.last_seen.timestamp() if alert.last_seen else 0.0
    return rank, -last_seen


def _group_alerts(
    alerts: list[StoredAlert],
    histories: dict[str, Series] | None = None,
    profile: dict[str, Any] | None = None,
) -> list[AlertGroup]:
    histories = histories or {}
    by_group: dict[str, list[AlertBanner]] = {}
    for alert in sorted(alerts, key=_banner_order):
        by_group.setdefault(alert.group, []).append(
            _alert_banner(alert, histories.get(alert.metric), profile)
        )
    known = [
        AlertGroup(group=group, alerts=by_group.pop(group))
        for group in _ALERT_GROUP_ORDER
        if group in by_group
    ]
    extra = [AlertGroup(group=group, alerts=items) for group, items in by_group.items()]
    return known + extra


def _mean_feature_values(history: list[StoredMetricResult], key: str) -> dict[str, float]:
    """Per-feature mean of one numeric field across materialized windows.

    The comparison period is summarized as the mean rather than any single window:
    which 5-minute window happens to sit at the period's edge is noise, the typical
    level over the period is the signal.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in history:
        for name, entry in (row.values.get("features") or {}).items():
            value = _maybe_float(entry.get(key)) if isinstance(entry, dict) else None
            if value is None:
                continue
            sums[name] = sums.get(name, 0.0) + value
            counts[name] = counts.get(name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums}


def _drifted_features(values: dict[str, Any]) -> list[DriftedFeature]:
    features = values.get("features", {})
    drifted: list[DriftedFeature] = []
    for name, entry in features.items():
        psi = entry.get("psi")
        if psi is None:
            continue
        drifted.append(
            DriftedFeature(
                feature=name,
                psi=float(psi),
                severity=Severity(entry.get("status", Severity.OK)),
            )
        )
    return drifted


def _output_drift_card(result: StoredMetricResult | None) -> Card | None:
    """The Overview's output-drift summary, as a card next to the runtime ones."""
    if result is None:
        return None
    psi = _maybe_float(result.values.get("psi"))
    if psi is None:
        return None
    return Card(
        key="output_drift",
        label="Output drift",
        value=psi,
        unit="score",
        severity=Severity(result.values.get("status", result.severity or Severity.OK)),
    )


def _output_psi_series(history: list[StoredMetricResult]) -> Series | None:
    points = [
        SeriesPoint(t=result.computed_at, value=_maybe_float(result.values.get("psi")))
        for result in history
        if result.computed_at is not None
    ]
    if not points:
        return None
    return Series(key="output_psi", label="PSI", unit="score", points=points)


_TREND_KEYS = (("median", "Median"), ("p05", "p05"), ("p95", "p95"), ("mean", "Mean"))


def _output_trend_series(history: list[StoredMetricResult]) -> list[Series]:
    """The per-window prediction summaries, one aligned series per statistic."""
    rows = [
        (result.computed_at, result.values.get("trend") or {})
        for result in history
        if result.computed_at is not None and result.values.get("trend")
    ]
    if not rows:
        return []
    return [
        Series(
            key=f"prediction_{key}",
            label=label,
            points=[SeriesPoint(t=at, value=_maybe_float(trend.get(key))) for at, trend in rows],
        )
        for key, label in _TREND_KEYS
    ]


_CLASS_TREND_LIMIT = 6


def _top_changed_classes(distribution: dict[str, Any] | None) -> list[ClassShift]:
    """Predicted classes ranked by how far their share moved off the reference.

    Built from the labels the model actually returned — the only output the Satellite
    records. Probability-based views need models that emit probability vectors.
    """
    if not distribution or distribution.get("kind") != "categorical":
        return []
    shifts = [
        ClassShift(
            label=entry["label"],
            reference=float(entry.get("reference") or 0.0),
            current=float(entry.get("current") or 0.0),
            delta=float(entry.get("current") or 0.0) - float(entry.get("reference") or 0.0),
        )
        for entry in distribution.get("bins", [])
    ]
    return sorted(shifts, key=lambda shift: abs(shift.delta), reverse=True)


def _class_share_series(
    distribution: dict[str, Any] | None, history: list[StoredMetricResult]
) -> list[Series]:
    """Each class's live share across the materialized windows.

    Assembled from the per-window distributions, for the classes that moved most in the
    latest window — the ones worth a line each.
    """
    top = _top_changed_classes(distribution)[:_CLASS_TREND_LIMIT]
    if not top:
        return []
    labels = [shift.label for shift in top]
    rows: list[tuple[datetime, dict[str, float]]] = []
    for result in history:
        stored = result.values.get("distribution") or {}
        if result.computed_at is None or stored.get("kind") != "categorical":
            continue
        shares = {
            entry["label"]: float(entry.get("current") or 0.0) for entry in stored.get("bins", [])
        }
        rows.append((result.computed_at, shares))
    if not rows:
        return []
    return [
        Series(
            key=f"class_{label}",
            label=label,
            unit="ratio",
            points=[SeriesPoint(t=at, value=shares.get(label)) for at, shares in rows],
        )
        for label in labels
    ]


def _confidence_block(
    raw: dict[str, Any] | None, history: list[StoredMetricResult]
) -> ConfidenceBlock | None:
    """The classifier's confidence, with its mean assembled across the windows."""
    if not raw:
        return None
    points = [
        SeriesPoint(
            t=result.computed_at,
            value=_maybe_float((result.values.get("confidence") or {}).get("mean")),
        )
        for result in history
        if result.computed_at is not None and result.values.get("confidence")
    ]
    mean_series = (
        Series(key="confidence_mean", label="Mean confidence", points=points) if points else None
    )
    return ConfidenceBlock(
        psi=_maybe_float(raw.get("psi")),
        mean=_maybe_float(raw.get("mean")),
        low_confidence_rate=_maybe_float(raw.get("low_confidence_rate")),
        low_confidence_threshold=_maybe_float(raw.get("low_confidence_threshold")),
        distribution=_distribution(raw.get("distribution")),
        mean_over_time=mean_series,
    )


def _maybe_float(value: float | int | str | None) -> float | None:
    return None if value is None else float(value)


def _feature_detail(values: dict[str, Any], feature: str | None) -> FeatureDriftDetail | None:
    if feature is None:
        return None
    entry = values.get("features", {}).get(feature)
    if entry is None:
        return None
    return FeatureDriftDetail(
        feature=feature,
        psi=_maybe_float(entry.get("psi")),
        status=Severity(entry.get("status", Severity.OK)),
        distribution=_distribution(entry.get("distribution")),
        psi_over_time=_psi_series(feature, entry.get("psi_series")),
    )


def _distribution(raw: dict[str, Any] | None) -> FeatureDistribution | None:
    if not raw:
        return None
    bins = [
        DistributionBin(
            label=str(b.get("label")),
            reference=_maybe_float(b.get("reference")),
            current=_maybe_float(b.get("current")),
        )
        for b in raw.get("bins", [])
    ]
    return FeatureDistribution(kind=raw.get("kind", "numeric"), bins=bins)


def _psi_series(feature: str, raw: list[dict[str, Any]] | None) -> Series | None:
    if not raw:
        return None
    points = [SeriesPoint(t=p["t"], value=_maybe_float(p.get("value"))) for p in raw]
    return Series(key="psi", label=f"PSI · {feature}", points=points)


def _points(raw: list[list[float]]) -> list[PcaPoint]:
    return [PcaPoint(x=float(p[0]), y=float(p[1])) for p in raw]


def _multivariate_panel(
    result: StoredMetricResult | None, drift: StoredMetricResult | None = None
) -> MultivariatePanel:
    if result is None:
        return MultivariatePanel(state=SectionState.EMPTY)
    values = result.values
    projection = values.get("projection", {})
    ellipses = values.get("ellipses", {})

    feature_source = drift.values if drift is not None else values
    return MultivariatePanel(
        state=SectionState.OK,
        status=Severity(values.get("status", result.severity or Severity.OK)),
        shift_value=_maybe_float(values.get("shift_value")),
        shift_metric=values.get("shift_metric"),
        shift_unit=str(values.get("shift_unit") or ""),
        dispersion_ratio=_maybe_float(values.get("dispersion_ratio")),
        outlier_rate=_maybe_float(values.get("outlier_rate")),
        reference_ellipse=_points(ellipses.get("reference", [])),
        current_ellipse=_points(ellipses.get("current", [])),
        explained_variance=[float(v) for v in values.get("explained_variance", [])],
        feature_psi=sorted(_drifted_features(feature_source), key=lambda d: d.psi, reverse=True),
        reference_projection=_points(projection.get("reference", [])),
        current_projection=_points(projection.get("current", [])),
    )


def _reference_feature(entry: ReferenceFeatureProfile) -> ReferenceProfileFeature:
    return ReferenceProfileFeature(
        feature=entry.feature,
        kind=entry.kind,
        summary=entry.summary,
        bin_edges=entry.bin_edges,
        histogram=entry.histogram,
        categories=entry.categories,
        category_probabilities=entry.category_probabilities,
    )


def _invalid_values(detail: dict[str, Any] | None) -> InvalidValueSummary | None:
    """Flatten the metric's per-check evidence into the single summary the panel reads."""
    if not detail:
        return None
    missing = detail.get("missing") or {}
    types = detail.get("type_mismatch") or {}
    ranges = detail.get("range_violation") or {}
    unseen = detail.get("unseen_category") or {}
    return InvalidValueSummary(
        missing_count=missing.get("count", 0),
        type_mismatch_count=types.get("count", 0),
        observed_types=types.get("types") or {},
        type_examples=types.get("examples") or [],
        range_violation_count=ranges.get("count", 0),
        below_min=ranges.get("below_min", 0),
        above_max=ranges.get("above_max", 0),
        observed_min=_maybe_float(ranges.get("observed_min")),
        observed_max=_maybe_float(ranges.get("observed_max")),
        reference_min=_maybe_float(ranges.get("reference_min")),
        reference_max=_maybe_float(ranges.get("reference_max")),
        unseen_category_count=unseen.get("count", 0),
        unseen_distinct=unseen.get("distinct", 0),
        reference_categories=unseen.get("reference_categories"),
        unseen_categories=[
            UnseenCategoryCount(value=str(item.get("value")), count=item.get("count", 0))
            for item in unseen.get("values") or []
        ],
    )


def _data_quality_rows(values: dict[str, Any], feature: str | None) -> list[DataQualityFeatureRow]:
    features = values.get("features", {})
    rows: list[DataQualityFeatureRow] = []
    for name, entry in features.items():
        if feature is not None and name != feature:
            continue

        range_violation = _maybe_float(entry.get("range_violation_rate"))
        unseen_category = _maybe_float(entry.get("unseen_category_rate"))
        applicable = [rate for rate in (range_violation, unseen_category) if rate is not None]
        rows.append(
            DataQualityFeatureRow(
                feature=name,
                kind=entry.get("kind"),
                missing_rate=_maybe_float(entry.get("missing_rate")),
                type_error_rate=_maybe_float(entry.get("type_mismatch_rate")),
                range_unseen_rate=max(applicable) if applicable else None,
                range_violation_rate=range_violation,
                unseen_category_rate=unseen_category,
                checked=entry.get("count"),
                status=Severity(entry.get("status", Severity.OK)),
                invalid=_invalid_values(entry.get("invalid")),
            )
        )
    return rows


def _overview_cards(
    rollup: _Rollup,
    previous: _Rollup | None,
    dims: QueryDimensions,
    alerts: list[StoredAlert],
    criticals: list[StoredAlert],
    drifted_names: list[str],
) -> list[Card]:
    kind = dims.compare if previous is not None else None
    return [
        Card(
            key="requests",
            label="Requests",
            value=rollup.request_count,
            delta=_delta(rollup.request_count, previous.request_count) if previous else None,
            delta_kind=kind,
        ),
        Card(
            key="error_rate",
            label="Error rate",
            value=rollup.error_rate,
            unit="ratio",
            delta=_delta(rollup.error_rate, previous.error_rate) if previous else None,
            delta_kind=kind,
        ),
        Card(
            key="latency_p95",
            label="Latency p95",
            value=rollup.latency_p95_ms,
            unit="ms",
            delta=_delta(rollup.latency_p95_ms, previous.latency_p95_ms) if previous else None,
            delta_kind=kind,
        ),
        Card(
            key="active_alerts",
            label="Active alerts",
            value=len(alerts),
            critical_count=len(criticals),
        ),
        Card(
            key="drifted_features",
            label="Drifted features",
            value=len(drifted_names),
            feature_names=drifted_names,
        ),
    ]


def _trace_row(event: InferenceEvent) -> TraceRow:
    return TraceRow(
        event_id=event.event_id,
        ts=event.ts,
        features_summary=_preview(event.inputs),
        prediction=_preview(event.output),
        latency_ms=event.latency_ms,
        status=event.status,
        status_code=event.status_code,
    )


def _trace_detail(event: InferenceEvent, spans: list[SpanRecord]) -> TraceDetail:
    return TraceDetail(
        event_id=event.event_id,
        ts=event.ts,
        latency_ms=event.latency_ms,
        status=event.status,
        status_code=event.status_code,
        trace_id=event.trace_id,
        span_id=event.span_id,
        inputs=_payload(event.inputs),
        output=_payload(event.output),
        spans=_trace_spans(event, spans),
    )


def _trace_spans(event: InferenceEvent, spans: list[SpanRecord]) -> list[TraceSpan]:
    """Spans of the trace, with the request payloads attached to its root.

    The collector keeps inputs/output on the `inference_events` row, not on the raw
    OTel span, so the root span would otherwise open with almost no attributes.
    When no spans were collected, the call still renders as a single synthetic span.
    """
    if not spans:
        return [_synthetic_span(event)]

    ids = {s.span_id for s in spans}
    payload = {
        "inference.inputs": _payload(event.inputs),
        "inference.output": _payload(event.output),
    }
    result = []
    for span in spans:
        is_root = span.parent_span_id is None or span.parent_span_id not in ids
        attributes = {**span.attributes, **payload} if is_root else dict(span.attributes)
        result.append(
            TraceSpan(
                trace_id=span.trace_id,
                span_id=span.span_id,
                parent_span_id=span.parent_span_id,
                name=span.name,
                kind=span.kind,
                start_time_unix_nano=span.start_time_unix_nano,
                end_time_unix_nano=span.end_time_unix_nano,
                status_code=span.status_code,
                status_message=span.status_message,
                attributes=attributes,
                events=span.events,
                links=span.links,
                dfs_span_type=span.dfs_span_type,
            )
        )
    return result


def _synthetic_span(event: InferenceEvent) -> TraceSpan:
    """The call itself, for deployments whose traces the collector did not store."""
    start_ns = int(event.ts.timestamp() * 1_000_000_000)
    return TraceSpan(
        trace_id=event.trace_id or "",
        span_id=event.span_id or event.event_id,
        parent_span_id=None,
        name="inference",
        kind=1,  # SPAN_KIND_INTERNAL
        start_time_unix_nano=start_ns,
        end_time_unix_nano=start_ns + int(event.latency_ms * 1_000_000),
        status_code=2 if event.status_code >= 500 else 1,
        status_message=None,
        attributes={
            "inference.event_id": event.event_id,
            "inference.status": event.status,
            "inference.latency_ms": event.latency_ms,
            "inference.inputs": _payload(event.inputs),
            "inference.output": _payload(event.output),
        },
    )


def _payload(raw: str | None) -> object | None:
    """Decode a stored inputs/output JSON string; keep it as text if it is not JSON."""
    if not raw:
        return None
    try:
        decoded: object = json.loads(raw)
        return decoded
    except ValueError:
        return raw


def _preview(raw: str | None) -> str | None:
    """Condense a stored inputs/output JSON string into one bounded table-cell summary."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return _truncate(raw, _TRACE_SUMMARY_MAX_LEN)
    if isinstance(parsed, dict):
        items = list(parsed.items())[:_TRACE_SUMMARY_MAX_KEYS]
        summary = ", ".join(f"{key}={_scalar(value)}" for key, value in items)
        if len(parsed) > _TRACE_SUMMARY_MAX_KEYS:
            summary += ", …"
        return _truncate(summary, _TRACE_SUMMARY_MAX_LEN)
    return _truncate(_scalar(parsed), _TRACE_SUMMARY_MAX_LEN)


def _scalar(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (str, int)):
        return str(value)
    return json.dumps(value, separators=(",", ":"))


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
