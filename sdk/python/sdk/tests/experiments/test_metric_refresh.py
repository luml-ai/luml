import logging
import os
import random
import sqlite3
import threading
import time
import warnings
from pathlib import Path

import pytest

from luml.experiments.backends import (
    _write_buffer as write_buffer,
    metric_store,
)
from luml.experiments.backends._write_buffer import (
    DEFAULT_FLUSH_THRESHOLD,
    BatchKeys,
    WriteBuffer,
)
from luml.experiments.backends.metric_store import METRIC_POINT_SQL
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import assert_bucket_invariants, make_store

EXP_ID = "exp"
NO_TIMER_FLUSH = 3600.0


@pytest.fixture
def store(tmp_path: Path) -> Path:
    make_store(tmp_path / "store", EXP_ID)
    return tmp_path / "store"


@pytest.fixture
def backend(store: Path) -> SQLiteBackend:
    backend = SQLiteBackend(str(store), flush_interval=NO_TIMER_FLUSH)
    backend._write_buffer.flush_threshold = 10**9
    return backend


def _db_path(store: Path) -> str:
    return str(store / EXP_ID / "exp.db")


def _check(store: Path) -> None:
    conn = sqlite3.connect(_db_path(store))
    try:
        assert_bucket_invariants(conn)
    finally:
        conn.close()


def _stored_points(store: Path) -> dict[tuple[str, int], float | None]:
    conn = sqlite3.connect(_db_path(store))
    try:
        rows = conn.execute("SELECT key, step, value FROM dynamic_metrics").fetchall()
    finally:
        conn.close()
    return {(key, step): value for key, step, value in rows}


def _touched_level3(backend: SQLiteBackend, store: Path) -> set[tuple[str, int]]:
    with backend.pool.get_connection(_db_path(store)) as conn:
        rows = conn.execute(
            "SELECT k.key, t.bucket FROM temp.luml_touched_buckets t "
            "JOIN metric_keys k ON k.id = t.metric_id WHERE t.level = 3"
        ).fetchall()
    return set(rows)


WIDE_KEYS = [f"w{index:02d}" for index in range(40)]


def _log_wide(backend: SQLiteBackend, step: int, value: float = 1.0) -> None:
    """Touches more level-3 buckets than are rebuilt one by one."""
    for key in WIDE_KEYS:
        backend.log_dynamic(EXP_ID, key, value, step=step)


def _wide_buckets(step: int) -> set[tuple[str, int]]:
    return {(key, step >> 6) for key in WIDE_KEYS}


def _wide_points(step: int, value: float = 1.0) -> dict[tuple[str, int], float | None]:
    return {(key, step): value for key in WIDE_KEYS}


def _random_batch(
    rng: random.Random, keys: list[str], expected: dict[tuple[str, int], float | None]
) -> None:
    """Many buckets per key, overwrites, out-of-order, negative and far-apart steps,
    the same (key, step) twice, and values that are not summable."""
    for _ in range(3_000):
        key = rng.choice(keys)
        roll = rng.random()
        if roll < 0.2 and expected:
            key, step = rng.choice(list(expected))
        elif roll < 0.3:
            step = rng.randrange(-5_000, 0)
        elif roll < 0.35:
            step = rng.choice([2**62, -(2**62), 4**12 * 7 + 3])
        else:
            step = rng.randrange(0, 20_000)
        value = rng.choice(
            [rng.uniform(-1e3, 1e3)] * 6 + [float("inf"), float("nan"), 1e300]
        )
        expected[(key, step)] = None if value != value else value


def test_wide_batches_match_brute_force(backend: SQLiteBackend, store: Path) -> None:
    rng = random.Random(7)
    keys = [f"m{index}" for index in range(120)]
    expected: dict[tuple[str, int], float | None] = {}
    for _ in range(4):
        batch: dict[tuple[str, int], float | None] = {}
        _random_batch(rng, keys, batch)
        for (key, step), value in batch.items():
            # Queued twice, the second write wins.
            backend.log_dynamic(EXP_ID, key, rng.uniform(-1, 1), step=step)
            backend.log_dynamic(
                EXP_ID, key, float("nan") if value is None else value, step=step
            )
        expected.update(batch)
        backend.flush(EXP_ID)
        _check(store)
    assert _stored_points(store) == expected


@pytest.mark.parametrize("wide", [False, True])
def test_a_row_dropped_by_the_replay_leaves_exact_buckets(
    backend: SQLiteBackend, store: Path, caplog: pytest.LogCaptureFixture, wide: bool
) -> None:
    db_path = _db_path(store)
    if wide:
        _log_wide(backend, step=3)
    buffer = backend._write_buffer
    for key in ("a", "b"):
        backend.log_dynamic(EXP_ID, key, 1.0, step=3)
        backend.log_dynamic(EXP_ID, key, 2.0, step=70)
    # Unencodable text fails only when bound, so the batch is replayed row by row:
    # one dropped row overwrites a point, the other is alone in its buckets.
    for step in (3, 10**9):
        buffer.enqueue(
            db_path,
            buffer.generation(db_path),
            METRIC_POINT_SQL,
            ("a", step, "\ud800", 0),
        )
    backend.log_dynamic(EXP_ID, "b", 5.0, step=4)

    with caplog.at_level(logging.ERROR):
        backend.flush(EXP_ID)

    assert sum("Dropped buffered row" in r.getMessage() for r in caplog.records) == 2
    assert _stored_points(store) == {
        ("a", 3): 1.0,
        ("a", 70): 2.0,
        ("b", 3): 1.0,
        ("b", 4): 5.0,
        ("b", 70): 2.0,
        **(_wide_points(3) if wide else {}),
    }
    _check(store)


def test_each_flush_rebuilds_only_its_own_buckets(
    backend: SQLiteBackend, store: Path
) -> None:
    _log_wide(backend, step=0)
    backend.log_dynamic(EXP_ID, "acc", 1.0, step=640)
    backend.flush(EXP_ID)
    assert _touched_level3(backend, store) == _wide_buckets(0) | {("acc", 10)}

    _log_wide(backend, step=64)
    backend.flush(EXP_ID)
    assert _touched_level3(backend, store) == _wide_buckets(64)
    _check(store)


def test_a_failed_refresh_is_rolled_back_and_the_next_flush_is_exact(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _log_wide(backend, step=0)
    backend.flush(EXP_ID)
    _log_wide(backend, step=0, value=7.0)
    backend.log_dynamic(EXP_ID, "acc", 3.0, step=100)
    good_statement = metric_store._REBUILD_UPPER_LEVEL
    monkeypatch.setattr(metric_store, "_REBUILD_UPPER_LEVEL", "SELECT * FROM missing")
    with pytest.raises(sqlite3.OperationalError):
        backend.flush(EXP_ID)
    assert _stored_points(store) == _wide_points(0)
    _check(store)

    monkeypatch.setattr(metric_store, "_REBUILD_UPPER_LEVEL", good_statement)
    backend.log_dynamic(EXP_ID, "lr", 0.1, step=5)
    backend.flush(EXP_ID)

    assert _stored_points(store) == {
        **_wide_points(0, value=7.0),
        ("acc", 100): 3.0,
        ("lr", 5): 0.1,
    }
    assert _touched_level3(backend, store) == _wide_buckets(0) | {
        ("acc", 1),
        ("lr", 0),
    }
    _check(store)


def test_a_failed_first_refresh_on_a_connection_is_rolled_back(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_statement = metric_store._REBUILD_UPPER_LEVEL
    monkeypatch.setattr(metric_store, "_REBUILD_UPPER_LEVEL", "SELECT * FROM missing")
    _log_wide(backend, step=0)
    with pytest.raises(sqlite3.OperationalError):
        backend.flush(EXP_ID)

    monkeypatch.setattr(metric_store, "_REBUILD_UPPER_LEVEL", good_statement)
    backend.flush(EXP_ID)

    assert _stored_points(store) == _wide_points(0)
    _check(store)


def test_a_reopened_connection_refreshes_buckets(
    backend: SQLiteBackend, store: Path
) -> None:
    _log_wide(backend, step=0)
    backend.flush(EXP_ID)
    backend.pool.close_connection(_db_path(store))

    _log_wide(backend, step=1)
    backend.flush(EXP_ID)

    assert _touched_level3(backend, store) == _wide_buckets(1)
    assert len(_stored_points(store)) == 2 * len(WIDE_KEYS)
    _check(store)


def test_write_through_refreshes_buckets(store: Path) -> None:
    backend = SQLiteBackend(str(store), flush_interval=0)
    for step in (5, -3, 5, 4**12 + 1):
        backend.log_dynamic(EXP_ID, "loss", float(step), step=step)
    backend.log_dynamic(EXP_ID, "acc", 1.0, step=0)
    backend.close()

    assert len(_stored_points(store)) == 4
    _check(store)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_a_forked_child_refreshes_buckets_on_its_own_connection(
    backend: SQLiteBackend, store: Path
) -> None:
    _log_wide(backend, step=0)
    backend.flush(EXP_ID)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        pid = os.fork()
    if pid == 0:
        exit_code = 1
        try:
            _log_wide(backend, step=1)
            backend.log_dynamic(EXP_ID, "acc", 2.0, step=200)
            backend.flush(EXP_ID)
            exit_code = 0
        finally:
            os._exit(exit_code)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0

    _log_wide(backend, step=2)
    backend.flush(EXP_ID)

    assert len(_stored_points(store)) == 3 * len(WIDE_KEYS) + 1
    _check(store)


class _FixedKeys:
    def __init__(self, keys: BatchKeys | None) -> None:
        self.keys = keys

    def batch_keys(self, db_path: str) -> BatchKeys | None:
        return self.keys


@pytest.mark.parametrize(
    ("keys", "threshold"),
    [
        (None, 5_000),
        (BatchKeys(count=1, mean_length=4), 5_000),
        (
            BatchKeys(count=200, mean_length=12),
            5_000 * 200 // write_buffer.WIDE_FLUSH_KEYS,
        ),
        (BatchKeys(count=10**6, mean_length=12), write_buffer.MAX_FLUSH_THRESHOLD),
        (
            BatchKeys(count=10**6, mean_length=1_000),
            write_buffer.MAX_QUEUED_BYTES // 1_240,
        ),
        (BatchKeys(count=10**6, mean_length=10**6), 5_000),
    ],
)
def test_flush_threshold_grows_with_the_keys_of_the_last_flush_within_bounds(
    backend: SQLiteBackend, keys: BatchKeys | None, threshold: int
) -> None:
    buffer = WriteBuffer(backend.pool, hook=_FixedKeys(keys))  # type: ignore[arg-type]
    buffer.close()

    assert buffer.flush_threshold_for("db") == threshold


def test_a_wide_experiment_queues_more_rows_before_an_inline_flush(
    backend: SQLiteBackend, store: Path
) -> None:
    buffer = backend._write_buffer
    keys = [f"m{index}" for index in range(2 * write_buffer.WIDE_FLUSH_KEYS)]
    for key in keys:
        backend.log_dynamic(EXP_ID, key, 0.0, step=0)
    backend.flush(EXP_ID)
    buffer.flush_threshold = 10
    assert buffer.flush_threshold_for(_db_path(store)) == 20

    for step in range(1, 11):
        for key in keys[:2]:
            backend.log_dynamic(EXP_ID, key, float(step), step=step)
    assert len(buffer._rows[_db_path(store)]) == 20

    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
    assert len(buffer._rows[_db_path(store)]) == 1
    assert buffer.flush_threshold_for(_db_path(store)) == 10
    _check(store)


RAISED_KEYS = [f"m{index}" for index in range(20 * write_buffer.WIDE_FLUSH_KEYS)]


def _raise_threshold_to_200(backend: SQLiteBackend, store: Path) -> WriteBuffer:
    buffer = backend._write_buffer
    for key in RAISED_KEYS:
        backend.log_dynamic(EXP_ID, key, 0.0, step=0)
    backend.flush(EXP_ID)
    buffer.flush_threshold = 10
    assert buffer.flush_threshold_for(_db_path(store)) == 200
    return buffer


def _log_spans(backend: SQLiteBackend, count: int, payload_bytes: int = 0) -> None:
    attributes = {"payload": "x" * payload_bytes}
    for index in range(count):
        backend.log_span(EXP_ID, "t", f"s{index}", "n", 0, 1, attributes=attributes)


def test_other_rows_on_a_failing_database_stop_at_the_base_threshold(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = _raise_threshold_to_200(backend, store)

    def failing_write(*args: object) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(buffer, "_write", failing_write)
    for key in RAISED_KEYS[:100]:
        backend.log_dynamic(EXP_ID, key, 1.0, step=1)
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        _log_spans(backend, 200, payload_bytes=4096)

    rows = buffer._rows[_db_path(store)]
    assert len(rows) == 110
    assert sum(sql != METRIC_POINT_SQL for sql, _ in rows) == 10


def test_spans_after_a_wide_metric_phase_are_held_to_the_base_threshold(
    backend: SQLiteBackend, store: Path
) -> None:
    buffer = _raise_threshold_to_200(backend, store)

    _log_spans(backend, 25)

    assert len(buffer._rows[_db_path(store)]) == 5
    assert buffer.flush_threshold_for(_db_path(store)) == 10


def test_the_threshold_stays_raised_after_a_flush_of_known_keys(
    backend: SQLiteBackend, store: Path
) -> None:
    buffer = _raise_threshold_to_200(backend, store)
    for key in RAISED_KEYS:
        backend.log_dynamic(EXP_ID, key, 1.0, step=1)
    backend.flush(EXP_ID)

    assert buffer.flush_threshold_for(_db_path(store)) == 200


def test_a_wide_run_with_a_few_spans_keeps_the_raised_threshold(
    backend: SQLiteBackend, store: Path
) -> None:
    buffer = _raise_threshold_to_200(backend, store)
    for key in RAISED_KEYS[:150]:
        backend.log_dynamic(EXP_ID, key, 1.0, step=1)
    _log_spans(backend, 5)
    for key in RAISED_KEYS[150:190]:
        backend.log_dynamic(EXP_ID, key, 1.0, step=1)

    assert len(buffer._rows[_db_path(store)]) == 195
    for key in RAISED_KEYS[190:]:
        backend.log_dynamic(EXP_ID, key, 1.0, step=1)
    assert len(buffer._rows[_db_path(store)]) == 5
    _check(store)


def test_the_timer_still_flushes_rows_below_a_raised_threshold(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = SQLiteBackend(str(store), flush_interval=0.05)
    buffer = backend._write_buffer
    keys = [f"m{index}" for index in range(300)]
    wide = BatchKeys(count=len(keys), mean_length=4)
    monkeypatch.setattr(buffer._hook, "batch_keys", lambda db_path: wide)
    threshold = buffer.flush_threshold_for(_db_path(store))
    assert (
        threshold == DEFAULT_FLUSH_THRESHOLD * len(keys) // write_buffer.WIDE_FLUSH_KEYS
    )
    inline_flushes: list[str] = []
    original_flush = buffer.flush

    def recording_flush(db_path: str) -> None:
        on_main = threading.current_thread() is threading.main_thread()
        if on_main and buffer._rows.get(db_path):
            inline_flushes.append(db_path)
        original_flush(db_path)

    monkeypatch.setattr(buffer, "flush", recording_flush)
    points = 0
    for step in range(40):
        for key in keys:
            backend.log_dynamic(EXP_ID, key, float(step), step=step)
            points += 1
    deadline = time.monotonic() + 30
    while len(_stored_points(store)) < points and time.monotonic() < deadline:
        time.sleep(0.05)

    assert points > DEFAULT_FLUSH_THRESHOLD
    assert len(_stored_points(store)) == points
    assert inline_flushes == []
    backend.close()
    _check(store)


def test_a_forgotten_database_starts_again_from_the_base_threshold(
    backend: SQLiteBackend, store: Path
) -> None:
    buffer = backend._write_buffer
    buffer.flush_threshold = 10
    keys = [f"m{index}" for index in range(500)]
    for key in keys:
        buffer.enqueue(_db_path(store), 0, METRIC_POINT_SQL, (key, 0, 1.0, 0))
    backend.flush(EXP_ID)
    assert (
        buffer.flush_threshold_for(_db_path(store))
        == 10 * len(keys) // write_buffer.WIDE_FLUSH_KEYS
    )

    buffer.mark_created(_db_path(store))
    assert buffer.flush_threshold_for(_db_path(store)) == 10


def test_points_split_over_statements_keep_the_last_write_of_a_step(
    backend: SQLiteBackend, store: Path
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
    backend.flush(EXP_ID)
    with backend.pool.get_connection(_db_path(store)) as conn:
        # Three points per statement.
        conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 13)
    expected: dict[tuple[str, int], float | None] = {}
    for attempt in range(3):
        for step in range(7):
            for key in ("loss", "acc"):
                value = float(-attempt * 100 + step)
                backend.log_dynamic(EXP_ID, key, value, step=step)
                expected[(key, step)] = value
    backend.log_dynamic(EXP_ID, "acc", -1.0, step=-70)
    expected[("acc", -70)] = -1.0

    backend.flush(EXP_ID)

    assert _stored_points(store) == expected
    _check(store)
