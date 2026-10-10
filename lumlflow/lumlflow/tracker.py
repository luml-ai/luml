import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self

from luml.experiments.tracker import ExperimentTracker

logger = logging.getLogger(__name__)

ExperimentDeleted = Callable[[str], None]
StorePath = Callable[[], str | Path]

# Each attempt already includes sqlite3's default five-second busy wait.
TRACKER_READ_RETRIES = 1


def _wrap_public_methods_with_lock(cls: type) -> type:
    parent = cls.__bases__[0]
    for name in list(vars(parent)):
        if name.startswith("_"):
            continue
        attr = getattr(parent, name)
        if not callable(attr):
            continue

        def _make_locked(method_name: str):  # noqa: ANN202
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
    def __init__(self, connection_string: str = "sqlite://./experiments") -> None:
        super().__init__(connection_string)
        self._lock = threading.Lock()


class TrackerProvider:
    def __init__(self, store_path: StorePath) -> None:
        self._store_path = store_path
        self._default: ExperimentTracker | None = None
        self._bound: ExperimentTracker | None = None
        self._deleted_listeners: set[ExperimentDeleted] = set()
        self._lock = threading.RLock()

    @property
    def store_path(self) -> Path:
        with self._lock:
            tracker = self._bound or self._default
        if tracker is not None:
            return Path(tracker.backend.base_path).resolve()
        return Path(self._store_path()).expanduser().resolve()

    @property
    def tracker(self) -> ExperimentTracker:
        with self._lock:
            if self._bound is not None:
                return self._bound
            if self._default is None:
                self._default = ThreadSafeTracker(f"sqlite://{self.store_path}")
            return self._default

    @contextmanager
    def bind(self, tracker: ExperimentTracker) -> Iterator[Self]:
        if tracker is self:
            raise ValueError("a tracker provider cannot be bound to itself")
        with self._lock:
            previous = self._bound
            self._bound = tracker
        try:
            yield self
        finally:
            with self._lock:
                self._bound = previous

    def on_experiment_deleted(self, listener: ExperimentDeleted) -> Callable[[], None]:
        with self._lock:
            self._deleted_listeners.add(listener)

        def unsubscribe() -> None:
            with self._lock:
                self._deleted_listeners.discard(listener)

        return unsubscribe

    def delete_experiment(self, experiment_id: str) -> None:
        self.tracker.delete_experiment(experiment_id)
        with self._lock:
            listeners = tuple(self._deleted_listeners)
        for listener in listeners:
            try:
                listener(experiment_id)
            except Exception:
                logger.exception("experiment-deleted listener failed")

    def read_experiment(self, experiment_id: str) -> Any | None:
        for attempt in range(TRACKER_READ_RETRIES + 1):
            try:
                return self.tracker.get_experiment_record(experiment_id)
            except Exception as failure:
                if _is_sqlite_locked(failure) and attempt < TRACKER_READ_RETRIES:
                    continue
                raise
        raise AssertionError("tracker retry loop did not return")

    def __getattr__(self, name: str) -> Any:
        return getattr(self.tracker, name)


def _is_sqlite_locked(failure: BaseException) -> bool:
    pending = [failure]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if (
            isinstance(current, sqlite3.OperationalError)
            and "locked" in str(current).casefold()
        ):
            return True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return False
