"""The method surface the daemon calls, and the process-wide state it owns.

Kernel plumbing is invisible by design: there is no connect, select, or
configure verb here because none is offered anywhere. The daemon spawns this,
handshakes, and runs cells; the only kernel control a user ever sees is a
restart.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import importlib.util
import os
import platform
import sys
import threading
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from lumlflow_kernel import PROTOCOL_VERSION, repl
from lumlflow_kernel.executor import Executor
from lumlflow_kernel.kinds import registry

_VENV_MARKERS = ("site-packages", "dist-packages")


class Link(Protocol):
    """The daemon side of the socket, as the kernel uses it."""

    def notify(self, method: str, params: dict[str, Any]) -> None: ...

    def request(self, method: str, params: dict[str, Any]) -> Any: ...

    def stop(self) -> None: ...


class Kernel:
    def __init__(self, *, flow_dir: Path, workspace_dir: Path, link: Link) -> None:
        self.flow_dir = flow_dir
        self.workspace_dir = workspace_dir
        self._link = link
        _enable_copy_on_write()
        self.registry = registry.build(workspace_dir)
        self.executor = Executor(
            flow_dir=flow_dir,
            workspace_dir=workspace_dir,
            registry=self.registry,
            emit=link.notify,
            ask_secret=self._secret,
        )
        self.methods: dict[str, Callable[[dict[str, Any]], Any]] = {
            "handshake": self.handshake,
            "run": self.run,
            "cancel": self.cancel,
            "eval": self.eval,
            "page": self.page,
            "evict_workspace_modules": self.evict_workspace_modules,
            "loaded_packages": self.loaded_packages,
            "shutdown": self.shutdown,
        }
        # Answered on the reader thread: each has to reach a kernel whose worker
        # is busy holding a ten-minute run. Asking what this kernel imported is
        # one of them — an install landing mid-run is exactly when a surface
        # needs to say the kernel is behind.
        self.inline = frozenset({"cancel", "shutdown", "loaded_packages"})
        self.stopped = threading.Event()

    def handshake(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_VERSION,
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "pid": os.getpid(),
            "flow_dir": str(self.flow_dir),
            "workspace_dir": str(self.workspace_dir),
            "capabilities": sorted(self.methods),
            "kinds": self.registry.report(),
        }

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.executor.run(params)

    def cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"cancelled": self.executor.cancel(str(params.get("run_id", "")))}

    def eval(self, params: dict[str, Any]) -> dict[str, Any]:
        """Scratch code against a branch's values. Writes no asset.

        Queued behind a run like every other worker method: the console capture
        is process-wide, so an expression never runs beside a materialization.
        """
        return repl.evaluate(
            self.executor,
            refs=dict(params.get("slice") or {}),
            code=str(params.get("code", "")),
            paranoid=bool(params.get("paranoid")),
        )

    def page(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.executor.page(
            str(params.get("value_ref", "")),
            str(params.get("kind", "")),
            dict(params.get("query") or {}),
        )

    def evict_workspace_modules(self, params: dict[str, Any]) -> dict[str, Any]:
        """Forget the workspace's modules so the next run imports them again.

        Skipping this would poison the cache the other way round: the store
        would key a materialization on the new tree hash while the kernel still
        held the old module.
        """
        evicted = []
        for name, module in list(sys.modules.items()):
            path = _module_path(module)
            if path is not None and self._is_workspace_code(path):
                del sys.modules[name]
                _drop_bytecode(path)
                evicted.append(name)
        importlib.invalidate_caches()
        return {"evicted": sorted(evicted)}

    def loaded_packages(self, params: dict[str, Any]) -> dict[str, Any]:
        """The distributions this kernel has already imported.

        A module in `sys.modules` is the one the next cell gets, whatever the
        lockfile now says — so this is the set an install can strand, and the
        only set a restart is worth raising over. Everything else the next run
        imports fresh.
        """
        imported = {name.partition(".")[0] for name in list(sys.modules)}
        distributions = importlib.metadata.packages_distributions()
        return {
            "loaded": sorted(
                {name for module in imported for name in distributions.get(module, ())}
            )
        }

    def shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        self.stopped.set()
        self._link.stop()
        return {"ok": True}

    def _secret(self, name: str) -> str:
        value = self._link.request("secret_get", {"name": name})
        if isinstance(value, dict):
            value = value.get("value")
        if not isinstance(value, str):
            raise KeyError(f"no secret named `{name}` is set for this workspace")
        return value

    def _is_workspace_code(self, path: Path) -> bool:
        if any(marker in path.parts for marker in _VENV_MARKERS):
            return False
        try:
            return path.is_relative_to(self.workspace_dir.resolve())
        except OSError:
            return False


def _drop_bytecode(source: Path) -> None:
    """Forget the compiled copy too, or the eviction buys nothing.

    CPython trusts a `.pyc` whose header still matches the source's mtime in
    whole seconds and its byte length. An agent rewriting `helpers.py` in place
    matches both, so dropping the module alone would import the old code back.
    """
    with contextlib.suppress(OSError, ValueError):
        Path(importlib.util.cache_from_source(str(source))).unlink(missing_ok=True)


def _module_path(module: Any) -> Path | None:
    filename = getattr(module, "__file__", None)
    if not isinstance(filename, str):
        return None
    try:
        return Path(filename).resolve()
    except OSError:
        return None


def _enable_copy_on_write() -> None:
    """Ask pandas for copy-on-write before anything imports it.

    Cells share input values by reference — that is the point of the hot cache —
    so a consumer that modifies a frame in place would otherwise change what the
    next consumer sees. This closes the cheap half of that hazard; paranoid mode
    catches the rest.
    """
    os.environ.setdefault("PANDAS_COPY_ON_WRITE", "1")
    pandas = sys.modules.get("pandas")
    if pandas is None:
        # The environment variable is what pandas reads at import, so a kernel
        # that has not loaded it yet is already covered.
        return
    with contextlib.suppress(Exception), warnings.catch_warnings():
        # Deprecated from pandas 3.0, where copy-on-write is the only mode and
        # setting it is a no-op worth no warning of ours.
        warnings.simplefilter("ignore")
        pandas.options.mode.copy_on_write = True
