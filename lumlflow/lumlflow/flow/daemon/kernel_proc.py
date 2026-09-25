"""One kernel process per flow, spawned into the workspace venv.

The daemon listens and the kernel dials in, so there is no readiness race to
poll for: by the time the process exists, the socket it was told about is
already accepting. The kernel package is path-injected from the tool install —
the venv holds no lumlflow code — and the workspace root rides along on
`PYTHONPATH` so `import helpers` works Jupyter-style.

None of this is a surface. There is no connect, select, or configure verb here
because none is offered anywhere: a flow's kernel starts when a cell has to
run, and the only kernel control a user ever sees is a restart.
"""

import asyncio
import contextlib
import json
import logging
import os
import secrets
import socket
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from luml import __version__ as DAEMON_SDK_VERSION

import lumlflow_kernel
from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.daemon import envs
from lumlflow.flow.daemon.framing import (
    STREAM_LIMIT_BYTES,
    STREAM_LIMIT_LABEL,
    discard_oversized_line,
)
from lumlflow.flow.errors import KernelError
from lumlflow.flow.scheduler.queue import RunRequest, RunResult
from lumlflow.flow.store.cas import Cas
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.flow.store.models import OutputRecord

logger = logging.getLogger(__name__)

KERNEL_DIRNAME = "kernel"
SOCKET_NAME = "kernel.sock"
TOKEN_NAME = "token"

_START_TIMEOUT_S = 60.0
_CALL_TIMEOUT_S = 30.0
_STOP_TIMEOUT_S = 5.0
_AUTH_TIMEOUT_S = 10.0
_DRAIN_TIMEOUT_S = 1.0
# macOS caps a unix socket path near 104 bytes; a deep temp directory beats it.
_UNIX_PATH_LIMIT = 100
_STDIO_TAIL_LINES = 40

KernelState = Literal["stopped", "running"]
# The process itself starting or stopping, as against a run's lifecycle. A
# surface reads the kernel's state from here after the one it was handed when
# it opened; the kernel starts lazily, so that first answer is usually
# "stopped" and stays wrong for the rest of the tab's life without this.
KERNEL_STATE_EVENT = "kernel_state"
OnEvent = Callable[[str, dict[str, Any]], None]
FailExperiment = Callable[[str], None]


@dataclass(frozen=True)
class _TrackedExperiment:
    experiment_id: str
    store: str
    sdk_version_warning: str | None = None


class _KernelProtocolError(KernelError):
    pass


class KernelProcess:
    """The scheduler's executor, on the other side of a socket."""

    def __init__(
        self,
        *,
        flow_dir: Path,
        workspace_dir: Path,
        tracker_store: Path | None = None,
        fail_experiment: FailExperiment | None = None,
        on_event: OnEvent | None = None,
    ) -> None:
        self.flow_dir = flow_dir
        self.workspace_dir = workspace_dir
        self.tracker_store = tracker_store.resolve() if tracker_store else None
        self._fail_experiment = fail_experiment
        self.handshake: dict[str, Any] | None = None
        self.interpreter: envs.Interpreter | None = None
        # The env as it stood when this process started. Within a kernel's
        # lifetime the env is whatever its imports say; the lockfile only
        # becomes law again at the next start, so this is what a later install
        # is measured against.
        self.env: dict[str, str] = {}
        self._on_event = on_event
        self._logs = Cas(store_dir(flow_dir) / "logs")
        self._kernel_dir = store_dir(flow_dir) / KERNEL_DIRNAME
        self._start_lock = asyncio.Lock()
        self._server: asyncio.AbstractServer | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._drain_task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._stdio: deque[str] = deque(maxlen=_STDIO_TAIL_LINES)
        self._token: str | None = None
        self._accepting = False
        self._next_id = 0
        self._evict_before_next_run: bool = False
        self._active_runs: set[str] = set()
        self._cancelled_runs: set[str] = set()
        self._tracked_runs: dict[str, _TrackedExperiment] = {}

    @property
    def state(self) -> KernelState:
        return "running" if self._writer is not None else "stopped"

    @property
    def stdio_tail(self) -> str:
        return "\n".join(self._stdio)

    async def ensure_started(self) -> dict[str, Any]:
        async with self._start_lock:
            if self.handshake is not None:
                return self.handshake
            # A kernel that died leaves a listening server and a corpse behind.
            await self._teardown()
            try:
                return await self._start()
            except BaseException:
                await self._teardown()
                raise

    async def restart(self) -> dict[str, Any]:
        await self.stop()
        return await self.ensure_started()

    async def stop(self) -> None:
        # The same lock a start takes: a restart must not tear down a kernel
        # another caller is in the middle of spawning.
        async with self._start_lock:
            if self._process is not None and self._process.returncode is None:
                await self._ask_shutdown()
            await self._teardown()

    async def run(self, request: RunRequest) -> RunResult:
        self._active_runs.add(request.run_id)
        self._tracked_runs.pop(request.run_id, None)
        try:
            await self.ensure_started()
            try:
                if self._evict_before_next_run:
                    self._evict_before_next_run = False
                    try:
                        await self._call("evict_workspace_modules", {})
                    except BaseException:
                        self._evict_before_next_run = True
                        raise
                if request.run_id in self._cancelled_runs:
                    return RunResult(state="cancelled")
                record = await self._call("run", _run_payload(request), timeout=None)
            except _KernelProtocolError:
                raise
            except KernelError as death:
                tracked = self._tracked_runs.pop(request.run_id, None)
                if tracked is None or self._fail_experiment is None:
                    raise KernelError(
                        f"the kernel stopped while `{request.slug}` was running: "
                        f"{death}"
                    ) from death
                close_error: Exception | None = None
                try:
                    await asyncio.to_thread(
                        self._fail_experiment, tracked.experiment_id
                    )
                except Exception as failure:
                    close_error = failure
                return self._died_result(request, death, tracked, close_error)
            tracked = self._tracked_runs.pop(request.run_id, None)
            return self._result(record, tracked)
        finally:
            self._active_runs.discard(request.run_id)
            self._cancelled_runs.discard(request.run_id)
            self._tracked_runs.pop(request.run_id, None)

    async def page(
        self, value_ref: str, kind: str, query: dict[str, Any]
    ) -> dict[str, Any]:
        """Read into a stored value — the one browse that needs a kernel.

        Previews come from the store, so cards render without a process; paging
        deserializes the value itself, which only the kind that wrote it can do.
        The kernel starts on demand here, and the surfaces say so before asking.
        """
        await self.ensure_started()
        result = await self._call(
            "page", {"value_ref": value_ref, "kind": kind, "query": query}
        )
        return dict(result or {})

    async def export_model(
        self,
        value_ref: str,
        kind: str,
        *,
        destination: Path,
        sample: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Package a stored model as the bundle LUML takes.

        Only the kernel can: the flavor that trained the model lives in the
        flow's venv, not the daemon's. No deadline — capturing a model's
        dependencies takes as long as the environment is large.
        """
        await self.ensure_started()
        result = await self._call(
            "export_model",
            {
                "value_ref": value_ref,
                "kind": kind,
                "destination": str(destination),
                "sample": sample,
            },
            timeout=None,
        )
        return dict(result or {})

    async def eval(
        self,
        branch_slice: dict[str, dict[str, str]],
        code: str,
    ) -> dict[str, Any]:
        """Run scratch code against a branch's values.

        Starts a kernel the way paging does, and writes nothing: the REPL is
        handed copies of what the branch resolved. No deadline either — an
        expression a person typed is as long as they made it.
        """
        await self.ensure_started()
        result = await self._call(
            "eval",
            {"slice": branch_slice, "code": code},
            timeout=None,
        )
        return dict(result or {})

    def cancel(self, run_id: str) -> None:
        """Fire-and-forget: the kernel answers a cancel on its reader thread."""
        if run_id in self._active_runs:
            self._cancelled_runs.add(run_id)
        self._send({"jsonrpc": "2.0", "method": "cancel", "params": {"run_id": run_id}})

    def evict_workspace_modules(self) -> None:
        """Forget workspace modules immediately before the next run."""
        self._evict_before_next_run = True

    async def env_drift(self) -> list[str]:
        """Packages this kernel imported that the workspace has moved since.

        Never invalidation: what already ran keeps the lock hash it ran under,
        and this only says the running process is behind. A distribution the
        kernel never imported is not in it — the next run picks that one up on
        its own, and a banner over it would be noise.
        """
        now = envs.packages(self.workspace_dir)
        # Either side missing is a workspace that pins nothing, not a workspace
        # that moved: calling a kernel behind an env nobody declared would be a
        # verdict against a baseline that never existed.
        if self._writer is None or not self.env or not now:
            return []
        moved = envs.drift(self.env, now)
        if not moved:
            return []
        result = await self._call("loaded_packages", {})
        loaded = {envs.normalize(str(name)) for name in result.get("loaded") or []}
        return [name for name in moved if name in loaded]

    async def _start(self) -> dict[str, Any]:
        address, token_file = await self._listen()
        self.interpreter = await envs.ensure_interpreter(self.workspace_dir)
        # After the sync, not before: the sync is what writes the lockfile this
        # process will import against.
        self.env = envs.packages(self.workspace_dir)
        self._process = await asyncio.create_subprocess_exec(
            str(self.interpreter.python),
            "-m",
            lumlflow_kernel.__name__,
            "--socket",
            address,
            "--flow-dir",
            str(self.flow_dir),
            "--workspace-dir",
            str(self.workspace_dir),
            *(("--token-file", str(token_file)) if token_file else ()),
            cwd=str(self.workspace_dir),
            env=spawn_environment(self.workspace_dir, tracker_store=self.tracker_store),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._drain_task = asyncio.create_task(self._drain_stdio(self._process))
        await self._await_connection()
        handshake = await self._call("handshake", {})
        if handshake.get("protocol") != lumlflow_kernel.PROTOCOL_VERSION:
            raise KernelError(
                f"the kernel in {self.workspace_dir} speaks a different "
                "protocol than this lumlflow. reinstall the tool"
            )
        self.handshake = handshake
        # Whoever is watching this flow learns the process exists from here.
        # Nothing journals a kernel start — it is not a fact about the store —
        # so a surface that only replayed the journal would keep reporting the
        # kernel it saw when its tab opened, however long ago that was.
        self._emit(KERNEL_STATE_EVENT, {"state": "running"})
        return handshake

    def _unix_socket_path(self) -> str | None:
        """Where the kernel would dial, when the platform has unix sockets and
        the path is short enough to bind. None means the link is loopback."""
        path = self._kernel_dir / SOCKET_NAME
        if hasattr(socket, "AF_UNIX") and len(str(path)) < _UNIX_PATH_LIMIT:
            return str(path)
        return None

    async def _listen(self) -> tuple[str, Path | None]:
        """A unix socket where the platform has them; loopback plus a token
        where it does not, or where the path is too long to bind."""
        self._kernel_dir.mkdir(parents=True, exist_ok=True)
        self._accepting = True
        unix_path = self._unix_socket_path()
        if unix_path is not None:
            Path(unix_path).unlink(missing_ok=True)
            self._server = await asyncio.start_unix_server(
                self._accept, path=unix_path, limit=STREAM_LIMIT_BYTES
            )
            return unix_path, None
        self._token = secrets.token_hex(16)
        token_file = self._kernel_dir / TOKEN_NAME
        atomic_write_bytes(token_file, self._token.encode("utf-8"))
        self._server = await asyncio.start_server(
            self._accept, "127.0.0.1", 0, limit=STREAM_LIMIT_BYTES
        )
        port = int(self._server.sockets[0].getsockname()[1])
        return f"127.0.0.1:{port}", token_file

    async def _await_connection(self) -> None:
        process = self._process
        if process is None:
            raise KernelError("the kernel was not spawned")
        connected = asyncio.ensure_future(self._connected.wait())
        exited = asyncio.ensure_future(process.wait())
        done, _ = await asyncio.wait(
            [connected, exited],
            timeout=_START_TIMEOUT_S,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in (connected, exited):
            if task not in done:
                task.cancel()
        if self._connected.is_set():
            return
        if process.returncode is not None:
            # Whatever it printed on the way out is the whole diagnosis — an
            # ImportError in the workspace venv, most often.
            if self._drain_task is not None:
                await _settled(self._drain_task, _DRAIN_TIMEOUT_S)
            raise KernelError(
                f"the kernel exited before it connected:\n{self.stdio_tail}"
            )
        raise KernelError(f"the kernel did not start within {int(_START_TIMEOUT_S)}s")

    async def _accept(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if not self._accepting or self._writer is not None:
            writer.close()
            return
        if not await self._authenticated(reader):
            writer.close()
            return
        if not self._accepting or self._writer is not None:
            # Authenticating awaits a read, so the kernel we already have — or
            # the teardown of the one we were waiting for — may have landed
            # while this connection was proving itself.
            writer.close()
            return
        self._writer = writer
        self._connected.set()
        try:
            while True:
                try:
                    line = await reader.readuntil()
                except asyncio.LimitOverrunError as overrun:
                    await discard_oversized_line(reader, overrun)
                    self._fail_pending(
                        f"a kernel message exceeded the {STREAM_LIMIT_LABEL} limit",
                        error_type=_KernelProtocolError,
                    )
                    continue
                except asyncio.IncompleteReadError as incomplete:
                    if incomplete.partial:
                        self._receive(incomplete.partial)
                    break
                self._receive(line)
        except OSError:
            pass
        finally:
            # Only the connection that is still the link may invalidate it: a
            # restart's old reader wakes up after the new kernel has connected,
            # and it is not that kernel's death it is reporting.
            if self._writer is writer:
                self._writer = None
                self.handshake = None
                self._fail_pending("the kernel link closed")
            writer.close()

    async def _authenticated(self, reader: asyncio.StreamReader) -> bool:
        """On loopback the first line proves this is the kernel we spawned and
        not another process that reached the port."""
        if self._token is None:
            return True
        try:
            # A connection that proves nothing must not hold this open forever.
            message = json.loads(
                await asyncio.wait_for(reader.readline(), _AUTH_TIMEOUT_S)
            )
        except (ValueError, TimeoutError):
            return False
        return (
            isinstance(message, dict)
            and message.get("method") == "authenticate"
            and (message.get("params") or {}).get("token") == self._token
        )

    def _receive(self, line: bytes) -> None:
        try:
            message = json.loads(line)
        except ValueError:
            return
        if not isinstance(message, dict):
            return
        method = message.get("method")
        if method is None:
            self._answer(message)
        elif "id" not in message and self._on_event is not None:
            params = message.get("params") or {}
            self._remember_experiment(str(method), params)
            self._emit(str(method), params)
        elif "id" not in message:
            self._remember_experiment(str(method), message.get("params") or {})

    def _remember_experiment(self, event: str, params: dict[str, Any]) -> None:
        if event != "experiment_started":
            return
        run_id = str(params.get("run_id") or "")
        experiment_id = str(params.get("experiment_id") or "")
        store = str(params.get("store") or "")
        if not run_id or not experiment_id or not store:
            return
        warning = params.get("sdk_version_warning")
        self._tracked_runs[run_id] = _TrackedExperiment(
            experiment_id=experiment_id,
            store=store,
            sdk_version_warning=str(warning) if warning is not None else None,
        )

    def _emit(self, event: str, params: dict[str, Any]) -> None:
        """A subscriber that throws loses its event, not the run.

        The read loop is the link: letting a listener's failure out of here
        would close the socket a ten-minute materialization is reporting on.
        """
        if self._on_event is None:
            return
        try:
            self._on_event(event, params)
        except Exception:
            logger.exception("kernel event listener failed")

    def _answer(self, message: dict[str, Any]) -> None:
        pending = self._pending.pop(_as_int(message.get("id")), None)
        if pending is None or pending.done():
            return
        error = message.get("error")
        if error is None:
            pending.set_result(message.get("result"))
            return
        pending.set_exception(
            KernelError(str(error.get("message", "the kernel refused the call")))
        )

    async def _call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: float | None = _CALL_TIMEOUT_S,
    ) -> Any:
        writer = self._writer
        if writer is None:
            raise KernelError("the kernel is not running")
        self._next_id += 1
        request_id = self._next_id
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        try:
            await writer.drain()
            # A ten-minute run is a normal run: only the calls that are supposed
            # to answer at once carry a deadline.
            if timeout is None:
                return await future
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)

    def _send(self, message: dict[str, Any]) -> None:
        writer = self._writer
        if writer is None or writer.is_closing():
            return
        writer.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")

    def _fail_pending(
        self,
        message: str,
        *,
        error_type: type[KernelError] = KernelError,
    ) -> None:
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(error_type(message))
        self._pending.clear()

    async def _drain_stdio(self, process: asyncio.subprocess.Process) -> None:
        """The kernel's own output — a run's streams are captured at fd level
        inside it, so what reaches here is how the kernel itself died."""
        stream = process.stdout
        if stream is None:
            return
        while line := await stream.readline():
            self._stdio.append(line.decode("utf-8", "replace").rstrip())

    async def _ask_shutdown(self) -> None:
        try:
            await self._call("shutdown", {}, timeout=_STOP_TIMEOUT_S)
        except (KernelError, TimeoutError):
            pass

    async def _teardown(self) -> None:
        # Stop listening before reaping, not after: a kernel that dials in
        # while its own corpse is being waited on would set the link back up
        # behind the teardown that just cleared it, leaving this reporting
        # `running` for a process about to be killed.
        self._accepting = False
        if self._server is not None:
            self._server.close()
            self._server = None
        self.handshake = None
        self._connected.clear()
        self._fail_pending("the kernel was stopped")
        was_running = self._writer is not None
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        # Only a link that was up has a stop worth announcing: a teardown of a
        # kernel that never connected would tell a surface a process died that
        # never lived.
        if was_running:
            self._emit(KERNEL_STATE_EVENT, {"state": "stopped"})
        await self._end_process()
        (self._kernel_dir / SOCKET_NAME).unlink(missing_ok=True)
        (self._kernel_dir / TOKEN_NAME).unlink(missing_ok=True)
        self._token = None

    async def _end_process(self) -> None:
        """Ask, then insist, then stop asking.

        A kernel that was told to shut down usually goes on its own; one that
        never connected, or that is holding a cell in a C call, does not, and a
        teardown that waited on it would hang the op that ordered it. The
        handle is dropped only once the process is, so a teardown cancelled
        halfway leaves the corpse to the next one rather than to nobody.
        """
        process = self._process
        if process is not None:
            if not await _exited(process, _STOP_TIMEOUT_S):
                _end(process.terminate)
                if not await _exited(process, _STOP_TIMEOUT_S):
                    _end(process.kill)
                    await process.wait()
            self._process = None
        await self._end_drain()

    async def _end_drain(self) -> None:
        """Take the kernel's last words, then stop listening for them.

        EOF on that pipe needs every holder of its write end gone, and a cell
        that spawned a subprocess may have handed one to a grandchild that
        outlives the kernel — so the tail is worth a moment and never worth
        hanging a shutdown on.
        """
        task, self._drain_task = self._drain_task, None
        if task is None:
            return
        await _settled(task, _DRAIN_TIMEOUT_S)
        task.cancel()

    def _result(
        self,
        record: dict[str, Any],
        started: _TrackedExperiment | None,
    ) -> RunResult:
        if not isinstance(record, dict) or "state" not in record:
            raise KernelError("the kernel answered a run with no result")
        experiment_id = str(record.get("experiment_id") or "") or (
            started.experiment_id if started is not None else None
        )
        experiment_store = str(record.get("store") or "") or (
            started.store if started is not None else None
        )
        warning = record.get("sdk_version_warning")
        return RunResult(
            state=record["state"],
            outputs={
                name: OutputRecord.model_validate(output)
                for name, output in (record.get("outputs") or {}).items()
            },
            identity_dependent=bool(record.get("identity_dependent")),
            external=bool(record.get("external")),
            cost_seconds=record.get("cost_seconds"),
            log_ref=self._log_ref(record),
            experiment_id=experiment_id,
            experiment_store=experiment_store,
            experiment_close_error=record.get("experiment_close_error"),
            sdk_version_warning=(
                str(warning)
                if warning is not None
                else (started.sdk_version_warning if started is not None else None)
            ),
        )

    def _died_result(
        self,
        request: RunRequest,
        death: KernelError,
        tracked: _TrackedExperiment,
        close_error: Exception | None,
    ) -> RunResult:
        message = f"the kernel stopped while `{request.slug}` was running: {death}"
        unclosed = None
        if close_error is not None:
            unclosed = (
                f"could not fail orphaned experiment `{tracked.experiment_id}` in "
                f"tracker store `{tracked.store}`: {close_error}"
            )
            message = f"{message}\n{unclosed}"
        return RunResult(
            state="failed",
            log_ref=self._logs.put(f"\nKernelError: {message}\n".encode()),
            experiment_id=tracked.experiment_id,
            experiment_store=tracked.store,
            experiment_close_error=unclosed,
            sdk_version_warning=tracked.sdk_version_warning,
        )

    def _log_ref(self, record: dict[str, Any]) -> str | None:
        """A failure's traceback belongs with the console output it interrupted.

        The kernel catches the exception rather than letting it print, so it
        never reaches the captured streams — without this the logs tab would
        show a cell's prints above a failure it could not explain.
        """
        ref = str(record.get("log_ref") or "")
        error = record.get("error")
        if not error:
            return ref or None
        captured = self._logs.get(ref) if ref and self._logs.exists(ref) else b""
        return self._logs.put(captured + _failure_text(error).encode("utf-8"))


def spawn_environment(
    workspace_dir: Path, *, tracker_store: Path | None = None
) -> dict[str, str]:
    """The kernel from the tool install, the workspace for `import helpers`.

    Path injection is what lets the venv hold no lumlflow code: the kernel is
    never installed into the environment it runs in, it is put on that
    interpreter's path from wherever this tool lives.
    """
    installed = getattr(lumlflow_kernel, "__file__", None)
    if installed is None:
        raise KernelError("this install carries no kernel package")
    existing = os.environ.get("PYTHONPATH", "")
    roots = [str(Path(installed).resolve().parent.parent), str(workspace_dir)]
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([*roots, *filter(None, [existing])]),
        "PYTHONUNBUFFERED": "1",
        "LUMLFLOW_DAEMON_SDK_VERSION": DAEMON_SDK_VERSION,
    }
    # Cells run on a worker thread; a GUI matplotlib backend (macOS, Tk) can only
    # draw on the main thread. A backend the workspace sets explicitly wins.
    environment.setdefault("MPLBACKEND", "Agg")
    if tracker_store is not None:
        store = str(tracker_store.resolve())
        environment["BACKEND_STORE_URI"] = store
        environment["LUML_BACKEND_STORE_URI"] = store
    return environment


def _run_payload(request: RunRequest) -> dict[str, Any]:
    return {
        "run_id": request.run_id,
        "version": {
            "slug": request.slug,
            "source": request.source,
            "produces": {
                name: spec.model_dump(mode="json")
                for name, spec in request.produces.items()
            },
        },
        "inputs": {
            name: {
                "value_ref": bound.value_ref,
                "kind": bound.kind,
            }
            for name, bound in request.inputs.items()
        },
        "params": request.params,
        "ctx_info": {"branch": request.branch, "step": request.step},
        "identity": {
            "flow": request.flow,
            "flow_id": request.flow_id,
            "path": request.flow_path,
            "slug": request.slug,
            "uid": request.uid,
            "lane": request.branch,
            "version_id": request.version_id,
            "run_id": request.run_id,
        },
    }


async def _settled(task: "asyncio.Task[None]", timeout: float) -> None:
    """Give a task a moment to finish, leaving it running if it will not."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout)


async def _exited(process: asyncio.subprocess.Process, timeout: float) -> bool:
    if process.returncode is not None:
        return True
    try:
        await asyncio.wait_for(process.wait(), timeout)
    except TimeoutError:
        return False
    return True


def _end(stop: Callable[[], None]) -> None:
    """A process that died between the check and the signal is already stopped."""
    with contextlib.suppress(ProcessLookupError, OSError):
        stop()


def _failure_text(error: dict[str, Any]) -> str:
    detail = error.get("traceback") or f"{error.get('type')}: {error.get('message')}"
    hint = error.get("hint")
    lines = ["", detail] + ([f"hint: {hint}"] if hint else [])
    return "\n".join(lines).rstrip() + "\n"


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) else -1
