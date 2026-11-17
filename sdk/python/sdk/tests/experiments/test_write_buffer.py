import atexit
import gc
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import warnings
import weakref
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends import (
    _write_buffer as write_buffer,
    sqlite as sqlite_backend,
)
from luml.experiments.backends._write_buffer import WriteBuffer
from luml.experiments.backends.data_types import AnnotationKind, AnnotationValueType
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker

EXP_ID = "buffered-exp"
NO_TIMER_FLUSH = 3600.0


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "experiments"


@pytest.fixture
def backend(store: Path) -> SQLiteBackend:
    backend = SQLiteBackend(str(store), flush_interval=NO_TIMER_FLUSH)
    backend.initialize_experiment(EXP_ID, "default", "buffered")
    return backend


def _count_rows(store: Path, table: str) -> int:
    conn = sqlite3.connect(store / EXP_ID / "exp.db")
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _log_span(backend: SQLiteBackend, span_id: str, name: str | None = "op") -> None:
    backend.log_span(
        EXP_ID,
        trace_id="trace-1",
        span_id=span_id,
        name=name,  # type: ignore[arg-type]
        start_time_unix_nano=1000,
        end_time_unix_nano=2000,
    )


def test_buffered_rows_visible_through_same_backend(backend: SQLiteBackend) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=0)
    _log_span(backend, "span-1")
    backend.log_eval_sample(EXP_ID, "e1", "ds1", inputs={"x": 1})

    history = backend.get_experiment_metric_history(EXP_ID, "loss")
    assert [(point["step"], point["value"]) for point in history] == [(0, 0.5)]
    assert backend.get_trace(EXP_ID, "trace-1") is not None
    assert backend.get_eval(EXP_ID, "e1") is not None


def test_other_connection_sees_rows_only_after_flush(
    backend: SQLiteBackend, store: Path
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=0)
    _log_span(backend, "span-1")

    assert _count_rows(store, "dynamic_metrics") == 0
    assert _count_rows(store, "spans") == 0

    backend.flush(EXP_ID)

    assert _count_rows(store, "dynamic_metrics") == 1
    assert _count_rows(store, "spans") == 1


def test_end_experiment_flushes_and_summarises_buffered_points(
    backend: SQLiteBackend, store: Path
) -> None:
    for step in range(5):
        backend.log_dynamic(EXP_ID, "loss", float(step), step=step)

    backend.end_experiment(EXP_ID)

    assert _count_rows(store, "dynamic_metrics") == 5
    experiment = backend.get_experiment(EXP_ID)
    assert experiment is not None
    assert experiment.dynamic_params == {"loss": 4.0}


def test_close_flushes_buffered_rows(backend: SQLiteBackend, store: Path) -> None:
    _log_span(backend, "span-1")
    backend.log_eval_sample(EXP_ID, "e1", "ds1", inputs={"x": 1})

    backend.close()

    assert _count_rows(store, "spans") == 1
    assert _count_rows(store, "evals") == 1


def test_export_flushes_buffered_rows(backend: SQLiteBackend, store: Path) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=0)

    backend.export_experiment_db(EXP_ID)

    assert _count_rows(store, "dynamic_metrics") == 1


def test_implicit_steps_follow_max_step(backend: SQLiteBackend, store: Path) -> None:
    for value in range(3):
        backend.log_dynamic(EXP_ID, "loss", value)
    backend.log_dynamic(EXP_ID, "loss", 10, step=10)
    backend.log_dynamic(EXP_ID, "loss", 11)
    backend.log_dynamic(EXP_ID, "loss", 3, step=3)
    backend.log_dynamic(EXP_ID, "loss", 12)
    backend.log_dynamic(EXP_ID, "acc", 0.1)
    backend.close()

    reopened = SQLiteBackend(str(store), flush_interval=NO_TIMER_FLUSH)
    reopened.log_dynamic(EXP_ID, "loss", 13)

    history = reopened.get_experiment_metric_history(EXP_ID, "loss")
    assert [(point["step"], point["value"]) for point in history] == [
        (0, 0.0),
        (1, 1.0),
        (2, 2.0),
        (3, 3.0),
        (10, 10.0),
        (11, 11.0),
        (12, 12.0),
        (13, 13.0),
    ]
    acc = reopened.get_experiment_metric_history(EXP_ID, "acc")
    assert [point["step"] for point in acc] == [0]


def test_failing_row_is_dropped_without_losing_batch(
    backend: SQLiteBackend, store: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _log_span(backend, "span-1")
    _log_span(backend, "span-bad", name=None)
    _log_span(backend, "span-2")
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=0)

    with caplog.at_level(logging.ERROR):
        backend.flush(EXP_ID)

    assert _count_rows(store, "spans") == 2
    assert _count_rows(store, "dynamic_metrics") == 1
    assert any("span-bad" in record.getMessage() for record in caplog.records)


def test_text_that_cannot_be_encoded_never_blocks_the_queue(
    backend: SQLiteBackend, store: Path
) -> None:
    with pytest.raises(ValueError, match="UTF-8"):
        backend.log_dynamic(EXP_ID, "bad\ud800", 0.5, step=0)
    _log_span(backend, "span-bad", name="bad\ud800")
    _log_span(backend, "span-1")
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=0)

    backend.flush(EXP_ID)

    assert _count_rows(store, "spans") == 1
    assert _count_rows(store, "dynamic_metrics") == 1
    assert backend._write_buffer._rows == {}


def test_annotations_after_buffered_rows_find_their_targets(
    backend: SQLiteBackend,
) -> None:
    _log_span(backend, "span-1")
    backend.log_eval_sample(EXP_ID, "e1", "ds1", inputs={"x": 1})

    span_annotation = backend.log_span_annotation(
        EXP_ID,
        "trace-1",
        "span-1",
        "quality",
        AnnotationKind.FEEDBACK,
        AnnotationValueType.BOOL,
        True,
        "alice",
    )
    eval_annotation = backend.log_eval_annotation(
        EXP_ID,
        "ds1",
        "e1",
        "quality",
        AnnotationKind.FEEDBACK,
        AnnotationValueType.BOOL,
        True,
        "alice",
    )

    assert span_annotation.value is True
    assert eval_annotation.value is True


def test_link_validates_against_buffered_rows(
    backend: SQLiteBackend, store: Path
) -> None:
    _log_span(backend, "span-1")
    backend.log_eval_sample(EXP_ID, "e1", "ds1", inputs={"x": 1})

    backend.link_eval_sample_to_trace(EXP_ID, "ds1", "e1", "trace-1")
    with pytest.raises(ValueError, match="Trace missing not found"):
        backend.link_eval_sample_to_trace(EXP_ID, "ds1", "e1", "missing")

    backend.flush(EXP_ID)
    assert _count_rows(store, "eval_traces_bridge") == 1


def test_full_queue_is_flushed_before_the_next_row(
    backend: SQLiteBackend, store: Path
) -> None:
    backend._write_buffer.flush_threshold = 3

    for step in range(3):
        backend.log_dynamic(EXP_ID, "loss", 0.1, step=step)
    assert _count_rows(store, "dynamic_metrics") == 0

    backend.log_dynamic(EXP_ID, "loss", 0.4, step=3)
    assert _count_rows(store, "dynamic_metrics") == 3


def test_inline_flush_runs_without_the_step_counter_lock(
    backend: SQLiteBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = backend._write_buffer
    buffer.flush_threshold = 1
    original_flush = buffer.flush
    locks_held_during_flush: list[int] = []

    def recording_flush(db_path: str) -> None:
        locks_held_during_flush.append(write_buffer._thread_state.locks_held)
        original_flush(db_path)

    monkeypatch.setattr(buffer, "flush", recording_flush)
    backend.log_dynamic(EXP_ID, "loss", 0.1, step=0)
    backend.log_dynamic(EXP_ID, "loss", 0.2, step=1)

    assert locks_held_during_flush == [0]


def test_write_through_commits_every_call(store: Path) -> None:
    tracker = ExperimentTracker(f"sqlite://{store}", flush_interval=0)
    exp_id = tracker.start_experiment(experiment_id=EXP_ID)

    tracker.log_dynamic("loss", 0.5, step=0, experiment_id=exp_id)
    assert _count_rows(store, "dynamic_metrics") == 1
    tracker.log_eval_sample(
        eval_id="e1", dataset_id="ds1", inputs={"x": 1}, experiment_id=exp_id
    )
    assert _count_rows(store, "evals") == 1

    assert isinstance(tracker.backend, SQLiteBackend)
    assert tracker.backend._write_buffer._flusher is None


def test_concurrent_logging_loses_nothing(backend: SQLiteBackend) -> None:
    backend._write_buffer.flush_threshold = 50
    workers = 8
    per_worker = 400
    barrier = threading.Barrier(workers)

    def log(worker: int) -> None:
        barrier.wait()
        for index in range(per_worker):
            backend.log_dynamic(EXP_ID, "implicit", worker)
            backend.log_dynamic(EXP_ID, f"worker-{worker}", index, step=index)
            _log_span(backend, f"span-{worker}-{index}")
            if index % 100 == 0:
                backend.flush(EXP_ID)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(log, range(workers)))

    data = backend.get_experiment_data(EXP_ID)
    implicit_steps = [point["step"] for point in data.dynamic_metrics["implicit"]]
    assert sorted(implicit_steps) == list(range(workers * per_worker))
    for worker in range(workers):
        assert len(data.dynamic_metrics[f"worker-{worker}"]) == per_worker
    trace = backend.get_trace(EXP_ID, "trace-1")
    assert trace is not None
    assert len(trace.spans) == workers * per_worker


def _db_path(store: Path) -> str:
    return str(store / EXP_ID / "exp.db")


def _query(store: Path, sql: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(store / EXP_ID / "exp.db")
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@contextmanager
def _locked_by_other_connection(
    backend: SQLiteBackend, store: Path
) -> Iterator[sqlite3.Connection]:
    with backend.pool.get_connection(_db_path(store)) as conn:
        conn.execute("PRAGMA busy_timeout = 20")
    other = sqlite3.connect(_db_path(store), isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    try:
        yield other
    finally:
        other.execute("COMMIT")
        other.close()


def test_sqlite_utc_now_matches_current_timestamp_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epoch = 1_700_000_000
    real_gmtime = time.gmtime
    monkeypatch.setattr(time, "gmtime", lambda: real_gmtime(epoch))
    expected = (
        sqlite3.connect(":memory:")
        .execute("SELECT datetime(?, 'unixepoch')", (epoch,))
        .fetchone()[0]
    )

    assert sqlite_backend._sqlite_utc_now() == expected == "2023-11-14 22:13:20"


def test_buffered_rows_keep_their_call_time(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = iter(range(60))
    monkeypatch.setattr(
        sqlite_backend, "_sqlite_utc_now", lambda: f"2026-01-01 00:00:{next(clock):02d}"
    )
    # 2026-01-01 00:00:00 UTC in epoch milliseconds.
    monkeypatch.setattr(
        sqlite_backend, "_utc_now_ms", lambda: 1_767_225_600_000 + next(clock) * 1000
    )

    backend.log_dynamic(EXP_ID, "loss", 0.1, step=0)
    backend.log_dynamic(EXP_ID, "loss", 0.2, step=1)
    _log_span(backend, "span-1")
    backend.log_eval_sample(EXP_ID, "e1", "ds1", inputs={"x": 1})
    backend.link_eval_sample_to_trace(EXP_ID, "ds1", "e1", "trace-1")
    backend.log_eval_sample(EXP_ID, "e2", "ds1", inputs={"x": 2})
    backend.log_eval_sample(EXP_ID, "e2", "ds1", inputs={"x": 3})
    backend.flush(EXP_ID)

    assert _query(store, "SELECT step, logged_at FROM dynamic_metrics") == [
        (0, "2026-01-01 00:00:00"),
        (1, "2026-01-01 00:00:01"),
    ]
    assert _query(store, "SELECT created_at FROM spans") == [("2026-01-01 00:00:02",)]
    assert _query(store, "SELECT created_at FROM eval_traces_bridge") == [
        ("2026-01-01 00:00:04",)
    ]
    # Replacing a sample restarts created_at, as the column default did before.
    assert _query(
        store, "SELECT id, created_at, updated_at FROM evals ORDER BY id"
    ) == [
        ("e1", "2026-01-01 00:00:03", "2026-01-01 00:00:03"),
        ("e2", "2026-01-01 00:00:06", "2026-01-01 00:00:06"),
    ]


def test_write_through_raises_row_errors(store: Path) -> None:
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.initialize_experiment(EXP_ID, "default", "write-through")

    with pytest.raises(sqlite3.IntegrityError, match="spans.name"):
        _log_span(backend, "span-bad", name=None)

    assert _count_rows(store, "spans") == 0


UNBINDABLE_CALLS: dict[str, Callable[[SQLiteBackend], None]] = {
    "metric step": lambda b: b.log_dynamic(EXP_ID, "loss", 0.1, step=Decimal(1)),  # type: ignore[arg-type]
    "metric key": lambda b: b.log_dynamic(EXP_ID, object(), 0.1, step=0),  # type: ignore[arg-type]
    "span kind": lambda b: b.log_span(EXP_ID, "t", "s", "op", Decimal(1), 1, 2),  # type: ignore[arg-type]
    "span time": lambda b: b.log_span(EXP_ID, "t", "s", "op", 0, 2**64, 2),
    "eval id": lambda b: b.log_eval_sample(EXP_ID, object(), "ds1", {"x": 1}),  # type: ignore[arg-type]
}


def _raised(call: Callable[[], None]) -> tuple[type[BaseException], str]:
    # Metric keys and steps are checked before binding, since buckets need ints.
    with pytest.raises((sqlite3.Error, OverflowError, TypeError)) as raised:
        call()
    return raised.type, str(raised.value)


@pytest.mark.parametrize("call", UNBINDABLE_CALLS.values(), ids=UNBINDABLE_CALLS)
def test_unbindable_values_raise_at_call_time_like_write_through(
    store: Path,
    call: Callable[[SQLiteBackend], None],
    caplog: pytest.LogCaptureFixture,
) -> None:
    buffered = SQLiteBackend(str(store / "buffered"), flush_interval=NO_TIMER_FLUSH)
    write_through = SQLiteBackend(str(store / "write-through"), flush_interval=0)
    for backend in (buffered, write_through):
        backend.initialize_experiment(EXP_ID, "default", "bind")

    buffered_error = _raised(lambda: call(buffered))

    assert buffered_error == _raised(lambda: call(write_through))
    with caplog.at_level(logging.WARNING):
        buffered.flush()
    assert not caplog.records


def test_bad_explicit_step_leaves_the_step_counter_alone(
    backend: SQLiteBackend,
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.1)
    with pytest.raises(TypeError):
        backend.log_dynamic(EXP_ID, "loss", 0.2, step=Decimal(5))  # type: ignore[arg-type]
    backend.log_dynamic(EXP_ID, "loss", 0.3)

    history = backend.get_experiment_metric_history(EXP_ID, "loss")
    assert [point["step"] for point in history] == [0, 1]


def test_locked_database_keeps_rows_queued_and_raises_to_the_caller(
    backend: SQLiteBackend, store: Path
) -> None:
    for step in range(3):
        backend.log_dynamic(EXP_ID, "loss", float(step), step=step)

    with _locked_by_other_connection(backend, store):
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            backend.flush(EXP_ID)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            backend.get_experiment_metric_history(EXP_ID, "loss")

    history = backend.get_experiment_metric_history(EXP_ID, "loss")
    assert [(point["step"], point["value"]) for point in history] == [
        (0, 0.0),
        (1, 1.0),
        (2, 2.0),
    ]


def test_full_queue_on_locked_database_rejects_new_rows(
    backend: SQLiteBackend, store: Path
) -> None:
    backend._write_buffer.flush_threshold = 2
    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
    backend.log_dynamic(EXP_ID, "loss", 1.0, step=1)

    with _locked_by_other_connection(backend, store):
        for step in range(2, 5):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                backend.log_dynamic(EXP_ID, "loss", float(step), step=step)
        assert len(backend._write_buffer._rows[_db_path(store)]) == 2

    backend.log_dynamic(EXP_ID, "loss", 2.0, step=2)
    history = backend.get_experiment_metric_history(EXP_ID, "loss")
    assert [point["step"] for point in history] == [0, 1, 2]


def test_timer_tick_flushes_and_retries_a_locked_database(
    backend: SQLiteBackend, store: Path, caplog: pytest.LogCaptureFixture
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.1, step=0)

    with (
        _locked_by_other_connection(backend, store),
        caplog.at_level(logging.WARNING),
    ):
        backend._write_buffer.flush_on_timer()
    assert any("retrying" in record.getMessage() for record in caplog.records)

    backend._write_buffer.flush_on_timer()

    assert _count_rows(store, "dynamic_metrics") == 1


def test_repeated_flush_failures_are_logged_at_most_every_30_seconds(
    backend: SQLiteBackend,
    store: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [1000.0]
    monkeypatch.setattr(write_buffer.time, "monotonic", lambda: now[0])
    backend.log_dynamic(EXP_ID, "loss", 0.1, step=0)

    def ticks(count: int, seconds_apart: float) -> list[str]:
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            for _ in range(count):
                backend._write_buffer.flush_on_timer()
                now[0] += seconds_apart
        return [record.getMessage() for record in caplog.records]

    with _locked_by_other_connection(backend, store):
        first = ticks(10, 0.5)
        assert len(first) == 1
        assert caplog.records[0].exc_info is not None
        now[0] += 30
        assert ticks(1, 0.5) == [
            f"Could not flush buffered rows to {_db_path(store)}; retrying in "
            f"{NO_TIMER_FLUSH}s (9 more failures since the last warning)"
        ]
        assert ticks(5, 0.5) == []

    assert ticks(1, 0.5) == []
    assert _count_rows(store, "dynamic_metrics") == 1
    backend.log_dynamic(EXP_ID, "loss", 0.2, step=1)
    with _locked_by_other_connection(backend, store):
        assert len(ticks(1, 0.5)) == 1


def test_flush_waits_for_a_flush_in_progress(
    backend: SQLiteBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    writing = threading.Event()
    release = threading.Event()
    original_write = WriteBuffer._write

    def blocking_write(
        self: WriteBuffer, conn: sqlite3.Connection, db_path: str, rows: list[Any]
    ) -> None:
        writing.set()
        release.wait()
        original_write(self, conn, db_path, rows)

    monkeypatch.setattr(WriteBuffer, "_write", blocking_write)
    backend.log_dynamic(EXP_ID, "loss", 0.1, step=0)
    timer = threading.Thread(target=backend._write_buffer.flush_on_timer)
    timer.start()
    writing.wait()
    history: list[Any] = []
    reader = threading.Thread(
        target=lambda: history.extend(
            backend.get_experiment_metric_history(EXP_ID, "loss")
        )
    )
    reader.start()

    reader.join(timeout=0.2)
    assert reader.is_alive()
    release.set()
    timer.join()
    reader.join()
    assert [point["step"] for point in history] == [0]


IN_FLIGHT_ROWS = 50


class _TimerBatchInFlight:
    """Holds the timer flusher inside its first write until `release`, then lets a
    call run on another thread and reports when that call returns or starts waiting
    (for the experiment's connection, or for the flusher thread to end)."""

    def __init__(
        self,
        store: Path,
        monkeypatch: pytest.MonkeyPatch,
        fail_first_write: bool = False,
    ) -> None:
        self._writing = threading.Event()
        self._release = threading.Event()
        self.progress = threading.Event()
        self.returned = threading.Event()
        self.errors: list[BaseException] = []
        self._thread: threading.Thread | None = None
        original_write = WriteBuffer._write
        held = False

        def holding_write(
            buffer: WriteBuffer,
            conn: sqlite3.Connection,
            db_path: str,
            rows: list[Any],
        ) -> None:
            nonlocal held
            if threading.current_thread().name == "luml-write-buffer" and not held:
                held = True
                self._writing.set()
                self._release.wait()
                if fail_first_write:
                    raise sqlite3.OperationalError("database is locked")
            original_write(buffer, conn, db_path, rows)

        monkeypatch.setattr(WriteBuffer, "_write", holding_write)
        self.backend = SQLiteBackend(str(store), flush_interval=0.001)
        buffer = self.backend._write_buffer
        # Started only once every row is queued, so its first batch holds them all.
        buffer._start_flusher = lambda: None  # type: ignore[method-assign]
        self.backend.initialize_experiment(EXP_ID, "default", "in-flight")
        for step in range(IN_FLIGHT_ROWS):
            self.backend.log_dynamic(EXP_ID, "loss", float(step), step=step)
        del buffer._start_flusher
        with buffer._lock:
            buffer._start_flusher()
        self._writing.wait()
        assert not buffer._rows
        write_lock = self.backend.pool._write_locks[_db_path(store)]
        monkeypatch.setattr(
            write_lock, "_lock", _SignallingLock(write_lock._lock, self.progress)
        )
        flusher = buffer._flusher
        assert flusher is not None
        original_join = flusher.join

        def signalling_join(timeout: float | None = None) -> None:
            self.progress.set()
            original_join(timeout)

        monkeypatch.setattr(flusher, "join", signalling_join)

    def call(self, target: Callable[[], object]) -> None:
        def run() -> None:
            try:
                target()
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.returned.set()
                self.progress.set()

        self._thread = threading.Thread(target=run)
        self._thread.start()
        self.progress.wait()

    def release(self) -> None:
        self._release.set()
        assert self._thread is not None
        self._thread.join()


def test_close_waits_for_a_timer_flush_in_flight(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_flight = _TimerBatchInFlight(store, monkeypatch)
    flusher = in_flight.backend._write_buffer._flusher
    assert flusher is not None

    in_flight.call(in_flight.backend.close)

    assert not in_flight.returned.is_set()
    in_flight.release()
    assert in_flight.errors == []
    assert not flusher.is_alive()
    assert _count_rows(store, "metric_points") == IN_FLIGHT_ROWS


def test_flush_all_waits_for_a_timer_flush_in_flight(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_flight = _TimerBatchInFlight(store, monkeypatch)

    in_flight.call(in_flight.backend.flush)

    assert not in_flight.returned.is_set()
    in_flight.release()
    assert in_flight.errors == []
    assert _count_rows(store, "metric_points") == IN_FLIGHT_ROWS
    in_flight.backend.close()


def test_flush_of_one_experiment_waits_for_a_timer_flush_in_flight(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_flight = _TimerBatchInFlight(store, monkeypatch)
    history: list[dict[str, Any]] = []

    def flush_and_read() -> None:
        in_flight.backend.flush(EXP_ID)
        assert _count_rows(store, "metric_points") == IN_FLIGHT_ROWS
        history.extend(in_flight.backend.get_experiment_metric_history(EXP_ID, "loss"))

    in_flight.call(flush_and_read)

    assert not in_flight.returned.is_set()
    in_flight.release()
    assert in_flight.errors == []
    assert len(history) == IN_FLIGHT_ROWS
    in_flight.backend.close()


def test_export_waits_for_a_timer_flush_in_flight(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_flight = _TimerBatchInFlight(store, monkeypatch)
    exported: list[int] = []

    def export() -> None:
        with in_flight.backend.snapshot_experiment(EXP_ID) as snapshot:
            conn = sqlite3.connect(snapshot.path)
            try:
                exported.append(
                    conn.execute("SELECT COUNT(*) FROM metric_points").fetchone()[0]
                )
            finally:
                conn.close()

    in_flight.call(export)

    assert not in_flight.returned.is_set()
    in_flight.release()
    assert in_flight.errors == []
    assert exported == [IN_FLIGHT_ROWS]
    in_flight.backend.close()


def test_close_writes_a_timer_batch_whose_write_failed_in_flight(
    store: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    in_flight = _TimerBatchInFlight(store, monkeypatch, fail_first_write=True)

    with caplog.at_level(logging.WARNING):
        in_flight.call(in_flight.backend.close)
        assert not in_flight.returned.is_set()
        in_flight.release()

    assert in_flight.errors == []
    assert any("retrying" in record.getMessage() for record in caplog.records)
    assert _count_rows(store, "metric_points") == IN_FLIGHT_ROWS


def test_flusher_that_cannot_start_leaves_rows_to_close_and_starts_later(
    store: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    backend = SQLiteBackend(str(store), flush_interval=NO_TIMER_FLUSH)
    backend.initialize_experiment(EXP_ID, "default", "no-timer")
    original_start = threading.Thread.start

    def failing_start(thread: threading.Thread) -> None:
        if thread.name == "luml-write-buffer":
            raise RuntimeError("can't start new thread")
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", failing_start)
    with caplog.at_level(logging.WARNING):
        backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
        backend.log_dynamic(EXP_ID, "loss", 1.0, step=1)
    assert backend._write_buffer._flusher is None
    assert [r.getMessage() for r in caplog.records if "timer" in r.getMessage()] == [
        "Could not start the write buffer's flush timer; buffered rows are written "
        "at the next flush or close"
    ]

    monkeypatch.setattr(threading.Thread, "start", original_start)
    backend.log_dynamic(EXP_ID, "loss", 2.0, step=2)
    flusher = backend._write_buffer._flusher
    assert flusher is not None
    assert flusher.is_alive()

    backend.close()

    assert not flusher.is_alive()
    assert _count_rows(store, "metric_points") == 3


def test_process_that_closes_and_exits_at_once_keeps_every_row(store: Path) -> None:
    script = """
import os, sys, time
from luml.experiments.backends.sqlite import SQLiteBackend
backend = SQLiteBackend(sys.argv[1], flush_interval=0.05)
backend.initialize_experiment(sys.argv[2], "default", "exit")
for step in range(int(sys.argv[3])):
    backend.log_dynamic(sys.argv[2], "loss", step * 0.5, step=step)
# Closes as soon as the timer takes the last rows, most often while it writes them.
while backend._write_buffer._rows:
    time.sleep(0)
backend.close()
os._exit(0)
"""
    rows = 20_000
    subprocess.run(
        [sys.executable, "-c", script, str(store), EXP_ID, str(rows)],
        check=True,
        capture_output=True,
        timeout=120,
    )

    assert _count_rows(store, "metric_points") == rows


def test_delete_discards_buffered_rows(backend: SQLiteBackend, store: Path) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.1, step=0)
    _log_span(backend, "span-1")

    backend.delete_experiment(EXP_ID)
    backend.flush()

    assert _db_path(store) not in backend.pool.get_stats()["connections"]
    backend.initialize_experiment(EXP_ID, "default", "recreated")
    backend.log_dynamic(EXP_ID, "acc", 0.5)
    backend.flush(EXP_ID)
    assert _query(store, "SELECT key, step FROM dynamic_metrics") == [("acc", 0)]
    assert _count_rows(store, "spans") == 0


def test_close_removes_its_exit_hook(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered: set[Callable[[], None]] = set()
    monkeypatch.setattr(atexit, "register", lambda func, *args: registered.add(func))
    monkeypatch.setattr(atexit, "unregister", registered.discard)
    backend = SQLiteBackend(str(store), flush_interval=NO_TIMER_FLUSH)
    buffer_hook = backend._write_buffer._exit_hook
    assert buffer_hook in registered

    backend.close()

    assert buffer_hook not in registered


def test_interpreter_exit_flushes_rows_left_in_the_buffer(store: Path) -> None:
    script = """
import sys
from luml.experiments.backends.sqlite import SQLiteBackend
backend = SQLiteBackend(sys.argv[1], flush_interval=3600)
backend.initialize_experiment(sys.argv[2], "default", "exit")
for step in range(20):
    backend.log_dynamic(sys.argv[2], "loss", step * 0.5)
backend.log_span(sys.argv[2], "t", "s", "op", 1000, 2000)
"""
    subprocess.run(
        [sys.executable, "-c", script, str(store), EXP_ID],
        check=True,
        capture_output=True,
        timeout=60,
    )

    assert _count_rows(store, "metric_points") == 20
    assert _count_rows(store, "spans") == 1


class _ScriptedStop(threading.Event):
    def __init__(self, ticks: int) -> None:
        super().__init__()
        self.ticks = ticks
        self.waits: list[float] = []

    def wait(self, timeout: float | None = None) -> bool:
        assert timeout is not None
        self.waits.append(timeout)
        return len(self.waits) > self.ticks


def test_timer_period_counts_from_the_start_of_each_flush() -> None:
    now = 0.0
    flush_durations = [0.2, 0.7, 0.1]

    class SlowBuffer:
        def flush_on_timer(self) -> None:
            nonlocal now
            now += flush_durations.pop(0)

    buffer = SlowBuffer()
    stop = _ScriptedStop(ticks=3)

    WriteBuffer._run_flusher(
        weakref.ref(buffer),  # type: ignore[arg-type]
        stop,
        0.5,
        clock=lambda: now,
    )

    assert stop.waits == pytest.approx([0.5, 0.3, 0.0, 0.4])


class _SignallingLock:
    """Wraps a lock and reports when a thread finds it taken."""

    def __init__(
        self,
        lock: "threading.Lock | threading.RLock",
        contended: threading.Event | None = None,
    ) -> None:
        self._lock = lock
        self.contended = contended or threading.Event()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if self._lock.acquire(blocking=False):
            return True
        self.contended.set()
        return blocking and self._lock.acquire(True, timeout)

    def release(self) -> None:
        self._lock.release()


FORK_TIMEOUT = 30.0


class _PausedThread:
    """Runs a call on a thread that stops where it calls `pause`, until another thread
    asks for the lock of the experiment's connection."""

    def __init__(
        self, backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_lock = backend.pool._write_locks[_db_path(store)]
        self.signalling = _SignallingLock(write_lock._lock)
        monkeypatch.setattr(write_lock, "_lock", self.signalling)
        self._inside = threading.Event()
        self._thread: threading.Thread | None = None

    def pause(self) -> None:
        if threading.current_thread() is self._thread and not self._inside.is_set():
            self._inside.set()
            self.signalling.contended.wait(FORK_TIMEOUT)

    def start(self, call: Callable[[], object]) -> None:
        self._thread = threading.Thread(target=call)
        self._thread.start()
        self._inside.wait()

    def resume(self) -> None:
        self.signalling.contended.set()
        if self._thread is not None:
            self._thread.join()


def _fork_child(child: Callable[[], bool]) -> int:
    """Forks from a helper thread, so a fork that never returns fails the test."""
    exit_codes: list[int] = []

    def fork() -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pid = os.fork()
        if pid == 0:
            exit_code = 1
            try:
                signal.alarm(int(FORK_TIMEOUT))
                if child():
                    exit_code = 0
            finally:
                os._exit(exit_code)
        _, status = os.waitpid(pid, 0)
        exit_codes.append(os.waitstatus_to_exitcode(status))

    forker = threading.Thread(target=fork, daemon=True)
    forker.start()
    forker.join(FORK_TIMEOUT * 2)
    if forker.is_alive():
        pytest.fail("fork() did not return")
    return exit_codes[0]


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_forked_child_writes_while_a_parent_thread_is_inside_a_flush(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=1)
    flusher = _PausedThread(backend, store, monkeypatch)
    with backend.pool.get_connection(_db_path(store)) as conn:
        changes_before_flush = conn.total_changes

        def pause_after_first_row() -> int:
            if conn.total_changes > changes_before_flush:
                flusher.pause()
            return 0

        conn.set_progress_handler(pause_after_first_row, 1)
    flusher.start(lambda: backend.flush(EXP_ID))

    def child() -> bool:
        backend.log_dynamic(EXP_ID, "loss", 1.0, step=2)
        backend.log_static(EXP_ID, "child", True)
        backend.flush(EXP_ID)
        return _query(store, "SELECT step FROM dynamic_metrics ORDER BY step") == [
            (0,),
            (1,),
            (2,),
        ]

    exit_code = _fork_child(child)
    flusher.resume()

    assert exit_code == 0


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_forked_child_exports_while_a_parent_thread_is_inside_a_read(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
    backend.flush(EXP_ID)
    reader = _PausedThread(backend, store, monkeypatch)

    def pause_reader() -> int:
        reader.pause()
        return 0

    with backend.pool.get_connection(_db_path(store)) as conn:
        conn.set_progress_handler(pause_reader, 1)
    reader.start(lambda: backend.get_experiment_metric_history(EXP_ID, "loss"))

    def child() -> bool:
        backend.log_dynamic(EXP_ID, "loss", 1.0, step=1)
        exported = Path(backend.export_experiment_db(EXP_ID).path)
        copy = exported.with_name("child-export.db")
        copy.write_bytes(exported.read_bytes())
        conn = sqlite3.connect(copy)
        try:
            steps = conn.execute("SELECT step FROM dynamic_metrics").fetchall()
        finally:
            conn.close()
        return sorted(steps) == [(0,), (1,)]

    exit_code = _fork_child(child)
    reader.resume()

    assert exit_code == 0


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_forked_child_logs_implicit_steps_while_a_parent_thread_is_in_log_dynamic(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0)
    backend.flush(EXP_ID)
    buffer = backend._write_buffer
    inside = threading.Event()
    release = threading.Event()
    original_enqueue = buffer.enqueue

    def pausing_enqueue(*args: Any, **kwargs: Any) -> bool:  # noqa: ANN401
        if threading.current_thread() is not threading.main_thread():
            inside.set()
            release.wait()
        return original_enqueue(*args, **kwargs)

    monkeypatch.setattr(buffer, "enqueue", pausing_enqueue)
    logger_thread = threading.Thread(
        target=backend.log_dynamic, args=(EXP_ID, "loss", 1.0)
    )
    logger_thread.start()
    assert inside.wait(FORK_TIMEOUT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        pid = os.fork()
    if pid == 0:
        exit_code = 1
        try:
            signal.alarm(10)
            backend.log_dynamic(EXP_ID, "loss", 2.0)
            backend.log_dynamic(EXP_ID, "loss", 3.0)
            backend.flush(EXP_ID)
            if _query(store, "SELECT step, value FROM dynamic_metrics") == [
                (0, 0.0),
                (1, 2.0),
                (2, 3.0),
            ]:
                exit_code = 0
        finally:
            os._exit(exit_code)

    _, status = os.waitpid(pid, 0)
    release.set()
    logger_thread.join()

    assert os.waitstatus_to_exitcode(status) == 0


DeleteRace = Callable[[SQLiteBackend], None]
CALLS_RACING_A_DELETE: dict[str, DeleteRace] = {
    "implicit metric": lambda b: b.log_dynamic(EXP_ID, "loss", 0.1),
    "implicit metric, new key": lambda b: b.log_dynamic(EXP_ID, "acc", 0.1),
    "explicit metric": lambda b: b.log_dynamic(EXP_ID, "loss", 0.1, step=7),
    "span": lambda b: _log_span(b, "old-span"),
    "eval": lambda b: b.log_eval_sample(EXP_ID, "old-eval", "ds1", {"x": 1}),
}


def _delete_inside_make_room(
    backend: SQLiteBackend, monkeypatch: pytest.MonkeyPatch, *, recreate: bool
) -> None:
    """Runs the delete where another thread can run it: after the log call has found
    the experiment and before it queues its row."""
    original_make_room = backend._write_buffer.make_room

    def make_room_with_delete(db_path: str) -> None:
        monkeypatch.setattr(backend._write_buffer, "make_room", original_make_room)
        backend.delete_experiment(EXP_ID)
        if recreate:
            backend.initialize_experiment(EXP_ID, "default", "recreated")
        original_make_room(db_path)

    monkeypatch.setattr(backend._write_buffer, "make_room", make_room_with_delete)


@pytest.mark.parametrize("flush_interval", [NO_TIMER_FLUSH, 0], ids=["buffered", "wt"])
@pytest.mark.parametrize(
    "call", CALLS_RACING_A_DELETE.values(), ids=CALLS_RACING_A_DELETE
)
def test_log_call_racing_delete_never_reaches_the_recreated_experiment(
    store: Path,
    monkeypatch: pytest.MonkeyPatch,
    flush_interval: float,
    call: DeleteRace,
) -> None:
    backend = SQLiteBackend(str(store), flush_interval=flush_interval)
    backend.initialize_experiment(EXP_ID, "default", "old")
    backend.log_dynamic(EXP_ID, "loss", 0.0)
    _delete_inside_make_room(backend, monkeypatch, recreate=True)

    with pytest.raises(ValueError, match="not initialized"):
        call(backend)
    backend.log_dynamic(EXP_ID, "loss", 0.5)
    backend.flush()

    assert _query(store, "SELECT step, value FROM dynamic_metrics") == [(0, 0.5)]
    assert _count_rows(store, "spans") == 0
    assert _count_rows(store, "evals") == 0


@pytest.mark.parametrize("flush_interval", [NO_TIMER_FLUSH, 0], ids=["buffered", "wt"])
@pytest.mark.parametrize(
    "call", CALLS_RACING_A_DELETE.values(), ids=CALLS_RACING_A_DELETE
)
def test_log_call_racing_delete_leaves_nothing_behind(
    store: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    flush_interval: float,
    call: DeleteRace,
) -> None:
    backend = SQLiteBackend(str(store), flush_interval=flush_interval)
    backend.initialize_experiment(EXP_ID, "default", "old")
    backend.log_dynamic(EXP_ID, "loss", 0.0)
    _delete_inside_make_room(backend, monkeypatch, recreate=False)

    with pytest.raises(ValueError, match="not initialized"):
        call(backend)
    with caplog.at_level(logging.WARNING):
        backend._write_buffer.flush_on_timer()

    assert not (store / EXP_ID).exists()
    assert not caplog.records


def test_delete_waits_for_a_log_call_seeding_its_step_counter(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeding = threading.Event()
    release = threading.Event()
    original_connection = backend._get_experiment_connection

    def pausing_connection(experiment_id: str, *, write: bool = False) -> Any:  # noqa: ANN401
        seeding.set()
        release.wait()
        return original_connection(experiment_id, write=write)

    monkeypatch.setattr(backend, "_get_experiment_connection", pausing_connection)
    logger_thread = threading.Thread(
        target=backend.log_dynamic, args=(EXP_ID, "loss", 0.1)
    )
    logger_thread.start()
    seeding.wait()
    deleter = threading.Thread(target=backend.delete_experiment, args=(EXP_ID,))
    deleter.start()

    deleter.join(timeout=0.2)
    deleted_while_seeding = not deleter.is_alive()
    release.set()
    logger_thread.join()
    deleter.join()
    assert not deleted_while_seeding
    assert not (store / EXP_ID).exists()


def _abandon_cyclic_tracker(store: Path, flush_interval: float) -> SQLiteBackend:
    """Leaves an active tracker in a reference cycle, so only the collector frees it."""
    tracker = ExperimentTracker(f"sqlite://{store}", flush_interval=flush_interval)
    tracker.start_experiment(experiment_id=EXP_ID)
    tracker.cycle = tracker  # type: ignore[attr-defined]
    assert isinstance(tracker.backend, SQLiteBackend)
    return tracker.backend


@pytest.fixture
def collector_paused() -> Iterator[None]:
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def _run_with_watchdog(target: Callable[[], None], backend: SQLiteBackend) -> None:
    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(timeout=10)
    if worker.is_alive():
        # Abandons the deadlocked locks, as a fork does, so exit hooks do not hang.
        backend._write_buffer._reset_after_fork()
        pytest.fail("deadlocked")


@pytest.mark.usefixtures("collector_paused")
def test_collecting_a_tracker_inside_the_flusher_write_does_not_deadlock(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _abandon_cyclic_tracker(store, NO_TIMER_FLUSH)
    for step in range(3):
        backend.log_dynamic(EXP_ID, "loss", float(step), step=step)
    original_write = WriteBuffer._write
    collected: list[int] = []

    def collecting_write(
        self: WriteBuffer, conn: sqlite3.Connection, db_path: str, rows: list[Any]
    ) -> None:
        collected.append(gc.collect())
        original_write(self, conn, db_path, rows)

    monkeypatch.setattr(WriteBuffer, "_write", collecting_write)

    _run_with_watchdog(backend._write_buffer.flush_on_timer, backend)

    assert len(collected) == 1
    assert collected[0] > 0
    assert _count_rows(store, "dynamic_metrics") == 3
    experiment = backend.get_experiment(EXP_ID)
    assert experiment is not None
    assert experiment.status == "error"


@pytest.mark.usefixtures("collector_paused")
def test_collecting_a_tracker_while_appending_does_not_deadlock(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _abandon_cyclic_tracker(store, NO_TIMER_FLUSH)
    buffer = backend._write_buffer
    original_start = buffer._start_flusher
    collected: list[int] = []

    def collecting_start() -> None:
        collected.append(gc.collect())
        original_start()

    monkeypatch.setattr(buffer, "_start_flusher", collecting_start)

    _run_with_watchdog(lambda: _log_span(backend, "span-1"), backend)

    assert len(collected) == 1
    assert collected[0] > 0
    assert _count_rows(store, "spans") == 1
    experiment = backend.get_experiment(EXP_ID)
    assert experiment is not None
    assert experiment.status == "error"


def test_reader_racing_delete_finds_no_experiment_and_leaves_nothing_behind(
    backend: SQLiteBackend, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0)
    backend.flush(EXP_ID)
    group_id = backend.list_groups()[0].id
    reader_progressed = threading.Event()
    pool_lock = backend.pool.lock
    monkeypatch.setattr(
        pool_lock, "_lock", _SignallingLock(pool_lock._lock, reader_progressed)
    )
    read_results: list[object] = []

    def read() -> None:
        try:
            keys = backend.get_group_experiments_dynamic_metrics_keys(group_id)
            read_results.append(keys)
        except Exception as error:  # noqa: BLE001
            read_results.append(repr(error))
        finally:
            reader_progressed.set()

    original_rmtree = sqlite_backend.shutil.rmtree

    def rmtree_racing_a_reader(path: Path) -> None:
        reader.start()
        reader_progressed.wait(FORK_TIMEOUT)
        original_rmtree(path)

    reader = threading.Thread(target=read)
    monkeypatch.setattr(sqlite_backend.shutil, "rmtree", rmtree_racing_a_reader)
    backend.delete_experiment(EXP_ID)
    reader.join()
    monkeypatch.setattr(sqlite_backend.shutil, "rmtree", original_rmtree)

    assert read_results in (
        [[]],
        [repr(ValueError(f"Experiment {EXP_ID} not found"))],
    )
    backend.initialize_experiment(EXP_ID, "default", "recreated")
    backend.log_dynamic(EXP_ID, "loss", 0.5)
    backend.flush(EXP_ID)
    assert _query(store, "SELECT step, value FROM dynamic_metrics") == [(0, 0.5)]


def test_connection_held_through_delete_is_not_reused_by_the_recreated_experiment(
    backend: SQLiteBackend, store: Path
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0)
    backend.flush(EXP_ID)

    with backend.pool.get_connection(_db_path(store)) as held:
        backend.delete_experiment(EXP_ID)
        backend.initialize_experiment(EXP_ID, "default", "recreated")
        backend.log_dynamic(EXP_ID, "loss", 0.5)
        backend.flush(EXP_ID)
        rows = _query(store, "SELECT step, value FROM dynamic_metrics")
        old_rows = held.execute("SELECT step, value FROM dynamic_metrics").fetchall()

    assert rows == [(0, 0.5)]
    assert old_rows == [(0, 0.0)]
    assert backend.get_experiment_metric_history(EXP_ID, "loss")[0]["value"] == 0.5


def _log_large_spans(backend: SQLiteBackend, first: int, count: int) -> None:
    for index in range(first, first + count):
        backend.log_span(
            EXP_ID,
            trace_id="trace-1",
            span_id=f"span-{index}",
            name="op",
            start_time_unix_nano=index,
            end_time_unix_nano=index + 1,
            attributes={"payload": "x" * 64_000},
        )
    backend.flush(EXP_ID)


def test_wal_shrinks_back_once_a_long_read_ends(
    backend: SQLiteBackend, store: Path
) -> None:
    wal = store / EXP_ID / "exp.db-wal"
    _log_large_spans(backend, 0, 1)
    reader = sqlite3.connect(_db_path(store), isolation_level=None)
    reader.execute("BEGIN")
    reader.execute("SELECT COUNT(*) FROM spans").fetchone()
    for batch in range(1, 13):
        _log_large_spans(backend, batch * 30, 30)
    grown_to = wal.stat().st_size
    reader.execute("COMMIT")
    reader.close()

    for batch in range(13, 15):
        _log_large_spans(backend, batch * 30, 30)

    assert grown_to > 2 * sqlite_backend.WAL_SIZE_LIMIT
    assert wal.stat().st_size <= sqlite_backend.WAL_SIZE_LIMIT
    assert _count_rows(store, "spans") == 1 + 14 * 30


def test_reads_of_one_database_take_turns_on_its_connection(
    backend: SQLiteBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.log_static(EXP_ID, "lr", 0.1)
    backend.log_dynamic(EXP_ID, "loss", 0.5, step=0)
    reading = threading.Event()
    release = threading.Event()
    original_convert = SQLiteBackend._convert_static_param_value

    def pausing_convert(value: str, value_type: str) -> Any:  # noqa: ANN401
        reading.set()
        release.wait()
        return original_convert(value, value_type)

    monkeypatch.setattr(
        SQLiteBackend, "_convert_static_param_value", staticmethod(pausing_convert)
    )
    slow_reader = threading.Thread(target=backend.get_experiment_data, args=(EXP_ID,))
    slow_reader.start()
    reading.wait()
    history: list[Any] = []
    reader = threading.Thread(
        target=lambda: history.extend(
            backend.get_experiment_metric_history(EXP_ID, "loss")
        )
    )
    reader.start()

    reader.join(timeout=0.2)
    read_concurrently = not reader.is_alive()
    release.set()
    slow_reader.join()
    reader.join()
    assert not read_concurrently
    assert [point["step"] for point in history] == [0]
