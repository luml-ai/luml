import math
import sqlite3
from pathlib import Path

import pytest
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.tracker import ExperimentTracker
from lumlflow.handlers.experiments import MAX_BUCKETS_PER_REQUEST
from lumlflow.schemas.experiments import (
    MetricBucket,
    MetricBuckets,
    MetricCatalog,
    MetricSummary,
)
from lumlflow.tui import metric_series
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.metric_series import (
    MetricSeries,
    bucket_averages,
    bucket_ranges,
    level_for,
    load_changed_series,
    load_comparison_series,
)

from tests.helpers.metrics import LEGACY_INSERT, log_points, revision2_experiment


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


def _load_all(
    facade: DataFacade,
    experiment_id: str,
    budgets: dict[str, int],
    shown: dict[str, tuple[MetricSummary | None, int]],
) -> list[MetricSeries]:
    result = load_changed_series(
        facade, experiment_id, budgets, shown, is_cancelled=lambda: False
    )
    assert result is not None
    return result.unwrap()


def test_load_changed_series_skips_what_is_already_shown(
    tracker: ExperimentTracker,
) -> None:
    facade = DataFacade(tracker=tracker)
    experiment_id = tracker.start_experiment(name="x")
    log_points(tracker, experiment_id, "a", [(step, 1.0) for step in range(10)])
    log_points(tracker, experiment_id, "b", [(step, 2.0) for step in range(300)])
    budgets = {"a": 100, "b": 100, "never": 100}

    first = _load_all(facade, experiment_id, budgets, {})
    shown = {loaded.key: loaded.fingerprint for loaded in first}
    again = _load_all(facade, experiment_id, budgets, shown)
    log_points(tracker, experiment_id, "a", [(10, 1.0)])
    grown = _load_all(facade, experiment_id, budgets, shown)

    assert {(s.key, s.level, len(s.buckets)) for s in first} == {
        ("a", 0, 10),
        ("b", 1, 75),
        ("never", 0, 0),
    }
    assert again == []
    assert [(s.key, len(s.buckets)) for s in grown] == [("a", 11)]


def test_load_changed_series_reads_each_level_in_batches_under_the_key_limit(
    tracker: ExperimentTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(metric_series, "MAX_KEYS_PER_BUCKET_REQUEST", 2)
    facade = DataFacade(tracker=tracker)
    experiment_id = tracker.start_experiment(name="x")
    short_keys = ["s0", "s1", "s2"]
    for key in short_keys:
        log_points(tracker, experiment_id, key, [(step, 1.0) for step in range(10)])
    log_points(tracker, experiment_id, "long", [(step, 1.0) for step in range(300)])
    calls: list[tuple[str, int | None, tuple[str, ...]]] = []
    catalog_read = facade.get_metric_catalog
    buckets_read = facade.get_metric_buckets

    def counted_catalog(experiment_id: str) -> Result[MetricCatalog]:
        calls.append(("catalog", None, ()))
        return catalog_read(experiment_id)

    def counted_buckets(
        experiment_id: str, keys: list[str], *, level: int
    ) -> Result[MetricBuckets]:
        calls.append(("buckets", level, tuple(keys)))
        return buckets_read(experiment_id, keys, level=level)

    monkeypatch.setattr(facade, "get_metric_catalog", counted_catalog)
    monkeypatch.setattr(facade, "get_metric_buckets", counted_buckets)
    budgets = dict.fromkeys([*short_keys, "long"], 100)

    loaded = _load_all(facade, experiment_id, budgets, {})

    assert calls == [
        ("catalog", None, ()),
        ("buckets", 0, ("s0", "s1")),
        ("buckets", 0, ("s2",)),
        ("buckets", 1, ("long",)),
    ]
    assert {(s.key, s.level, len(s.buckets)) for s in loaded} == {
        ("s0", 0, 10),
        ("s1", 0, 10),
        ("s2", 0, 10),
        ("long", 1, 75),
    }


@pytest.mark.parametrize(
    ("appended", "averages"),
    [
        ([], ([0.0, 1.0, 2.0], [0.0, 7.0, 10.0])),
        ([(3, 3.0)], ([0.0, 1.0, 2.0, 3.0], [0.0, 7.0, 10.0, 3.0])),
    ],
)
def test_a_refresh_picks_up_a_value_overwritten_at_an_existing_step(
    tracker: ExperimentTracker,
    appended: list[tuple[int, float]],
    averages: tuple[list[float], list[float]],
) -> None:
    facade = DataFacade(tracker=tracker)
    experiment_id = tracker.start_experiment(name="x")
    log_points(tracker, experiment_id, "m", [(0, 0.0), (1, 5.0), (2, 10.0)])
    budgets = {"m": 100}
    first = _load_all(facade, experiment_id, budgets, {})
    shown = {series.key: series.fingerprint for series in first}
    assert bucket_averages(first[0]) == ([0.0, 1.0, 2.0], [0.0, 5.0, 10.0])

    log_points(tracker, experiment_id, "m", [(1, 7.0), *appended])
    refreshed = _load_all(facade, experiment_id, budgets, shown)

    assert [bucket_averages(series) for series in refreshed] == [averages]


def _revision3_experiment(store: Path) -> str:
    experiment_id, db_path = revision2_experiment(store, "m", [(0, 1.0), (1, 2.0)])
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate(target_version=3)
    conn.close()
    return experiment_id


@pytest.mark.parametrize(("revision", "reads_again"), [(2, 0), (3, 1), (4, 0)])
def test_an_unchanged_metric_is_read_again_only_where_writes_are_not_tracked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    revision: int,
    reads_again: int,
) -> None:
    store = tmp_path / "experiments"
    if revision == 2:
        experiment_id, _ = revision2_experiment(store, "m", [(0, 1.0), (1, 2.0)])
        tracker = ExperimentTracker(f"sqlite://{store}")
    elif revision == 3:
        experiment_id = _revision3_experiment(store)
        tracker = ExperimentTracker(f"sqlite://{store}")
    else:
        tracker = ExperimentTracker(f"sqlite://{store}")
        experiment_id = tracker.start_experiment(name="x")
        log_points(tracker, experiment_id, "m", [(0, 1.0), (1, 2.0)])
    facade = DataFacade(tracker=tracker)
    budgets = {"m": 100}
    first = _load_all(facade, experiment_id, budgets, {})
    shown = {series.key: series.fingerprint for series in first}
    assert facade.get_metric_catalog(experiment_id).unwrap().revision == revision
    bucket_reads: list[tuple[str, ...]] = []
    buckets_read = facade.get_metric_buckets

    def counted_buckets(
        experiment_id: str, keys: list[str], *, level: int
    ) -> Result[MetricBuckets]:
        bucket_reads.append(tuple(keys))
        return buckets_read(experiment_id, keys, level=level)

    monkeypatch.setattr(facade, "get_metric_buckets", counted_buckets)

    again = _load_all(facade, experiment_id, budgets, shown)

    assert len(bucket_reads) == reads_again
    assert [bucket_averages(series) for series in again] == [
        bucket_averages(first[0])
    ] * reads_again


def test_a_revision2_metric_is_read_again_once_points_are_appended(
    tmp_path: Path,
) -> None:
    store = tmp_path / "experiments"
    experiment_id, db_path = revision2_experiment(store, "m", [(0, 1.0), (1, 2.0)])
    facade = DataFacade(tracker=ExperimentTracker(f"sqlite://{store}"))
    budgets = {"m": 100}
    first = _load_all(facade, experiment_id, budgets, {})
    shown = {series.key: series.fingerprint for series in first}
    conn = sqlite3.connect(db_path)
    conn.execute(LEGACY_INSERT, ("m", 3.0, 2, "2026-01-02 03:04:06"))
    conn.commit()
    conn.close()

    again = _load_all(facade, experiment_id, budgets, shown)

    assert facade.get_metric_catalog(experiment_id).unwrap().revision == 2
    assert [bucket_averages(series) for series in again] == [
        ([0.0, 1.0, 2.0], [1.0, 2.0, 3.0])
    ]


def test_a_refresh_of_many_dense_metrics_stays_within_the_bucket_limit(
    tracker: ExperimentTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    facade = DataFacade(tracker=tracker)
    experiment_id = tracker.start_experiment(name="x")
    keys = [f"m{index:04d}" for index in range(1000)]
    for step in range(201):
        for key in keys:
            tracker.log_dynamic(key, float(step), step=step)
    tracker.backend.flush()
    batch_sizes: list[int] = []
    buckets_read = facade.get_metric_buckets

    def counted_buckets(
        experiment_id: str, keys: list[str], *, level: int
    ) -> Result[MetricBuckets]:
        batch_sizes.append(len(keys))
        return buckets_read(experiment_id, keys, level=level)

    monkeypatch.setattr(facade, "get_metric_buckets", counted_buckets)
    # A chart cell's budget on a terminal wide enough for three columns.
    budget = 250

    loaded = _load_all(facade, experiment_id, dict.fromkeys(keys, budget), {})

    assert len(loaded) == len(keys)
    assert all(len(series.buckets) == 201 for series in loaded)
    assert all(size * budget <= MAX_BUCKETS_PER_REQUEST for size in batch_sizes)


def test_a_cancelled_load_stops_before_the_next_bucket_read(
    tracker: ExperimentTracker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(metric_series, "MAX_KEYS_PER_BUCKET_REQUEST", 1)
    facade = DataFacade(tracker=tracker)
    experiment_id = tracker.start_experiment(name="x")
    for key in ("a", "b", "c"):
        log_points(tracker, experiment_id, key, [(0, 1.0)])
    bucket_reads: list[tuple[str, ...]] = []
    buckets_read = facade.get_metric_buckets

    def counted_buckets(
        experiment_id: str, keys: list[str], *, level: int
    ) -> Result[MetricBuckets]:
        bucket_reads.append(tuple(keys))
        return buckets_read(experiment_id, keys, level=level)

    monkeypatch.setattr(facade, "get_metric_buckets", counted_buckets)

    loaded = load_changed_series(
        facade,
        experiment_id,
        dict.fromkeys(["a", "b", "c"], 100),
        {},
        is_cancelled=lambda: len(bucket_reads) == 1,
    )

    assert loaded is None
    assert bucket_reads == [("a",)]


def test_load_comparison_series_marks_unknown_experiments_unreadable(
    tracker: ExperimentTracker,
) -> None:
    facade = DataFacade(tracker=tracker)
    with_key = tracker.start_experiment(name="with")
    without_key = tracker.start_experiment(name="without")
    log_points(tracker, with_key, "m", [(0, 1.0), (1, 3.0)])
    log_points(tracker, without_key, "other", [(0, 1.0)])

    loaded = load_comparison_series(
        facade, [with_key, without_key, "gone"], "m", 50, is_cancelled=lambda: False
    )
    assert loaded is not None

    assert loaded["gone"] is None
    assert loaded[without_key] == MetricSeries(key="m", level=0, summary=None)
    plotted = loaded[with_key]
    assert plotted is not None
    assert plotted.summary is not None
    assert plotted.summary.writes is not None
    assert plotted.summary.model_copy(update={"writes": None}) == MetricSummary(
        key="m", first_step=0, last_step=1, count=2, min=1.0, max=3.0
    )
    assert bucket_averages(plotted) == ([0.0, 1.0], [1.0, 3.0])


@pytest.mark.parametrize(
    ("checks_before_cancel", "expected_reads"),
    [(1, ["catalog"]), (2, ["catalog", "catalog"])],
)
def test_a_cancelled_comparison_load_stops_reading_and_returns_nothing(
    tracker: ExperimentTracker,
    monkeypatch: pytest.MonkeyPatch,
    checks_before_cancel: int,
    expected_reads: list[str],
) -> None:
    facade = DataFacade(tracker=tracker)
    first = tracker.start_experiment(name="first")
    log_points(tracker, first, "m", [(0, 1.0)])
    reads: list[str] = []
    for name, read in (
        ("catalog", facade.get_metric_catalog),
        ("buckets", facade.get_metric_buckets),
    ):

        def recorded(*args, _read=read, _name=name, **kwargs):
            reads.append(_name)
            return _read(*args, **kwargs)

        monkeypatch.setattr(facade, f"get_metric_{name}", recorded)
    checks: list[None] = []

    def is_cancelled() -> bool:
        checks.append(None)
        return len(checks) > checks_before_cancel

    loaded = load_comparison_series(
        facade, [first, "gone"], "m", 50, is_cancelled=is_cancelled
    )

    assert loaded is None
    assert reads == expected_reads
