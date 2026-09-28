"""One run: a fresh namespace, a workspace cwd, and the facts the store records.

Nothing about a run is inherited from the last one. The namespace is built from
the version's bound source every time, the cwd is the flow's containing
directory, and a per-run scratch directory exists only for `ctx.tempdir()` and
output staging. The environment, working directory, logging configuration and
open figures are put back where they were.

Failures are recorded, not raised: a cell that throws produces a `failed`
materialization with its traceback, because a broken cell is a state the store
knows how to hold, not a protocol error.
"""

from __future__ import annotations

import contextlib
import copy
import ctypes
import linecache
import logging
import os
import shutil
import sqlite3
import sys
import threading
import time
import traceback
from base64 import b64encode
from collections import OrderedDict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumlflow_kernel.capture import Capture
from lumlflow_kernel.cas import Cas, canonical_json, hash_bytes
from lumlflow_kernel.ctxobj import EXTERNAL, IDENTITY, Ctx
from lumlflow_kernel.kinds import preview as previews
from lumlflow_kernel.kinds.registry import Registry
from lumlflow_kernel.tracker import (
    Experiment,
    ExperimentRef,
    SdkTrackerClient,
    Tracker,
    TrackerError,
    daemon_sdk_version,
    open_sdk_tracker,
    sdk_version_warning,
    tracker_store,
)

SCRATCH_DIRNAME = "scratch"
NON_INTERACTIVE_HINT = "cells are non-interactive — take values via `params`"

_CACHE_ENTRIES = 8
_SAFE_ID = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

Emit = Callable[[str, dict[str, Any]], None]


class Cancelled(BaseException):
    """Injected into the running thread. Not an `Exception`, so a cell's own
    `except Exception` cannot swallow the cancel that was meant for it."""


class CellError(Exception):
    """A failure the run surfaces in words — no traceback into kernel frames."""


@dataclass(frozen=True)
class OutputSpec:
    type: str = "asset"
    kind: str | None = None
    persist: bool = True


@dataclass(frozen=True)
class Version:
    slug: str
    source: str
    produces: dict[str, OutputSpec] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Version:
        produces = payload.get("produces") or {}
        return cls(
            slug=str(payload.get("slug", "cell")),
            source=str(payload.get("source", "")),
            produces={
                name: _output_spec(spec) for name, spec in sorted(produces.items())
            },
        )


class Executor:
    def __init__(
        self,
        *,
        flow_dir: Path,
        workspace_dir: Path,
        registry: Registry,
        emit: Emit,
    ) -> None:
        self._flow_dir = flow_dir
        self._workspace_dir = workspace_dir
        self._registry = registry
        self._emit = emit
        store = flow_dir / ".lumlflow"
        self._values = Cas(store / "values")
        self._previews = Cas(store / "previews")
        self._logs = Cas(store / "logs")
        self._index_path = store / "store.sqlite"
        self._scratch_root = store / "kernel" / SCRATCH_DIRNAME
        self._cache: OrderedDict[tuple[str, str], Any] = OrderedDict()
        self._tracker_client: tuple[Path, SdkTrackerClient] | None = None
        self._lock = threading.Lock()
        self._active: _Active | None = None

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        run_id = _safe_id(str(request.get("run_id", "run")))
        version = Version.from_payload(request.get("version") or {})
        params = dict(request.get("params") or {})
        ctx_info = dict(request.get("ctx_info") or {})
        declared = dict(request.get("inputs") or {})
        observed = _Observed()
        capture = Capture(
            lambda stream, seq, data: self._emit(
                "log", _log_event(run_id, stream, seq, data)
            )
        )
        scratch = self._scratch_root / run_id
        started = time.monotonic()
        state = "succeeded"
        outputs: dict[str, dict[str, Any]] = {}
        error: dict[str, Any] | None = None
        tracker: Tracker | None = None
        experiment_client: SdkTrackerClient | None = None
        tracker_close_error: str | None = None
        tracker_sdk_warning: str | None = None
        identity = self._experiment_identity(request, version, ctx_info, run_id)
        with self._claim(run_id) as cell_returned:
            self._emit("started", {"run_id": run_id, "slug": version.slug})
            try:
                with _restored():
                    scratch.mkdir(parents=True, exist_ok=True)
                    try:
                        with capture:
                            os.chdir(self._workspace_dir)
                            if _uses_experiment(version, declared):
                                store = tracker_store()
                                experiment_client, tracker_sdk_warning = (
                                    self._experiment_tracker(
                                        store, self._warn_sdk_version
                                    )
                                )
                                if _declares_experiment(version):
                                    tracker = Tracker.start(
                                        experiment_client,
                                        name=version.slug,
                                        group=identity["flow"],
                                        tags=[identity["lane"], version.slug],
                                        store=store,
                                        params=params,
                                    )
                                    event = {
                                        "run_id": run_id,
                                        "slug": version.slug,
                                        **tracker.event_fields,
                                    }
                                    if tracker_sdk_warning is not None:
                                        event["sdk_version_warning"] = (
                                            tracker_sdk_warning
                                        )
                                    self._emit("experiment_started", event)
                                    tracker.initialize({"lumlflow": identity})
                            cell = _instantiate(version)
                            inputs = self._load_inputs(
                                version, declared, experiment_client
                            )
                            returned = cell.materialize(
                                self._ctx(
                                    version,
                                    ctx_info,
                                    params,
                                    scratch,
                                    observed,
                                    tracker,
                                ),
                                **inputs,
                            )
                            cell_returned()
                            outputs = self._store_outputs(
                                run_id, version, returned, scratch
                            )
                    finally:
                        cell_returned()
                        # A cell may have moved into its scratch directory.
                        with contextlib.suppress(OSError):
                            os.chdir(self._workspace_dir)
                        shutil.rmtree(scratch, ignore_errors=True)
            except Cancelled:
                state = "cancelled"
            except BaseException as failure:  # noqa: B036 - a failure is a record
                state = "failed"
                error = _error(failure)
            if tracker is not None:
                try:
                    if state == "succeeded":
                        tracker.complete()
                    else:
                        tracker.fail()
                except BaseException as failure:  # noqa: B036 - reported on the run
                    tracker_close_error = str(failure) or type(failure).__name__
        record: dict[str, Any] = {
            "run_id": run_id,
            "state": state,
            "outputs": outputs,
            "identity_dependent": observed.identity,
            "external": observed.external,
            "cost_seconds": round(time.monotonic() - started, 6),
            "log_ref": self._store_log(capture.artifact()),
            "log_truncated": capture.truncated,
        }
        if tracker is not None:
            record.update(tracker.event_fields)
        if tracker_close_error is not None:
            record["experiment_close_error"] = tracker_close_error
        if tracker_sdk_warning is not None:
            record["sdk_version_warning"] = tracker_sdk_warning
        if error is not None:
            record["error"] = error
        self._emit("materialized" if state == "succeeded" else "failed", record)
        return record

    def cancel(self, run_id: str) -> bool:
        """Raise `Cancelled` inside the running thread at its next bytecode.

        A cell blocked in a C call keeps running until it returns to the
        interpreter; ending that is the daemon's business, not ours. A cell
        that has already returned is past interrupting, and says so.
        """
        with self._lock:
            active = self._active
            if active is None or active.run_id != _safe_id(run_id):
                return False
            interrupted = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(active.thread_id), ctypes.py_object(Cancelled)
            )
            return interrupted == 1

    def page(self, value_ref: str, kind: str, query: dict[str, Any]) -> dict[str, Any]:
        asset_type = self._registry.get(kind)
        pager = getattr(asset_type, "page", None)
        if pager is None:
            raise CellError(f"`{kind}` values are not paged")
        return pager(self._deserialize(asset_type, kind, value_ref), query)

    def value(self, value_ref: str, kind: str) -> Any:
        """A stored value, deserialized once and kept for the next reader."""
        return self._deserialize(self._registry.get(kind), kind, value_ref)

    def fresh(self, value_ref: str, kind: str) -> Any:
        """The same value read again — never the object the cache holds."""
        return self._registry.get(kind).deserialize(self._values.path(value_ref))

    def copy_of(self, value_ref: str, kind: str) -> Any:
        """A value the caller cannot reach the cached one through.

        The hot cache is what makes reading a large frame a second time
        instant, so it is read — and never handed out. A value no copy protocol
        reaches is read again from its own bytes instead, which is a copy by
        construction.
        """
        try:
            return copy.deepcopy(self.value(value_ref, kind))
        except Exception:
            return self.fresh(value_ref, kind)

    @contextlib.contextmanager
    def _claim(self, run_id: str) -> Iterator[Callable[[], None]]:
        """Hold the kernel for one run, and hand back the end of the window a
        cancel may land in.

        A cancel is an exception injected into this thread at its next
        bytecode, so it arrives after the call that armed it. Closing the
        window the moment the cell returns is what keeps one out of the
        teardown, where it would destroy the record the daemon is waiting for
        instead of the run it was aimed at.
        """
        with self._lock:
            if self._active is not None:
                raise CellError("this kernel is already running a cell")
            self._active = _Active(run_id, threading.get_ident())

        def close_window() -> None:
            with self._lock:
                self._active = None

        try:
            yield close_window
        finally:
            close_window()

    def _ctx(
        self,
        version: Version,
        ctx_info: dict[str, Any],
        params: dict[str, Any],
        scratch: Path,
        observed: _Observed,
        tracker: Tracker | None,
    ) -> Ctx:
        return Ctx(
            branch=str(ctx_info.get("branch", "main")),
            step=int(ctx_info.get("step", 0)),
            workspace_dir=self._workspace_dir,
            flow_dir=self._flow_dir,
            params=params,
            scratch=scratch,
            observe=lambda fact, detail: self._observe(observed, version, fact, detail),
            tracker=tracker,
        )

    def _experiment_tracker(
        self, store: Path, warn: Callable[[str], None]
    ) -> tuple[SdkTrackerClient, str | None]:
        daemon_version = daemon_sdk_version()
        if self._tracker_client is None or self._tracker_client[0] != store:
            client = open_sdk_tracker(store, daemon_version=daemon_version, warn=warn)
            self._tracker_client = (store, client)
        else:
            client = self._tracker_client[1]
            warning = sdk_version_warning(client.sdk_version, daemon_version)
            if warning is not None:
                warn(warning)
        return client, sdk_version_warning(client.sdk_version, daemon_version)

    @staticmethod
    def _warn_sdk_version(message: str) -> None:
        print(f"warning: {message}", file=sys.stderr, flush=True)

    def _experiment_identity(
        self,
        request: dict[str, Any],
        version: Version,
        ctx_info: dict[str, Any],
        run_id: str,
    ) -> dict[str, str]:
        supplied = dict(request.get("identity") or {})
        path = Path(str(supplied.get("path") or self._flow_dir)).expanduser().resolve()
        flow = str(supplied.get("flow") or _flow_name(path))
        return {
            "flow": flow,
            "flow_id": str(supplied.get("flow_id") or ""),
            "path": str(path),
            "slug": version.slug,
            "uid": str(supplied.get("uid") or ""),
            "lane": str(supplied.get("lane") or ctx_info.get("branch") or "main"),
            "version_id": str(supplied.get("version_id") or ""),
            "run_id": run_id,
        }

    def _observe(
        self, observed: _Observed, version: Version, fact: str, detail: str
    ) -> None:
        if fact == IDENTITY:
            observed.identity = True
            self._emit("identity_access", {"slug": version.slug, "detail": detail})
        elif fact == EXTERNAL:
            observed.external = True
            self._emit("external_access", {"slug": version.slug, "detail": detail})

    def _load_inputs(
        self,
        version: Version,
        inputs: dict[str, Any],
        experiment_client: SdkTrackerClient | None,
    ) -> dict[str, Any]:
        loaded = {}
        for name, spec in inputs.items():
            value_ref = str((spec or {}).get("value_ref") or "")
            kind = str((spec or {}).get("kind") or "")
            if not value_ref or not self._values.exists(value_ref):
                raise CellError(
                    f"`{version.slug}` needs `{name}`, whose value is not stored — "
                    "run the cell that produces it"
                )
            value = self._deserialize(self._registry.get(kind), kind, value_ref)
            if kind == "experiment":
                if experiment_client is None or not isinstance(value, ExperimentRef):
                    raise CellError("stored experiment reference is invalid")
                value = Experiment(experiment_client, value)
            loaded[name] = value
        return loaded

    def _deserialize(self, asset_type: Any, kind: str, value_ref: str) -> Any:
        key = (value_ref, kind)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        value = asset_type.deserialize(self._values.path(value_ref))
        self._cache[key] = value
        # Bounded by entries, not by bytes: a host-side value has no size the
        # kernel can ask for without walking it.
        while len(self._cache) > _CACHE_ENTRIES:
            self._cache.popitem(last=False)
        return value

    def _store_outputs(
        self, run_id: str, version: Version, returned: Any, scratch: Path
    ) -> dict[str, dict[str, Any]]:
        values = _returned_values(version, returned)
        stored = {}
        for name, spec in version.produces.items():
            stored[name] = self._store_output(run_id, name, spec, values[name], scratch)
        return stored

    def _store_output(
        self,
        run_id: str,
        name: str,
        spec: OutputSpec,
        value: Any,
        scratch: Path,
    ) -> dict[str, Any]:
        if spec.type == "experiment" and not isinstance(value, ExperimentRef):
            raise CellError(
                f"`{name}` is declared as an `experiment`; "
                "return `ctx.tracker.record` for it"
            )
        resolution = self._registry.resolve(value, spec.kind)
        asset_type = resolution.asset_type
        self._emit(
            "kind_inferred",
            {
                "run_id": run_id,
                "output": name,
                "kind": resolution.kind,
                "kind_source": resolution.source,
            },
        )
        preview_ref = self._previews.put(
            canonical_json(
                previews.envelope(resolution.kind, asset_type.preview(value))
            )
        )
        self._emit(
            "preview",
            {
                "run_id": run_id,
                "output": name,
                "kind": resolution.kind,
                "preview_ref": preview_ref,
            },
        )
        record: dict[str, Any] = {
            "kind": resolution.kind,
            "kind_source": resolution.source,
            "preview_ref": preview_ref,
            "persisted": spec.persist,
        }
        if resolution.kind == "file":
            record["filename"] = Path(value).name
        if not spec.persist:
            # Declared unpersisted: a token unique to this materialization
            # stands in for the content hash, so no consumer ever memo-hits
            # across a rematerialization it cannot read the bytes of.
            record["content_hash"] = hash_bytes(f"{run_id}/{name}".encode())
            record["value_ref"] = None
            record["size"] = 0
            return record
        value_ref, size = self._persist(run_id, asset_type.serialize(value), scratch)
        custom = getattr(asset_type, "content_hash", None)
        record["content_hash"] = custom(value) if custom else value_ref
        record["value_ref"] = value_ref
        record["size"] = size
        return record

    def _persist(
        self, run_id: str, serialized: bytes | Path, scratch: Path
    ) -> tuple[str, int]:
        def pin(digest: str) -> None:
            self._pin_value(run_id, digest)

        if not isinstance(serialized, Path):
            return self._values.put(serialized, before_stage=pin), len(serialized)
        size = serialized.stat().st_size
        moved = self._values.put_file(
            serialized,
            move=_under(serialized, scratch),
            before_stage=pin,
        )
        return moved, size

    def _pin_value(self, run_id: str, digest: str) -> None:
        # A standalone kernel has no flow-store sweeper to race.
        if not self._index_path.is_file():
            return
        connection = sqlite3.connect(self._index_path, timeout=30.0)
        try:
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO value_pins (run_id, digest) VALUES (?, ?)",
                    (run_id, digest),
                )
        finally:
            connection.close()

    def _store_log(self, artifact: bytes) -> str | None:
        return self._logs.put(artifact) if artifact else None


@dataclass
class _Active:
    run_id: str
    thread_id: int


@dataclass
class _Observed:
    identity: bool = False
    external: bool = False


@contextlib.contextmanager
def _restored() -> Iterator[None]:
    """Put back what a run is allowed to change but not to keep."""
    environ = dict(os.environ)
    cwd = Path.cwd()
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(environ)
        with contextlib.suppress(OSError):
            os.chdir(cwd)
        root.handlers[:] = handlers
        root.setLevel(level)
        pyplot = sys.modules.get("matplotlib.pyplot")
        if pyplot is not None:
            pyplot.close("all")


def _instantiate(version: Version) -> Any:
    """Build the cell from its bound source in a namespace of its own.

    The source is registered with `linecache` under a name that says what it is,
    so a traceback shows the failing line without claiming a file offset the
    author's file does not have — the bound source drops comments and blank
    lines, so its line numbers are its own.
    """
    filename = f"<cell {version.slug}>"
    linecache.cache[filename] = (
        len(version.source),
        None,
        version.source.splitlines(keepends=True),
        filename,
    )
    namespace: dict[str, Any] = {"__name__": "lumlflow_cell", "__file__": filename}
    exec(compile(version.source, filename, "exec"), namespace)
    classes = [
        value
        for value in namespace.values()
        if isinstance(value, type)
        and getattr(value, "__module__", "") == "lumlflow_cell"
    ]
    if len(classes) != 1:
        raise CellError(f"`{version.slug}` does not hold exactly one cell class")
    cell = classes[0]()
    if not callable(getattr(cell, "materialize", None)):
        raise CellError(f"`{version.slug}` has no `materialize` yet")
    return cell


def _returned_values(version: Version, returned: Any) -> dict[str, Any]:
    declared = set(version.produces)
    if not declared:
        return {}
    if not isinstance(returned, dict):
        raise CellError(
            f"`{version.slug}` must return a dict of its outputs — "
            f"{_names(sorted(declared))}"
        )
    missing = declared - set(returned)
    if missing:
        raise CellError(
            f"`{version.slug}` did not return {_names(sorted(missing))}, "
            "which it declares in `produces`"
        )
    extra = set(returned) - declared
    if extra:
        raise CellError(
            f"`{version.slug}` returned {_names(sorted(extra))}, "
            "which it does not declare in `produces`"
        )
    return returned


def _output_spec(spec: Any) -> OutputSpec:
    if not isinstance(spec, dict):
        return OutputSpec(type=str(spec or "asset"))
    kind = spec.get("kind")
    return OutputSpec(
        type=str(spec.get("type", "asset")),
        kind=str(kind) if isinstance(kind, str) else None,
        persist=bool(spec.get("persist", True)),
    )


def _declares_experiment(version: Version) -> bool:
    return any(spec.type == "experiment" for spec in version.produces.values())


def _uses_experiment(version: Version, inputs: dict[str, Any]) -> bool:
    return _declares_experiment(version) or any(
        str((spec or {}).get("kind") or "") == "experiment" for spec in inputs.values()
    )


def _flow_name(path: Path) -> str:
    return path.name.removesuffix(".flow")


def _error(failure: BaseException) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": type(failure).__name__,
        "message": str(failure) or type(failure).__name__,
    }
    if not isinstance(failure, CellError | TrackerError):
        # Drop this module's own frame: the traceback the author reads should
        # start at their code.
        tb = failure.__traceback__
        body["traceback"] = "".join(
            traceback.format_exception(type(failure), failure, tb.tb_next if tb else tb)
        )
    if isinstance(failure, EOFError):
        body["hint"] = NON_INTERACTIVE_HINT
    return body


def _log_event(run_id: str, stream: str, seq: int, data: bytes) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "stream": stream,
        "seq": seq,
        "bytes": b64encode(data).decode("ascii"),
    }


def _under(path: Path, root: Path) -> bool:
    """Only a file the run made under scratch may be moved rather than copied."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def _names(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def _safe_id(run_id: str) -> str:
    cleaned = "".join(char for char in run_id if char in _SAFE_ID)
    return cleaned or "run"
