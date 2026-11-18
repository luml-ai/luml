"""Bucketed metric series behind the TUI charts.

A chart never reads a metric's full history. It reads the experiment's metric
catalog, picks the bucket level whose bucket count fits the plot's width for the
plotted step range, and reads only those buckets. Each plotted point is a
bucket's average; the zoom view also draws its min and max.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from luml.experiments.backends.metric_store import choose_bucket_level

from lumlflow.schemas.experiments import (
    MAX_KEYS_PER_BUCKET_REQUEST,
    MetricBucket,
    MetricSummary,
)
from lumlflow.tui.data import DataFacade, Result


@dataclass(frozen=True)
class MetricSeries:
    key: str
    level: int
    summary: MetricSummary | None
    buckets: tuple[MetricBucket, ...] = ()

    @property
    def has_points(self) -> bool:
        return any(bucket.finite_count for bucket in self.buckets)

    @property
    def fingerprint(self) -> tuple[MetricSummary | None, int]:
        """What a reload compares to tell whether the chart would change."""
        return self.summary, self.level


def _bucket_x(bucket: MetricBucket) -> float:
    return (bucket.first_step + bucket.last_step) / 2


def bucket_averages(series: MetricSeries) -> tuple[list[float], list[float]]:
    """Buckets without a finite value have no average and are left out."""
    xs: list[float] = []
    ys: list[float] = []
    for bucket in series.buckets:
        if bucket.finite_count and bucket.sum is not None:
            xs.append(_bucket_x(bucket))
            ys.append(bucket.sum / bucket.finite_count)
    return xs, ys


def bucket_ranges(series: MetricSeries) -> tuple[list[float], list[float], list[float]]:
    """The finite min and max of every bucket that spans more than one point."""
    xs: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    for bucket in series.buckets:
        low, high = bucket.min, bucket.max
        if bucket.count < 2 or low is None or high is None:
            continue
        if math.isfinite(low) and math.isfinite(high):
            xs.append(_bucket_x(bucket))
            lows.append(low)
            highs.append(high)
    return xs, lows, highs


def level_for(first_step: int, last_step: int, max_buckets: int) -> int:
    return choose_bucket_level(first_step, last_step, max(1, max_buckets))


def load_changed_series(
    facade: DataFacade,
    experiment_id: str,
    budgets: dict[str, int],
    shown: dict[str, tuple[MetricSummary | None, int]],
) -> Result[list[MetricSeries]]:
    """Series for the keys in `budgets` (key to bucket budget) whose catalog entry
    or level differs from `shown`. One catalog read, then one bucket read per
    level and per `MAX_KEYS_PER_BUCKET_REQUEST` keys; unchanged metrics read no
    buckets."""
    catalog = facade.get_metric_catalog(experiment_id)
    if not catalog.ok or catalog.value is None:
        return Result[list[MetricSeries]](error=catalog.error)
    summaries = {metric.key: metric for metric in catalog.value.metrics}
    loaded: list[MetricSeries] = []
    keys_by_level: dict[int, list[str]] = defaultdict(list)
    for key, budget in budgets.items():
        summary = summaries.get(key)
        level = 0
        if summary is not None:
            level = level_for(summary.first_step, summary.last_step, budget)
        if shown.get(key) == (summary, level):
            continue
        if summary is None:
            loaded.append(MetricSeries(key=key, level=level, summary=None))
        else:
            keys_by_level[level].append(key)
    batches = [
        (level, keys[start : start + MAX_KEYS_PER_BUCKET_REQUEST])
        for level, keys in keys_by_level.items()
        for start in range(0, len(keys), MAX_KEYS_PER_BUCKET_REQUEST)
    ]
    for level, keys in batches:
        result = facade.get_metric_buckets(experiment_id, keys, level=level)
        if not result.ok or result.value is None:
            return Result[list[MetricSeries]](error=result.error)
        for series in result.value.series:
            loaded.append(
                MetricSeries(
                    key=series.key,
                    level=level,
                    summary=summaries[series.key],
                    buckets=tuple(series.buckets),
                )
            )
    return Result.success(loaded)


def load_comparison_series(
    facade: DataFacade,
    experiment_ids: list[str],
    key: str,
    max_buckets: int,
    *,
    is_cancelled: Callable[[], bool],
) -> dict[str, MetricSeries | None] | None:
    """One series per experiment (None when it could not be read), all at the
    level chosen for the union of their step ranges so bucket boundaries line
    up across the compared experiments. Returns None, without reading further,
    once `is_cancelled` is true, so a partial set is never plotted."""
    summaries: dict[str, MetricSummary | None] = {}
    result: dict[str, MetricSeries | None] = {}
    for experiment_id in experiment_ids:
        if is_cancelled():
            return None
        catalog = facade.get_metric_catalog(experiment_id)
        if not catalog.ok or catalog.value is None:
            result[experiment_id] = None
            continue
        summaries[experiment_id] = next(
            (metric for metric in catalog.value.metrics if metric.key == key), None
        )
    present = [summary for summary in summaries.values() if summary is not None]
    if not present:
        result.update(
            {eid: MetricSeries(key=key, level=0, summary=None) for eid in summaries}
        )
        return result
    first_step = min(summary.first_step for summary in present)
    last_step = max(summary.last_step for summary in present)
    level = level_for(first_step, last_step, max_buckets)
    for experiment_id, summary in summaries.items():
        if summary is None:
            result[experiment_id] = MetricSeries(key=key, level=level, summary=None)
            continue
        if is_cancelled():
            return None
        buckets = facade.get_metric_buckets(
            experiment_id,
            [key],
            level=level,
            start_step=first_step,
            end_step=last_step,
        )
        if not buckets.ok or buckets.value is None:
            result[experiment_id] = None
            continue
        result[experiment_id] = MetricSeries(
            key=key,
            level=level,
            summary=summary,
            buckets=tuple(buckets.value.series[0].buckets),
        )
    return result
