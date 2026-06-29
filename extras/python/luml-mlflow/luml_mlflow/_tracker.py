import threading
from collections.abc import Callable
from functools import cache
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


@cache
def _cached_tracker(connection_string: str) -> ThreadSafeTracker:
    return ThreadSafeTracker(connection_string)


def get_tracker() -> ThreadSafeTracker:
    """Return the process-wide tracker for the configured backend store."""
    settings = get_settings()
    return _cached_tracker(f"sqlite://{settings.LUML_BACKEND_STORE_URI}")


def reset_tracker_cache() -> None:
    _cached_tracker.cache_clear()
