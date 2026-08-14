"""Finding, starting, and calling the server that owns a workspace.

Every verb goes through here: resolve the workspace root, read the record, and
call. Starting is not a gesture the product offers — there is no connect verb
anywhere — so a verb that finds nobody home starts one in the background and
carries on.

The transport is line-delimited JSON-RPC over loopback, the token from the
record proving the caller is not just some process that reached the port.
"""

import contextlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import Any

from lumlflow.flow import errors
from lumlflow.flow.daemon import workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowError, ServerError

START_TIMEOUT_S = 30.0
STOP_TIMEOUT_S = 30.0
_CONNECT_TIMEOUT_S = 5.0
_PING_TIMEOUT_S = 2.0
_POLL_S = 0.05
_START_ATTEMPTS = 2
_STEP_ASIDE_GRACE_S = 3.0
_LOG_TAIL_CHARS = 2000


class DaemonClient:
    """`timeout` of None waits as long as the call takes — a ten-minute run is
    a normal run, and only liveness checks have a deadline worth having."""

    def __init__(self, record: DaemonRecord, *, timeout: float | None = None) -> None:
        self.record = record
        try:
            self._sock = socket.create_connection(
                ("127.0.0.1", record.port), timeout=timeout or _CONNECT_TIMEOUT_S
            )
        except OSError as unreachable:
            raise ServerError(
                f"nothing is answering for {record.workspace}"
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


def attach(record: DaemonRecord, *, timeout: float | None = None) -> DaemonClient:
    return DaemonClient(record, timeout=timeout)


def is_alive(record: DaemonRecord) -> bool:
    """Does the recorded process still answer? A pid is not an answer."""
    try:
        with attach(record, timeout=_PING_TIMEOUT_S) as live:
            return bool(live.call("ping"))
    except (ServerError, OSError, ValueError):
        return False


def live_record(root: Path) -> DaemonRecord | None:
    """Whoever is serving this workspace right now, if anybody is."""
    record = workspace.read_record(root.resolve())
    return record if record is not None and is_alive(record) else None


def connect(root: Path, *, start: bool = True) -> DaemonClient:
    """The server for this workspace, started in the background if none answers."""
    root = root.resolve()
    record = live_record(root)
    if record is not None:
        return attach(record)
    if not start:
        raise ServerError(f"nothing is serving {root}")
    return attach(start_daemon(root))


def stop(record: DaemonRecord, *, timeout: float = STOP_TIMEOUT_S) -> bool:
    """Ask a server to let go of its workspace, and wait until it has.

    The record is surrendered last, after the kernels and stores are closed, so
    its disappearance — not the answer to the call — is what says the workspace
    is free for a successor.
    """
    with contextlib.suppress(FlowError, OSError):
        with attach(record, timeout=_PING_TIMEOUT_S) as live:
            live.call("shutdown")
    root = Path(record.workspace)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = workspace.read_record(root)
        if current is None or current.pid != record.pid:
            return True
        time.sleep(_POLL_S)
    return False


def stand_down(record: DaemonRecord) -> bool:
    """Give up the workspace so a foreground server can take it — if that is free.

    Background plumbing with nothing in flight is replaceable and says so. A
    server a person is watching in a terminal, or one carrying a run, is not:
    a port is never worth someone else's session or half a training job.
    """
    if record.foreground or not _idle(record):
        return False
    return stop(record)


def _idle(record: DaemonRecord) -> bool:
    try:
        with attach(record, timeout=_PING_TIMEOUT_S) as live:
            return not live.call("ping").get("running")
    except (FlowError, OSError, ValueError):
        return False


def start_daemon(root: Path, *, timeout: float = START_TIMEOUT_S) -> DaemonRecord:
    """Spawn a background server and wait for one registered for this workspace.

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
    log = workspace.log_path(root)
    log.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    for _ in range(_START_ATTEMPTS):
        record = _await_registration(root, _spawn(root, log), deadline)
        if record is not None:
            return record
        if time.monotonic() >= deadline:
            raise ServerError(f"lumlflow did not start within {int(timeout)}s")
    raise ServerError(f"lumlflow could not start:\n{_tail(log)}")


def _spawn(root: Path, log: Path) -> "subprocess.Popen[bytes]":
    with log.open("ab") as output:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "lumlflow.flow.daemon",
                "--workspace",
                str(root),
            ],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            cwd=str(root),
            **_detached(),
        )


def _await_registration(
    root: Path, process: "subprocess.Popen[bytes]", deadline: float
) -> DaemonRecord | None:
    """The workspace's daemon once one answers, or None to try again."""
    while time.monotonic() < deadline:
        record = workspace.read_record(root)
        if record is not None and is_alive(record):
            return record
        if process.poll() is not None:
            # It stepped aside, or it never got going: either way the daemon
            # that owns the workspace has a moment to register before we retry.
            deadline = min(deadline, time.monotonic() + _STEP_ASIDE_GRACE_S)
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
