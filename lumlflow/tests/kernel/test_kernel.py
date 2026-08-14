"""The method surface the daemon calls, and one run over a real socket.

Pinned here is what the daemon reads off a fresh kernel — the handshake it
records inference facts from, module eviction after a workspace edit, paging a
stored value, `ctx.secret` travelling back up the link, and shutdown — plus one
end-to-end pass where a spawned `python -m lumlflow_kernel` runs a cell and
reports it in events.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import platform
import socket
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lumlflow_kernel import PROTOCOL_VERSION
from lumlflow_kernel.executor import CellError
from tests.kernel.helpers import FakeLink, make_kernel, run, stored_value

_TIMEOUT_S = 10.0
_REPO_ROOT = Path(__file__).resolve().parents[2]

_WORKSPACE_KIND = '''
    """A workspace kind, found by the registry's parse-then-import scan."""


    class TokenKind:
        kind = "token"
        priority = 5
        python_types = ("project.Token",)

        def matches(self, value):
            return False

        def serialize(self, value):
            return b""

        def deserialize(self, source):
            return None

        def preview(self, value):
            return []


    LUMLFLOW_KINDS = [TokenKind]
'''


@pytest.fixture
def import_state(tmp_path: Path) -> Iterator[None]:
    """Undo what importing a workspace does to this interpreter.

    Both the registry scan and the eviction test put a temporary directory on
    `sys.path` and import out of it; leaving either behind would make the suite
    order-dependent.
    """
    saved = list(sys.path)
    try:
        yield
    finally:
        sys.path[:] = saved
        for name, module in list(sys.modules.items()):
            filename = getattr(module, "__file__", None)
            if isinstance(filename, str) and Path(filename).is_relative_to(tmp_path):
                del sys.modules[name]


def test_the_handshake_reports_the_protocol_the_interpreter_and_the_verbs(
    tmp_path: Path,
) -> None:
    kernel, _ = make_kernel(tmp_path)

    reported = kernel.handshake({})

    assert reported["protocol"] == PROTOCOL_VERSION
    assert reported["python"] == platform.python_version()
    assert reported["implementation"] == platform.python_implementation()
    assert reported["pid"] == os.getpid()
    assert reported["capabilities"] == [
        "cancel",
        "eval",
        "evict_workspace_modules",
        "handshake",
        "loaded_packages",
        "page",
        "run",
        "shutdown",
    ]
    assert reported["flow_dir"] == str(kernel.flow_dir)
    assert reported["workspace_dir"] == str(kernel.workspace_dir)


def test_the_handshake_reports_the_flows_kinds_with_priority_and_provenance(
    tmp_path: Path, import_state: None
) -> None:
    kernel, _ = make_kernel(tmp_path, files={"project_kinds.py": _WORKSPACE_KIND})

    kinds = {entry["kind"]: entry for entry in kernel.handshake({})["kinds"]}

    assert kinds["frame"] == {
        "kind": "frame",
        "priority": 40,
        "provenance": "builtin",
        "python_types": ["pandas.DataFrame", "polars.DataFrame"],
    }
    assert kinds["token"]["provenance"] == "`project_kinds.py`"
    # Priority is the order the daemon has to record inference under: the
    # workspace's own kind outranks the builtins, and pickle claims last.
    priorities = [entry["priority"] for entry in kernel.handshake({})["kinds"]]
    assert priorities == sorted(priorities)
    assert priorities[0] == kinds["token"]["priority"]
    assert priorities[-1] == kinds["pickle"]["priority"]


def test_evicting_workspace_modules_forgets_the_workspace_and_nothing_else(
    tmp_path: Path, import_state: None
) -> None:
    kernel, _ = make_kernel(
        tmp_path,
        files={
            "helpers_mod.py": "VALUE = 1\n",
            ".venv/lib/site-packages/installed_mod.py": "VALUE = 2\n",
        },
    )
    sys.path.insert(0, str(kernel.workspace_dir))
    sys.path.insert(0, str(kernel.workspace_dir / ".venv" / "lib" / "site-packages"))
    importlib.invalidate_caches()
    importlib.import_module("helpers_mod")
    importlib.import_module("installed_mod")

    evicted = kernel.evict_workspace_modules({})["evicted"]

    assert "helpers_mod" in evicted
    assert "helpers_mod" not in sys.modules
    # The workspace's venv lives inside the workspace; its packages are not the
    # user's code and re-importing them on every edit would be pure cost.
    assert "installed_mod" not in evicted
    assert "installed_mod" in sys.modules
    assert "lumlflow_kernel.kernel" in sys.modules
    assert "json" in sys.modules


def test_an_evicted_workspace_module_is_imported_again_on_the_next_run(
    tmp_path: Path, import_state: None
) -> None:
    kernel, _ = make_kernel(tmp_path, files={"helpers_mod.py": "GREETING = 'old'\n"})
    sys.path.insert(0, str(kernel.workspace_dir))
    importlib.invalidate_caches()
    body = """
        def materialize(self, ctx):
            import helpers_mod

            return {"note": helpers_mod.GREETING}
    """
    first = run(kernel, body, produces={"note": {"kind": "note"}})
    _edit_in_place(kernel.workspace_dir / "helpers_mod.py", "GREETING = 'new'\n")

    kernel.evict_workspace_modules({})
    second = run(kernel, body, run_id="run2", produces={"note": {"kind": "note"}})

    assert stored_value(kernel, first, "note") == b"old"
    assert stored_value(kernel, second, "note") == b"new"


def test_paging_a_stored_frame_returns_the_window_and_the_true_total(
    tmp_path: Path,
) -> None:
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            import pandas

            return {"rows": pandas.DataFrame({"n": list(range(50))})}
        """,
        produces={"rows": {"kind": "frame"}},
    )

    page = kernel.page(
        {
            "value_ref": record["outputs"]["rows"]["value_ref"],
            "kind": "frame",
            "query": {"offset": 10, "limit": 5},
        }
    )

    assert page["columns"] == ["n"]
    assert page["rows"] == [[10], [11], [12], [13], [14]]
    assert page["offset"] == 10
    assert page["total_rows"] == 50


def test_paging_a_kind_that_has_no_pager_is_refused(tmp_path: Path) -> None:
    kernel, _ = make_kernel(tmp_path)
    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"note": "nothing to page"}
        """,
        produces={"note": {"kind": "note"}},
    )

    with pytest.raises(CellError, match="`note` values are not paged"):
        kernel.page(
            {
                "value_ref": record["outputs"]["note"]["value_ref"],
                "kind": "note",
                "query": {},
            }
        )


def test_a_cell_asking_for_a_secret_gets_it_from_the_daemon(tmp_path: Path) -> None:
    kernel, link = make_kernel(
        tmp_path, link=FakeLink(secrets={"API_KEY": "sk-live-1"})
    )

    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"note": "matched" if ctx.secret("API_KEY") == "sk-live-1" else "no"}
        """,
        produces={"note": {"kind": "note"}},
    )

    assert link.requests == [("secret_get", {"name": "API_KEY"})]
    assert record["state"] == "succeeded"
    assert stored_value(kernel, record, "note") == b"matched"


def test_a_secret_the_daemon_does_not_hold_is_a_recorded_failure(
    tmp_path: Path,
) -> None:
    kernel, _ = make_kernel(tmp_path)

    record = run(
        kernel,
        """
        def materialize(self, ctx):
            return {"note": ctx.secret("API_KEY")}
        """,
        produces={"note": {"kind": "note"}},
    )

    assert record["state"] == "failed"
    assert "API_KEY" in record["error"]["message"]


def test_shutdown_stops_the_link_and_marks_the_kernel_stopped(tmp_path: Path) -> None:
    kernel, link = make_kernel(tmp_path)

    assert kernel.shutdown({}) == {"ok": True}
    assert kernel.stopped.is_set()
    assert link.stopped


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="unix sockets only")
def test_a_spawned_kernel_handshakes_runs_a_cell_and_shuts_down(
    tmp_path: Path,
) -> None:
    address = tmp_path / "kernel.sock"
    flow_dir = tmp_path / "project" / "churn.flow"
    (flow_dir / "cells").mkdir(parents=True)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.settimeout(_TIMEOUT_S)
    listener.bind(str(address))
    listener.listen(1)
    kernel = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lumlflow_kernel",
            "--socket",
            str(address),
            "--flow-dir",
            str(flow_dir),
        ],
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )
    daemon: _Daemon | None = None
    try:
        accepted, _ = listener.accept()
        daemon = _Daemon(accepted)

        greeting = daemon.call(1, "handshake", {})
        record = daemon.call(2, "run", _run_request())

        assert greeting["protocol"] == PROTOCOL_VERSION
        assert greeting["pid"] == kernel.pid
        assert "run" in greeting["capabilities"]
        assert record["state"] == "succeeded"
        assert record["outputs"]["note"]["kind"] == "note"
        assert daemon.named("started") == [{"run_id": "run1", "slug": "greet"}]
        assert _logged(daemon) == "hello from the cell\n"
        assert [event["run_id"] for event in daemon.named("materialized")] == ["run1"]

        assert daemon.call(3, "shutdown", {}) == {"ok": True}
        assert kernel.wait(timeout=_TIMEOUT_S) == 0
    finally:
        if kernel.poll() is None:
            kernel.kill()
            kernel.wait(timeout=_TIMEOUT_S)
        if daemon is not None:
            daemon.close()
        listener.close()


class _Daemon:
    """The daemon side of a real socket, speaking the protocol by hand."""

    def __init__(self, sock: socket.socket) -> None:
        sock.settimeout(_TIMEOUT_S)
        self._sock = sock
        self._reader = sock.makefile("rb")
        self._writer = sock.makefile("wb")
        self.events: list[tuple[str, dict[str, Any]]] = []

    def call(self, request_id: int, method: str, params: dict[str, Any]) -> Any:
        """Send one request and return its result, keeping the events that
        arrive on the way — a run reports itself before it answers."""
        self._writer.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            ).encode("utf-8")
            + b"\n"
        )
        self._writer.flush()
        while True:
            line = self._reader.readline()
            assert line, f"the kernel closed the link without answering `{method}`"
            message = json.loads(line)
            if message.get("id") == request_id:
                assert "error" not in message, message["error"]
                return message["result"]
            self.events.append((message["method"], message.get("params") or {}))

    def named(self, event: str) -> list[dict[str, Any]]:
        return [params for name, params in self.events if name == event]

    def close(self) -> None:
        for stream in (self._writer, self._reader):
            with contextlib.suppress(OSError):
                stream.close()
        self._sock.close()


def _edit_in_place(path: Path, source: str) -> None:
    """Rewrite a module the way an agent does: same byte length, same second.

    Those two are the whole of a `.pyc` header's staleness check, and holding
    the mtime fixed is what keeps the test from passing by luck when the write
    lands in the next second.
    """
    before = path.stat()
    path.write_text(source, encoding="utf-8")
    os.utime(path, (before.st_atime, before.st_mtime))


def _run_request() -> dict[str, Any]:
    source = textwrap.dedent(
        """
        class Greet:
            def materialize(self, ctx):
                print("hello from the cell")
                return {"note": "greetings"}
        """
    ).strip()
    return {
        "run_id": "run1",
        "version": {
            "slug": "greet",
            "source": source,
            "produces": {"note": {"kind": "note"}},
        },
        "inputs": {},
        "params": {},
        "ctx_info": {"branch": "main", "step": 1},
    }


def _logged(daemon: _Daemon) -> str:
    from base64 import b64decode

    chunks = sorted(daemon.named("log"), key=lambda event: event["seq"])
    return b"".join(b64decode(chunk["bytes"]) for chunk in chunks).decode("utf-8")
