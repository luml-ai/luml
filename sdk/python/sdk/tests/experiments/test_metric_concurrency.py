import contextlib
import multiprocessing
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends import metric_store
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import assert_bucket_invariants, make_store

EXP_ID = "exp"
KEYS = ["loss", "acc", "lr"]


def _db(store: Path) -> Path:
    return store / EXP_ID / "exp.db"


def _check(store: Path) -> None:
    conn = sqlite3.connect(_db(store))
    try:
        assert_bucket_invariants(conn)
    finally:
        conn.close()


def _points(store: Path) -> dict[str, dict[int, float]]:
    conn = sqlite3.connect(_db(store))
    try:
        points: dict[str, dict[int, float]] = {}
        for key, step, value in conn.execute(
            "SELECT key, step, value FROM dynamic_metrics"
        ):
            points.setdefault(key, {})[step] = value
        return points
    finally:
        conn.close()


def _value(writer: int, key: str, step: int) -> float:
    return writer * 1_000_000 + KEYS.index(key) * 100_000 + step


def _write_overlapping(backend: SQLiteBackend, writer: int, steps: int) -> None:
    for step in range(steps):
        for key in KEYS:
            # Every writer overwrites the same steps, some of them out of order.
            target = step if step % 7 else steps - step
            backend.log_dynamic(EXP_ID, key, _value(writer, key, target), step=target)


def _assert_values_from_writers(store: Path, writers: int, steps: int) -> None:
    points = _points(store)
    assert set(points) == set(KEYS)
    targets = {step if step % 7 else steps - step for step in range(steps)}
    for key, by_step in points.items():
        assert set(by_step) == targets
        for step, value in by_step.items():
            assert value in {_value(writer, key, step) for writer in range(writers)}


@pytest.mark.parametrize("flush_interval", [0.01, 0.0])
def test_threads_writing_the_same_keys_and_steps(
    tmp_path: Path, flush_interval: float
) -> None:
    store = tmp_path / "store"
    make_store(store, EXP_ID)
    backend = SQLiteBackend(str(store), flush_interval=flush_interval)
    threads = [
        threading.Thread(target=_write_overlapping, args=(backend, writer, 300))
        for writer in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    backend.close()

    _check(store)
    _assert_values_from_writers(store, 6, 300)


def _process_writer(store: str, writer: int, flush_interval: float) -> None:
    backend = SQLiteBackend(store, flush_interval=flush_interval)
    _write_overlapping(backend, writer, 400)
    backend.close()


@pytest.mark.parametrize("flush_interval", [0.01, 0.0])
def test_processes_writing_the_same_keys_and_steps(
    tmp_path: Path, flush_interval: float
) -> None:
    store = tmp_path / "store"
    make_store(store, EXP_ID)
    context = multiprocessing.get_context("spawn")
    children = [
        context.Process(
            target=_process_writer, args=(str(store), writer, flush_interval)
        )
        for writer in range(4)
    ]
    for child in children:
        child.start()
    for child in children:
        child.join(120)
        assert child.exitcode == 0

    _check(store)
    _assert_values_from_writers(store, 4, 400)


def _killed_writer(store: str, phase: str, fatal_flush: int) -> None:
    refresh = metric_store.refresh_buckets
    calls = 0

    def dying_refresh(conn: sqlite3.Connection, touched: Any) -> None:  # noqa: ANN401
        nonlocal calls
        calls += 1
        if calls == fatal_flush:
            if phase == "after_buckets":
                refresh(conn, touched)
            os._exit(0)
        refresh(conn, touched)

    metric_store.refresh_buckets = dying_refresh
    backend = SQLiteBackend(store, flush_interval=3600)
    for step in range(100_000):
        backend.log_dynamic(EXP_ID, "loss", float(step) * 0.5)
    backend.close()
    os._exit(1)


@pytest.mark.parametrize("phase", ["before_buckets", "after_buckets"])
def test_hard_kill_mid_flush_leaves_a_consistent_prefix(
    tmp_path: Path, phase: str
) -> None:
    store = tmp_path / "store"
    make_store(store, EXP_ID)
    context = multiprocessing.get_context("spawn")
    child = context.Process(target=_killed_writer, args=(str(store), phase, 4))
    child.start()
    child.join(120)
    assert child.exitcode == 0

    _check(store)
    steps = _points(store)["loss"]
    assert steps, "earlier flushes committed"
    assert sorted(steps) == list(range(len(steps)))
    assert all(value == step * 0.5 for step, value in steps.items())

    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.log_dynamic(EXP_ID, "loss", -1.0)
    assert backend.get_metric_catalog(EXP_ID).metrics[0].count == len(steps) + 1
    backend.close()
    _check(store)


def test_delete_and_recreate_while_logging_never_uses_a_stale_metric_id(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    make_store(store, EXP_ID)
    backend = SQLiteBackend(str(store), flush_interval=0.005)
    stop = threading.Event()

    def log() -> None:
        step = 0
        while not stop.is_set():
            for index in range(20):
                # ValueError while the experiment is being deleted.
                with contextlib.suppress(ValueError):
                    backend.log_dynamic(EXP_ID, f"k{index}", float(index), step=step)
            step += 1

    logger = threading.Thread(target=log)
    logger.start()
    try:
        for cycle in range(15):
            backend.flush()
            _check_key_values(store)
            backend.delete_experiment(EXP_ID)
            backend.initialize_experiment(EXP_ID, name=f"cycle-{cycle}")
            # A different number of keys registered first in each incarnation
            # gives the logged keys other ids, so a stale id lands on a wrong key.
            for decoy in range(cycle % 4 + 1):
                backend.log_dynamic(EXP_ID, f"decoy{decoy}", -1.0, step=0)
            threading.Event().wait(0.02)
    finally:
        stop.set()
        logger.join()
    backend.flush()
    _check_key_values(store)
    backend.close()


def _check_key_values(store: Path) -> None:
    conn = sqlite3.connect(_db(store))
    try:
        assert_bucket_invariants(conn)
        for key, value in conn.execute("SELECT key, value FROM dynamic_metrics"):
            expected = -1.0 if key.startswith("decoy") else float(key[1:])
            assert value == expected, (key, value)
    finally:
        conn.close()


def test_a_database_re_created_by_another_backend_gets_fresh_metric_ids(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    make_store(store, EXP_ID)
    first = SQLiteBackend(str(store), flush_interval=0)
    first.log_dynamic(EXP_ID, "loss", 1.0, step=0)
    second = SQLiteBackend(str(store), flush_interval=0)
    second.delete_experiment(EXP_ID)
    second.initialize_experiment(EXP_ID)
    second.log_dynamic(EXP_ID, "acc", 0.5, step=0)
    # An idle connection is closed by eviction or end_experiment.
    first.pool.close_all()

    first.log_dynamic(EXP_ID, "loss", 2.0, step=1)

    assert _points(store) == {"acc": {0: 0.5}, "loss": {1: 2.0}}
    _check(store)
    first.close()
    second.close()


def _cached_metric_ids(backend: SQLiteBackend) -> dict[str, int]:
    hook = backend._write_buffer._hook
    assert isinstance(hook, metric_store.MetricWriteHook)
    db_path = _db(backend.base_path)
    with backend.pool.get_connection(db_path, create=False) as conn:
        return hook.cached_ids(conn, str(db_path))


def _backend_with_cached_ids(store: Path) -> SQLiteBackend:
    make_store(store, EXP_ID)
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.log_dynamic(EXP_ID, "loss", 1.0, step=0)
    assert _cached_metric_ids(backend) == {"loss": 1}
    return backend


def test_discarding_a_database_forgets_its_metric_ids(tmp_path: Path) -> None:
    backend = _backend_with_cached_ids(tmp_path / "store")
    backend._write_buffer.discard(str(_db(backend.base_path)))
    assert _cached_metric_ids(backend) == {}
    backend.close()


def test_creating_a_database_forgets_its_metric_ids(tmp_path: Path) -> None:
    backend = _backend_with_cached_ids(tmp_path / "store")
    backend._write_buffer.mark_created(str(_db(backend.base_path)))
    assert _cached_metric_ids(backend) == {}
    backend.close()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
def test_a_forked_child_forgets_metric_ids(tmp_path: Path) -> None:
    backend = _backend_with_cached_ids(tmp_path / "store")
    hook = backend._write_buffer._hook
    assert isinstance(hook, metric_store.MetricWriteHook)
    db_path = _db(backend.base_path)
    with backend.pool.get_connection(db_path, create=False) as conn:
        pass
    pid = os.fork()
    if pid == 0:
        os._exit(0 if hook.cached_ids(conn, str(db_path)) == {} else 1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0
    backend.close()
