import json
import math
import random
import sqlite3
from pathlib import Path

import pytest

from luml.experiments.backends._exceptions import (
    InvalidBucketLevelError,
    TooManyBucketsError,
)
from luml.experiments.backends.data_types import MetricBucket, MetricBuckets
from luml.experiments.backends.metric_store import (
    MAX_RETURNED_BUCKETS,
    choose_bucket_level,
    fetch_metric_buckets,
)
from luml.experiments.backends.migration_runner import read_experiment_schema
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import (
    FIXTURES_DIR,
    LEGACY_INSERT,
    aggregate,
    assert_bucket_invariants,
    assert_same_buckets,
    assert_same_catalog,
    brute_force_buckets,
    make_revision2_store,
    make_store,
    sums_close,
)

EXP_ID = "exp"
NO_TIMER_FLUSH = 3600.0


@pytest.fixture
def backend(tmp_path: Path) -> SQLiteBackend:
    make_store(tmp_path / "store", EXP_ID)
    return SQLiteBackend(str(tmp_path / "store"), flush_interval=NO_TIMER_FLUSH)


def _expected(
    points: list[tuple[int, float | None]],
    key: str,
    level: int,
    start: int | None = None,
    end: int | None = None,
) -> MetricBuckets:
    steps = [step for step, _ in points]
    low = min(steps) if start is None else start
    high = max(steps) if end is None else end
    shift = 2 * level
    buckets = [
        MetricBucket(
            bucket=bucket,
            first_step=agg.first_step,
            last_step=agg.last_step,
            count=agg.count,
            finite_count=agg.finite_count,
            min=agg.min,
            max=agg.max,
            sum=agg.sum,
        )
        for bucket, agg in brute_force_buckets(points, level).items()
        if low >> shift <= bucket <= high >> shift and low <= high
    ]
    return MetricBuckets(
        key=key,
        level=level,
        first_step=min(steps),
        last_step=max(steps),
        buckets=buckets,
    )


def _log(backend: SQLiteBackend, key: str, points: list[tuple[int, float]]) -> None:
    for step, value in points:
        backend.log_dynamic(EXP_ID, key, value, step=step)
    backend.flush()


def test_range_edges_inside_a_bucket_return_the_whole_bucket(
    backend: SQLiteBackend,
) -> None:
    points = [(step, float(step)) for step in range(1000)]
    _log(backend, "m", points)

    result = backend.get_metric_buckets(EXP_ID, "m", 3, start_step=70, end_step=130)

    assert [(b.bucket, b.first_step, b.last_step, b.count) for b in result.buckets] == [
        (1, 64, 127, 64),
        (2, 128, 191, 64),
    ]
    assert (result.first_step, result.last_step) == (0, 999)
    assert result.buckets[0].sum == sum(range(64, 128))


@pytest.mark.parametrize("level", [0, 1, 2, 3, 7, 12, 13, 16, 31])
def test_every_level_matches_brute_force(backend: SQLiteBackend, level: int) -> None:
    rng = random.Random(level)
    points = [(step, rng.uniform(-5, 5)) for step in range(-300, 2500, 3)]
    points += [(10**9, 1.0), (-(10**9), -1.0)]
    _log(backend, "m", points)

    for start, end in [(None, None), (-50, 50), (100, 100), (2000, 10**10)]:
        assert_same_buckets(
            backend.get_metric_buckets(EXP_ID, "m", level, start, end),
            _expected(points, "m", level, start, end),
        )


def test_empty_range_and_unknown_key(backend: SQLiteBackend) -> None:
    _log(backend, "m", [(0, 1.0), (10, 2.0)])

    reversed_range = backend.get_metric_buckets(EXP_ID, "m", 0, 5, 4)
    gap = backend.get_metric_buckets(EXP_ID, "m", 0, 1, 9)
    unknown = backend.get_metric_buckets(EXP_ID, "nope", 3)

    assert (reversed_range.buckets, reversed_range.first_step) == ([], 0)
    assert (gap.buckets, gap.last_step) == ([], 10)
    assert unknown == MetricBuckets(
        key="nope", level=3, first_step=None, last_step=None
    )


def test_non_finite_values(backend: SQLiteBackend) -> None:
    _log(
        backend,
        "m",
        [(0, float("nan")), (1, float("inf")), (2, float("-inf")), (3, 2.0)],
    )
    nan_only = backend.get_metric_buckets(EXP_ID, "m", 0, 0, 0).buckets[0]
    whole = backend.get_metric_buckets(EXP_ID, "m", 3).buckets[0]

    assert (nan_only.count, nan_only.finite_count, nan_only.min, nan_only.sum) == (
        1,
        0,
        None,
        None,
    )
    assert (whole.count, whole.finite_count, whole.sum) == (4, 1, 2.0)
    assert (whole.min, whole.max) == (float("-inf"), float("inf"))


def test_values_beyond_the_summable_limit_count_but_are_not_summed(
    tmp_path: Path, backend: SQLiteBackend
) -> None:
    huge = 1.7976931348623157e308
    # Opposite-signed halves in sibling buckets used to overflow to +-inf.
    points = [(step, huge) for step in range(64)]
    points += [(step, -huge) for step in range(64, 128)]
    points += [(128, 1e290), (129, -1e291), (130, 2.0)]
    _log(backend, "m", points)
    rev2_db = make_revision2_store(tmp_path / "rev2", EXP_ID)
    _write_revision2(rev2_db, [("m", value, step) for step, value in points])
    reader2 = SQLiteBackend(str(tmp_path / "rev2"), flush_interval=0)

    for level in (2, 3, 4, 12, 13):
        result = backend.get_metric_buckets(EXP_ID, "m", level)
        assert_same_buckets(result, reader2.get_metric_buckets(EXP_ID, "m", level))
        assert_same_buckets(result, _expected(points, "m", level))
    top = backend.get_metric_buckets(EXP_ID, "m", 12).buckets[0]
    assert (top.count, top.finite_count, top.sum) == (131, 2, 1e290 + 2.0)
    assert (top.min, top.max) == (-huge, huge)
    first = backend.get_metric_buckets(EXP_ID, "m", 3).buckets[0]
    assert (first.count, first.finite_count, first.sum) == (64, 0, None)
    reader2.close()
    conn = sqlite3.connect(tmp_path / "store" / EXP_ID / "exp.db")
    assert_bucket_invariants(conn)
    conn.close()


def _vm_steps(db_path: Path, key: str) -> int:
    conn = sqlite3.connect(db_path)
    steps = 0

    def count() -> int:
        nonlocal steps
        steps += 1
        return 0

    schema = read_experiment_schema(conn)
    conn.set_progress_handler(count, 1)
    fetch_metric_buckets(conn, schema, key, 12)
    conn.close()
    return steps


def test_a_coarse_read_costs_the_same_however_many_points(
    backend: SQLiteBackend, tmp_path: Path
) -> None:
    for step in range(100):
        backend.log_dynamic(EXP_ID, "small", 1.0, step=step)
    for step in range(50_000):
        backend.log_dynamic(EXP_ID, "large", 1.0, step=step)
    backend.flush()
    db_path = tmp_path / "store" / EXP_ID / "exp.db"

    assert _vm_steps(db_path, "large") <= _vm_steps(db_path, "small") + 50


def test_stored_levels_are_read_from_the_bucket_table(
    backend: SQLiteBackend, tmp_path: Path
) -> None:
    _log(backend, "m", [(step, 1.0) for step in range(300)])
    conn = sqlite3.connect(tmp_path / "store" / EXP_ID / "exp.db")
    conn.execute(
        "UPDATE metric_buckets SET count = count + 1000 WHERE level IN (3, 12)"
    )
    conn.commit()
    conn.close()

    counts = {
        level: [b.count for b in backend.get_metric_buckets(EXP_ID, "m", level).buckets]
        for level in (2, 3, 4, 12, 13)
    }
    assert counts[2] == [16] * 18 + [12]
    assert counts[3] == [1064] * 4 + [1044]
    assert counts[4] == [256, 44]
    assert counts[12] == counts[13] == [1300]


def test_a_range_outside_64_bit_steps_returns_no_buckets(
    backend: SQLiteBackend,
) -> None:
    _log(backend, "m", [(-(2**63), 1.0), (2**63 - 1, 2.0)])
    for start, end in [(2**70, 2**63 - 1), (2**70, 2**71), (-(2**71), -(2**70))]:
        assert backend.get_metric_buckets(EXP_ID, "m", 3, start, end).buckets == []
    whole = backend.get_metric_buckets(EXP_ID, "m", 31, -(2**70), 2**70)
    assert [b.count for b in whole.buckets] == [1, 1]


def test_bucket_cap(backend: SQLiteBackend) -> None:
    _log(backend, "m", [(step, 1.0) for step in range(MAX_RETURNED_BUCKETS + 1)])

    with pytest.raises(TooManyBucketsError):
        backend.get_metric_buckets(EXP_ID, "m", 0)
    exact = backend.get_metric_buckets(EXP_ID, "m", 0, 1, MAX_RETURNED_BUCKETS)
    assert len(exact.buckets) == MAX_RETURNED_BUCKETS
    assert len(backend.get_metric_buckets(EXP_ID, "m", 1).buckets) == 5001


def test_numeric_types_are_stored_as_numbers(
    backend: SQLiteBackend, tmp_path: Path
) -> None:
    np = pytest.importorskip("numpy")
    backend.log_dynamic(EXP_ID, "m", np.float32(1.5), step=np.int64(7))
    backend.log_dynamic(EXP_ID, "m", 4, step=2.0)
    with pytest.raises(TypeError, match="integer"):
        backend.log_dynamic(EXP_ID, "m", 1.0, step=2.5)
    backend.flush()

    conn = sqlite3.connect(tmp_path / "store" / EXP_ID / "exp.db")
    rows = conn.execute(
        "SELECT step, typeof(step), value, typeof(value) FROM metric_points"
    ).fetchall()
    conn.close()
    assert rows == [(2, "integer", 4.0, "real"), (7, "integer", 1.5, "real")]


@pytest.mark.parametrize("level", [-1, 32, 2**70, True, 3.0])
def test_invalid_level(backend: SQLiteBackend, level: object) -> None:
    _log(backend, "m", [(0, 1.0)])
    with pytest.raises(InvalidBucketLevelError, match="from 0 to 31"):
        backend.get_metric_buckets(EXP_ID, "m", level)
    assert backend.get_metric_buckets(EXP_ID, "m", 31).buckets[0].count == 1


def test_catalog(backend: SQLiteBackend) -> None:
    _log(backend, "b", [(5, 3.0), (-2, float("inf")), (9, float("nan"))])
    _log(backend, "a", [(0, 1.0)])

    catalog = backend.get_metric_catalog(EXP_ID)

    assert (catalog.revision, catalog.bucket_min_level, catalog.bucket_max_level) == (
        3,
        3,
        12,
    )
    assert [
        (m.key, m.first_step, m.last_step, m.count, m.min, m.max)
        for m in catalog.metrics
    ] == [
        ("a", 0, 0, 1, 1.0, 1.0),
        ("b", -2, 9, 3, 3.0, float("inf")),
    ]


def test_level_vectors() -> None:
    vectors = json.loads((FIXTURES_DIR / "bucket_level_vectors.json").read_text())
    assert len(vectors["vectors"]) > 20
    for vector in vectors["vectors"]:
        args = (vector["first_step"], vector["last_step"], vector["max_buckets"])
        if vector.get("error"):
            with pytest.raises(ValueError, match="must"):
                choose_bucket_level(*args)
            continue
        level = choose_bucket_level(*args)
        assert level == vector["level"], vector
        span = vector["last_step"] - vector["first_step"] + 1
        assert math.ceil(span / 4**level) <= vector["max_buckets"]
        if level:
            assert -(-span // 4 ** (level - 1)) > vector["max_buckets"]


VALUE_POOL = [
    float("nan"),
    float("inf"),
    float("-inf"),
    1e300,
    -1e300,
    1e-300,
    -0.0,
    0.0,
]


def _random_value(rng: random.Random) -> float:
    if rng.random() < 0.2:
        return rng.choice(VALUE_POOL)
    return rng.uniform(-1000, 1000)


def _random_step(rng: random.Random, steps: dict[int, float]) -> int | None:
    roll = rng.random()
    if roll < 0.35:
        return None
    if roll < 0.55 and steps:
        return rng.choice(list(steps))
    if roll < 0.75:
        return rng.randint(-600, 3000)
    if roll < 0.9:
        return rng.randint(-(10**12), 10**12)
    return -rng.randint(1, 5000)


def _write_revision2(db_path: Path, rows: list[tuple[str, float, int]]) -> None:
    conn = sqlite3.connect(db_path)
    conn.executemany(
        LEGACY_INSERT,
        [(key, value, step, "2026-01-01 00:00:00") for key, value, step in rows],
    )
    conn.commit()
    conn.close()


@pytest.mark.parametrize("flush_interval", [NO_TIMER_FLUSH, 0.0])
def test_random_operations_keep_invariants_and_match_revision_2(
    tmp_path: Path, flush_interval: float
) -> None:
    rng = random.Random(20261115)
    store3, store2 = tmp_path / "rev3", tmp_path / "rev2"
    make_store(store3, EXP_ID)
    rev2_db = make_revision2_store(store2, EXP_ID)
    backend = SQLiteBackend(str(store3), flush_interval=flush_interval)
    checker = sqlite3.connect(store3 / EXP_ID / "exp.db")
    model: dict[str, dict[int, float]] = {}
    pending: list[tuple[str, float, int]] = []

    for operation in range(1500):
        key = rng.choice(["loss", "acc", "lr", "grad"])
        steps = model.setdefault(key, {})
        step = _random_step(rng, steps)
        value = _random_value(rng)
        backend.log_dynamic(EXP_ID, key, value, step=step)
        actual_step = (max(steps) + 1 if steps else 0) if step is None else step
        steps[actual_step] = value
        pending.append((key, value, actual_step))
        if rng.random() < 0.02:
            # A span that fails as a row forces the row-by-row replay.
            try:
                backend.log_span(EXP_ID, "t", f"s{operation}", None, 0, 0, 1)
            except sqlite3.IntegrityError:
                assert flush_interval == 0
        if rng.random() < 0.05:
            backend.flush()
            _write_revision2(rev2_db, pending)
            pending = []
            assert_bucket_invariants(checker)
    backend.flush()
    _write_revision2(rev2_db, pending)
    assert_bucket_invariants(checker)
    checker.close()

    reader2 = SQLiteBackend(str(store2), flush_interval=0)
    assert_same_catalog(
        backend.get_metric_catalog(EXP_ID), reader2.get_metric_catalog(EXP_ID)
    )
    for key, steps in model.items():
        points = sorted(steps.items())
        lo, hi = points[0][0], points[-1][0]
        middle = (lo + hi) // 2
        for level in range(15):
            for start, end in [(None, None), (lo + 7, middle), (-100, 100)]:
                if level < 2 and start is None:
                    continue
                result3 = backend.get_metric_buckets(EXP_ID, key, level, start, end)
                result2 = reader2.get_metric_buckets(EXP_ID, key, level, start, end)
                assert_same_buckets(result3, result2)
                _assert_matches_model(result3, points, key, level, start, end)
                _assert_matches_model(result2, points, key, level, start, end)
    assert reader2.get_experiment_ddl_version(EXP_ID) == 2
    reader2.close()
    backend.close()


def _assert_matches_model(
    result: MetricBuckets,
    points: list[tuple[int, float]],
    key: str,
    level: int,
    start: int | None,
    end: int | None,
) -> None:
    stored = [(step, None if math.isnan(value) else value) for step, value in points]
    expected = _expected(stored, key, level, start, end)
    assert len(result.buckets) == len(expected.buckets)
    for actual, wanted in zip(result.buckets, expected.buckets, strict=True):
        members = [(s, v) for s, v in stored if s >> (2 * level) == wanted.bucket]
        scale = aggregate(members).abs_sum
        assert (actual.bucket, actual.count, actual.finite_count) == (
            wanted.bucket,
            wanted.count,
            wanted.finite_count,
        )
        assert (actual.min, actual.max, actual.first_step, actual.last_step) == (
            wanted.min,
            wanted.max,
            wanted.first_step,
            wanted.last_step,
        )
        assert sums_close(actual.sum, wanted.sum, scale)
