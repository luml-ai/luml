"""Ending the servers a test started, however the test ended.

Every one of them owns a workspace lock, a kernel or two and a port until
something tells it not to, so a suite that leaves one behind leaves it behind
for as long as the machine is up.
"""

import contextlib
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import client
from lumlflow.flow.daemon.workspace import RECORDS_DIRNAME, DaemonRecord

# Windows has no SIGKILL; there, terminating is already the hard kind.
_HARD_KILL = getattr(signal, "SIGKILL", signal.SIGTERM)
_GRACE_S = 10.0


def stop_recorded(state_dir: Path) -> None:
    """Stop whoever is registered for a workspace under this state directory.

    Reads the discovery record rather than tracking handles, so it reaches the
    servers a verb started three layers down inside a CLI subprocess.
    """
    for path in sorted((state_dir / RECORDS_DIRNAME).glob("*.json")):
        record = _read(path)
        if record is not None:
            _end(record)


def reap(child: "subprocess.Popen[Any]") -> None:
    """Make sure a server a test started by hand is not still running."""
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=_GRACE_S)
        except subprocess.TimeoutExpired:
            child.kill()
    child.wait()
    # A test that never read the pipes it asked for still has them open.
    for stream in (child.stdin, child.stdout, child.stderr):
        if stream is not None:
            stream.close()


def _read(path: Path) -> DaemonRecord | None:
    try:
        return DaemonRecord(**json.loads(path.read_bytes()))
    except (OSError, ValueError, TypeError):
        return None


def _end(record: DaemonRecord) -> None:
    """Asked to stop first — a killed server leaves its kernels behind.

    The pid is only signalled when the process answered a moment ago, so a
    record left over from a run whose pid the machine has since handed to
    somebody else costs nothing.
    """
    if not client.is_alive(record):
        return
    if client.stop(record, timeout=_GRACE_S):
        return
    with contextlib.suppress(OSError, ProcessLookupError):
        os.kill(record.pid, _HARD_KILL)
