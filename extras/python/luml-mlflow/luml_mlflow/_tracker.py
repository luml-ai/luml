import json
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any

from luml.experiments.tracker import ExperimentTracker

from luml_mlflow.config import get_settings


def _wrap_public_methods_with_lock(cls: type) -> type:
    parent = cls.__bases__[0]
    for name in list(vars(parent)):
        if name.startswith("_"):
            continue
        attr = getattr(parent, name)
        if not callable(attr):
            continue

        def _make_locked(method_name: str) -> Callable[..., Any]:
            def locked(self: Any, *args: Any, **kwargs: Any) -> Any:
                with self._lock:
                    return getattr(super(cls, self), method_name)(*args, **kwargs)

            locked.__name__ = method_name
            locked.__qualname__ = f"{cls.__name__}.{method_name}"
            return locked

        setattr(cls, name, _make_locked(name))
    return cls


@_wrap_public_methods_with_lock
class ThreadSafeTracker(ExperimentTracker):
    def __init__(self, connection_string: str) -> None:
        super().__init__(connection_string)
        self._lock = threading.Lock()


@contextmanager
def store_connection(tracker: ThreadSafeTracker) -> Iterator[sqlite3.Connection]:
    """Serialize plugin writes in a transaction shared across processes."""
    conn = sqlite3.connect(tracker.backend.meta_db_path, timeout=30)
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
    finally:
        conn.close()


def mutate_experiment(
    tracker: ThreadSafeTracker,
    run_id: str,
    fn: Callable[[dict[str, Any], list[str]], None],
) -> None:
    """Atomically update a run's metadata and native flag tags."""
    with store_connection(tracker) as conn:
        row = conn.execute(
            "SELECT metadata, tags FROM experiments WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Experiment {run_id!r} not found")
        metadata = json.loads(row[0]) if row[0] else {}
        tags = json.loads(row[1]) if row[1] else []
        fn(metadata, tags)
        conn.execute(
            "UPDATE experiments SET metadata = ?, tags = ? WHERE id = ?",
            (json.dumps(metadata), json.dumps(tags), run_id),
        )


@cache
def _cached_tracker(connection_string: str) -> ThreadSafeTracker:
    return ThreadSafeTracker(connection_string)


def _store_path() -> Path:
    return Path(get_settings().LUML_BACKEND_STORE_URI)


def get_tracker() -> ThreadSafeTracker:
    """Return the process-wide tracker for the configured backend store."""
    return _cached_tracker(f"sqlite://{_store_path()}")


def delete_experiment_if(
    tracker: ThreadSafeTracker,
    experiment_id: str,
    predicate: Callable[[dict[str, Any]], bool],
) -> bool:
    conn = sqlite3.connect(_store_path() / "meta.db", isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT metadata FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
            metadata = json.loads(row[0]) if row is not None and row[0] else {}
            if row is None or not predicate(metadata):
                conn.execute("ROLLBACK")
                return False
            conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    tracker.delete_experiment(experiment_id)
    return True


def reset_tracker_cache() -> None:
    _cached_tracker.cache_clear()
