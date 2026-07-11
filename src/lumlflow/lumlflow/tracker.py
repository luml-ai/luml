import threading
from typing import Any

from luml.experiments.tracker import ExperimentTracker


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
