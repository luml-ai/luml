import math
from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.schemas.experiments import MetricBucket, MetricSummary
from lumlflow.tui.data import DataFacade
from lumlflow.tui.metric_series import (
    MetricSeries,
    bucket_averages,
    bucket_ranges,
    level_for,
    load_changed_series,
    load_comparison_series,
)

from tests.helpers.metrics import log_points


def series(*buckets: MetricBucket, level: int = 2) -> MetricSeries:
    return MetricSeries(key="m", level=level, summary=None, buckets=buckets)


def test_averages_use_the_finite_sum_and_skip_buckets_without_finite_values() -> None:
    plotted = series(
        MetricBucket(0, 0, 14, 4, 2, 1.0, math.inf, 6.0),
        MetricBucket(1, 16, 16, 1, 0, -math.inf, -math.inf, None),
        MetricBucket(2, 32, 40, 2, 2, 1.0, 3.0, 4.0),
    )

    assert bucket_averages(plotted) == ([7.0, 36.0], [3.0, 2.0])


def test_ranges_keep_only_finite_multi_point_buckets() -> None:
    plotted = series(
        MetricBucket(0, 0, 14, 4, 2, 1.0, math.inf, 6.0),
        MetricBucket(1, 16, 16, 1, 1, 5.0, 5.0, 5.0),
        MetricBucket(2, 32, 40, 2, 2, 1.0, 3.0, 4.0),
        MetricBucket(3, 48, 50, 2, 0, None, None, None),
    )

    assert bucket_ranges(plotted) == ([36.0], [1.0], [3.0])


@pytest.mark.parametrize(
    ("first", "last", "budget", "level"),
    [(0, 0, 100, 0), (0, 99, 100, 0), (0, 100, 100, 1), (0, 499, 10, 3), (5, 5, 0, 0)],
)
def test_level_for_picks_the_smallest_level_within_the_budget(
    first: int, last: int, budget: int, level: int
) -> None:
    assert level_for(first, last, budget) == level


@pytest.fixture()
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


def test_load_changed_series_skips_what_is_already_shown(
    tracker: ExperimentTracker,
) -> None:
    facade = DataFacade(tracker=tracker)
    experiment_id = tracker.start_experiment(name="x")
    log_points(tracker, experiment_id, "a", [(step, 1.0) for step in range(10)])
    log_points(tracker, experiment_id, "b", [(step, 2.0) for step in range(300)])
    budgets = {"a": 100, "b": 100, "never": 100}

    first = load_changed_series(facade, experiment_id, budgets, {}).unwrap()
    shown = {loaded.key: loaded.fingerprint for loaded in first}
    again = load_changed_series(facade, experiment_id, budgets, shown).unwrap()
    log_points(tracker, experiment_id, "a", [(10, 1.0)])
    grown = load_changed_series(facade, experiment_id, budgets, shown).unwrap()

    assert {(s.key, s.level, len(s.buckets)) for s in first} == {
        ("a", 0, 10),
        ("b", 1, 75),
        ("never", 0, 0),
    }
    assert again == []
    assert [(s.key, len(s.buckets)) for s in grown] == [("a", 11)]


def test_load_comparison_series_marks_unknown_experiments_unreadable(
    tracker: ExperimentTracker,
) -> None:
    facade = DataFacade(tracker=tracker)
    with_key = tracker.start_experiment(name="with")
    without_key = tracker.start_experiment(name="without")
    log_points(tracker, with_key, "m", [(0, 1.0), (1, 3.0)])
    log_points(tracker, without_key, "other", [(0, 1.0)])

    loaded = load_comparison_series(facade, [with_key, without_key, "gone"], "m", 50)

    assert loaded["gone"] is None
    assert loaded[without_key] == MetricSeries(key="m", level=0, summary=None)
    plotted = loaded[with_key]
    assert plotted is not None
    assert plotted.summary == MetricSummary(
        key="m", first_step=0, last_step=1, count=2, min=1.0, max=3.0
    )
    assert bucket_averages(plotted) == ([0.0, 1.0], [1.0, 3.0])
