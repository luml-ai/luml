import multiprocessing
import sqlite3
import warnings
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from multiprocessing.context import BaseContext
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker

# Only the exit path can write a row: the timer never fires during a test.
NO_TIMER_FLUSH = 3600.0
EXP_ID = "process-exp"
CHILD_TIMEOUT = 30.0
START_METHODS = multiprocessing.get_all_start_methods()

needs_fork = pytest.mark.skipif("fork" not in START_METHODS, reason="needs fork")

_inherited: SQLiteBackend | None = None
_own: SQLiteBackend | None = None


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "experiments"


@pytest.fixture
def backend(store: Path) -> Iterator[SQLiteBackend]:
    global _inherited
    backend = SQLiteBackend(str(store), flush_interval=NO_TIMER_FLUSH)
    backend.initialize_experiment(EXP_ID, "default", "processes")
    _inherited = backend
    yield backend
    _inherited = None
    backend.close()


def _query(store: Path, sql: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(store / EXP_ID / "exp.db")
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _points(store: Path) -> list[tuple[int, float]]:
    return _query(store, "SELECT step, value FROM dynamic_metrics ORDER BY step")


@contextmanager
def _forking_with_threads() -> Iterator[None]:
    # The parent's flusher thread is running; the child resets what it inherited.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield


def _run_child(
    context: BaseContext, target: Callable[..., None], *args: object
) -> int | None:
    with _forking_with_threads():
        process = context.Process(target=target, args=args)
        process.start()
    process.join(CHILD_TIMEOUT)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("child process did not exit")
    return process.exitcode


def _log_point(step: int) -> int:
    assert _inherited is not None
    _inherited.log_dynamic(EXP_ID, "loss", step * 0.5, step=step)
    return step


def _log_span() -> None:
    assert _inherited is not None
    _inherited.log_span(EXP_ID, "trace-1", "span-1", "op", 1000, 2000)


def _log_eval() -> None:
    assert _inherited is not None
    _inherited.log_eval_sample(EXP_ID, "eval-1", "ds1", {"x": 1})


def _log_through_tracker(tracker: ExperimentTracker) -> None:
    tracker.log_dynamic("loss", 1.0, step=1, experiment_id=EXP_ID)


def _log_through_own_backend(store: str) -> None:
    global _own
    _own = SQLiteBackend(store, flush_interval=NO_TIMER_FLUSH)
    _own.log_dynamic(EXP_ID, "loss", 1.0, step=1)


@needs_fork
def test_fork_child_that_returns_writes_its_points_but_not_the_parents(
    backend: SQLiteBackend, store: Path
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)

    exit_code = _run_child(multiprocessing.get_context("fork"), _log_point, 1)

    assert exit_code == 0
    assert _points(store) == [(1, 0.5)]
    backend.close()
    assert _points(store) == [(0, 0.0), (1, 0.5)]


@needs_fork
@pytest.mark.parametrize(
    ("log", "table"), [(_log_span, "spans"), (_log_eval, "evals")], ids=["span", "eval"]
)
def test_fork_child_that_returns_writes_its_rows(
    backend: SQLiteBackend, store: Path, log: Callable[[], None], table: str
) -> None:
    exit_code = _run_child(multiprocessing.get_context("fork"), log)

    assert exit_code == 0
    assert _query(store, f"SELECT COUNT(*) FROM {table}") == [(1,)]


@needs_fork
def test_fork_child_that_returns_writes_points_logged_through_a_tracker(
    store: Path,
) -> None:
    tracker = ExperimentTracker(f"sqlite://{store}", flush_interval=NO_TIMER_FLUSH)
    tracker.start_experiment(experiment_id=EXP_ID)
    tracker.log_dynamic("loss", 0.0, step=0, experiment_id=EXP_ID)

    exit_code = _run_child(
        multiprocessing.get_context("fork"), _log_through_tracker, tracker
    )

    assert exit_code == 0
    assert _points(store) == [(1, 1.0)]
    assert isinstance(tracker.backend, SQLiteBackend)
    tracker.backend.close()
    assert _points(store) == [(0, 0.0), (1, 1.0)]


@pytest.mark.parametrize(
    "method",
    [
        pytest.param(
            method,
            marks=pytest.mark.skipif(
                method not in START_METHODS, reason=f"needs {method}"
            ),
        )
        for method in ("fork", "forkserver")
    ],
)
def test_child_that_returns_writes_points_of_a_backend_it_created(
    backend: SQLiteBackend, store: Path, method: str
) -> None:
    exit_code = _run_child(
        multiprocessing.get_context(method), _log_through_own_backend, str(store)
    )

    assert exit_code == 0
    assert _points(store) == [(1, 1.0)]


@needs_fork
def test_pool_workers_closed_and_joined_write_every_point_once(
    backend: SQLiteBackend, store: Path
) -> None:
    backend.log_dynamic(EXP_ID, "loss", 0.0, step=0)
    steps = list(range(1, 9))
    with _forking_with_threads():
        pool = multiprocessing.get_context("fork").Pool(2)
    try:
        assert pool.map_async(_log_point, steps).get(CHILD_TIMEOUT) == steps
        pool.close()
        pool.join()
    finally:
        pool.terminate()

    assert _points(store) == [(step, step * 0.5) for step in steps]
    backend.close()
    assert _points(store) == [(step, step * 0.5) for step in [0, *steps]]


@needs_fork
def test_process_pool_executor_workers_write_every_point_once(
    backend: SQLiteBackend, store: Path
) -> None:
    steps = list(range(1, 9))
    with (
        _forking_with_threads(),
        ProcessPoolExecutor(2, mp_context=multiprocessing.get_context("fork")) as pool,
    ):
        assert list(pool.map(_log_point, steps, timeout=CHILD_TIMEOUT)) == steps

    assert _points(store) == [(step, step * 0.5) for step in steps]
