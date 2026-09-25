"""Discover, start, and call the one per-user daemon."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import Any

from lumlflow.flow import errors
from lumlflow.flow.daemon import harnesses, workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowError, ServerError

START_TIMEOUT_S = 30.0
STOP_TIMEOUT_S = 30.0
_CONNECT_TIMEOUT_S = 5.0
_PING_TIMEOUT_S = 0.5
_POLL_S = 0.05
_START_ATTEMPTS = 2
_STEP_ASIDE_GRACE_S = 3.0
_HELD_RETRY_S = 3.0
_LOG_TAIL_CHARS = 2000


class DaemonClient:
    """`timeout` of None waits as long as the call takes — a ten-minute run is
    a normal run, and only liveness checks have a deadline worth having."""

    def __init__(
        self,
        record: DaemonRecord,
        *,
        timeout: float | None = None,
        started: bool = False,
    ) -> None:
        self.record = record
        self.started = started
        try:
            self._sock = socket.create_connection(
                ("127.0.0.1", record.port), timeout=timeout or _CONNECT_TIMEOUT_S
            )
        except OSError as unreachable:
            raise ServerError(
                "nothing is answering for the lumlflow daemon"
            ) from unreachable
        self._sock.settimeout(timeout)
        self._reader = self._sock.makefile("rb")
        self._next_id = 0
        self._send(
            {
                "jsonrpc": "2.0",
                "method": "authenticate",
                "params": {"token": record.token},
            }
        )

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        request_id = self._next_id
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        try:
            line = self._reader.readline()
        except OSError as dropped:
            raise ServerError(f"lumlflow dropped `{method}`") from dropped
        if not line:
            raise ServerError(f"lumlflow closed the connection during `{method}`")
        try:
            message = json.loads(line)
        except ValueError as unreadable:
            raise ServerError(
                f"lumlflow answered `{method}` unreadably"
            ) from unreadable
        error = message.get("error")
        if error is not None:
            raise _raised(error)
        return message.get("result")

    def close(self) -> None:
        for stream in (self._reader, self._sock):
            try:
                stream.close()
            except OSError:
                pass

    def __enter__(self) -> "DaemonClient":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()

    def _send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
        try:
            self._sock.sendall(line)
        except OSError as dropped:
            raise ServerError("the connection to lumlflow dropped") from dropped


def attach(
    record: DaemonRecord, *, timeout: float | None = None, started: bool = False
) -> DaemonClient:
    return DaemonClient(record, timeout=timeout, started=started)


def is_alive(record: DaemonRecord) -> bool:
    """The record's exact daemon answers; a reused pid or port is not enough."""
    try:
        with attach(record, timeout=_PING_TIMEOUT_S) as live:
            answer = live.call("ping")
            return (
                isinstance(answer, dict)
                and answer.get("instance_id") == record.instance_id
            )
    except (ServerError, OSError, ValueError):
        return False


def discover(*, timeout: float = _HELD_RETRY_S) -> DaemonRecord | None:
    """Return the answering daemon, clean a stale row, or name a hung holder."""
    deadline = time.monotonic() + timeout
    while True:
        record = workspace.read_record()
        if record is not None and is_alive(record):
            return record
        if not workspace.lock_held():
            if record is not None:
                workspace.clear_record(instance_id=record.instance_id)
            return None
        if time.monotonic() >= deadline:
            raise ServerError(
                "the lumlflow daemon holds its lock but is not answering. "
                f"see {workspace.log_path()} or run `lumlflow daemon stop`"
            )
        time.sleep(_POLL_S)


def connect(directory: Path | None = None, *, start: bool = True) -> DaemonClient:
    """Attach to the daemon, starting it in the caller's directory if absent."""
    record = discover()
    if record is not None:
        return attach(record)
    if not start:
        raise ServerError("the lumlflow daemon is not running")
    record, started = _start_daemon((directory or Path.cwd()).resolve())
    return attach(record, started=started)


def stop(record: DaemonRecord, *, timeout: float = STOP_TIMEOUT_S) -> bool:
    """Signal the recorded pid only while the singleton lock proves it is live."""
    if not workspace.lock_held():
        workspace.clear_record(instance_id=record.instance_id)
        return False
    current = workspace.read_record()
    if current is None or current.instance_id != record.instance_id:
        return False
    try:
        os.kill(record.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = workspace.read_record()
        if current is not None and current.instance_id != record.instance_id:
            return True
        if not workspace.lock_held():
            if current is not None and current.instance_id == record.instance_id:
                workspace.clear_record(instance_id=record.instance_id)
            return True
        time.sleep(_POLL_S)
    return False


def wait_stopped(record: DaemonRecord, *, timeout: float = STOP_TIMEOUT_S) -> bool:
    """Wait for a daemon that already accepted a graceful shutdown request."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = workspace.read_record()
        if current is not None and current.instance_id != record.instance_id:
            return True
        if not workspace.lock_held():
            if current is not None and current.instance_id == record.instance_id:
                workspace.clear_record(instance_id=record.instance_id)
            return True
        time.sleep(_POLL_S)
    return False


def start_daemon(directory: Path, *, timeout: float = START_TIMEOUT_S) -> DaemonRecord:
    return _start_daemon(directory, timeout=timeout)[0]


def _start_daemon(
    directory: Path, *, timeout: float = START_TIMEOUT_S
) -> tuple[DaemonRecord, bool]:
    """Spawn a background server and wait for the singleton that wins the lock.

    Not necessarily the one spawned here: two verbs firing at once each start a
    daemon, and the one that loses the workspace steps aside within
    milliseconds. What the caller needs is a daemon to talk to, so a spawn that
    exits without registering is given a moment for the winner to appear, and
    then tried once more — the loser may have stepped aside for a daemon that
    was itself shutting down.

    It outlives this process — a verb starts it, a later verb reuses it — so it
    is detached from the caller's session, and its output goes to a log in the
    state directory rather than into the caller's terminal.
    """
    directory = directory.resolve()
    log = workspace.log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    for _ in range(_START_ATTEMPTS):
        process = _spawn(directory, log)
        record = _await_registration(process, deadline)
        if record is not None:
            return record, record.pid == process.pid
        if time.monotonic() >= deadline:
            break
    if workspace.lock_held():
        raise ServerError(
            "the lumlflow daemon holds its lock but is not answering. "
            f"see {log} or run `lumlflow daemon stop`"
        )
    raise ServerError(f"lumlflow could not start:\n{_tail(log)}")


def _spawn(directory: Path, log: Path) -> "subprocess.Popen[bytes]":
    inherited_executable = os.environ.get(harnesses.DAEMON_EXECUTABLE_ENV)
    environment = dict(os.environ)
    environment[harnesses.DAEMON_EXECUTABLE_ENV] = inherited_executable or str(
        Path(sys.argv[0]).resolve()
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [sys.executable, "-m", "lumlflow.flow.daemon"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(directory),
        env=environment,
        **_detached(),
    )


def _await_registration(
    process: "subprocess.Popen[bytes]", deadline: float
) -> DaemonRecord | None:
    """The daemon once one answers, or None when a loser leaves no winner."""
    exited_at: float | None = None
    while time.monotonic() < deadline:
        record = workspace.read_record()
        if record is not None and is_alive(record):
            return record
        if process.poll() is not None:
            exited_at = exited_at or time.monotonic()
            if (
                not workspace.lock_held()
                and time.monotonic() - exited_at >= _STEP_ASIDE_GRACE_S
            ):
                return None
        time.sleep(_POLL_S)
    return None


def _detached() -> dict[str, Any]:
    if sys.platform == "win32":
        creation = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        return {"creationflags": creation}
    return {"start_new_session": True}


def _raised(error: dict[str, Any]) -> FlowError:
    """Rebuild the failure the server named, so verbs catch what they expect."""
    kind = (error.get("data") or {}).get("kind")
    message = str(error.get("message", "lumlflow refused the call"))
    raised = getattr(errors, str(kind), None) if kind else None
    if isinstance(raised, type) and issubclass(raised, FlowError):
        try:
            return raised(message)
        except TypeError:
            # A failure that carries structure — the adopt conflict menu — does
            # not rebuild from a sentence. Its wording still crosses.
            return FlowError(message)
    return FlowError(message)


def _tail(log: Path) -> str:
    try:
        return log.read_text("utf-8", errors="replace")[-_LOG_TAIL_CHARS:].strip()
    except OSError:
        return ""
