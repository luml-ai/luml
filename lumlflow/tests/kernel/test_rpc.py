"""The kernel's end of the link: framing, dispatch, and the inline lane.

Pinned here is the transport contract the daemon is written against — one JSON
line per message, an answer for every `id`, events with no `id`, a
kernel-initiated request for `secret_get`, and a reader thread that keeps
answering while the worker holds a run.
"""

from __future__ import annotations

import contextlib
import json
import socket
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from lumlflow_kernel.rpc import METHOD_NOT_FOUND, Connection, RpcError, connect

_TIMEOUT_S = 5.0


class _Handler:
    def __init__(
        self,
        methods: dict[str, Callable[[dict[str, Any]], Any]],
        *,
        inline: frozenset[str] = frozenset(),
    ) -> None:
        self.methods = methods
        self.inline = inline


class _Daemon:
    """The other end of the socket, driven by hand."""

    def __init__(self, sock: socket.socket) -> None:
        # Every read is bounded: a kernel that never answers fails the test
        # instead of hanging the suite.
        sock.settimeout(_TIMEOUT_S)
        self._sock = sock
        self._reader = sock.makefile("rb")
        self._writer = sock.makefile("wb")

    def send(self, message: dict[str, Any]) -> None:
        self.send_raw(json.dumps(message).encode("utf-8") + b"\n")

    def send_raw(self, line: bytes) -> None:
        self._writer.write(line)
        self._writer.flush()

    def call(
        self, request_id: int, method: str, params: dict[str, Any] | None = None
    ) -> None:
        self.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )

    def read(self) -> dict[str, Any]:
        line = self._reader.readline()
        assert line, "the kernel closed the link without answering"
        message: dict[str, Any] = json.loads(line)
        return message

    def close(self) -> None:
        for stream in (self._writer, self._reader):
            with contextlib.suppress(OSError):
                stream.close()
        self._sock.close()


class _Wire:
    def __init__(self) -> None:
        kernel_sock, daemon_sock = socket.socketpair()
        self.connection = Connection(kernel_sock)
        self.daemon = _Daemon(daemon_sock)
        self.served: threading.Thread | None = None

    def serve(self, handler: _Handler) -> None:
        self.served = threading.Thread(
            target=self.connection.serve, args=(handler,), name="serve-under-test"
        )
        self.served.start()

    def close(self) -> None:
        self.daemon.close()
        self.connection.close()
        if self.served is not None:
            self.served.join(timeout=_TIMEOUT_S)


@pytest.fixture
def wire() -> Iterator[_Wire]:
    link = _Wire()
    try:
        yield link
    finally:
        link.close()


def test_a_request_is_answered_with_its_own_id_and_the_result(wire: _Wire) -> None:
    wire.serve(_Handler({"echo": lambda params: {"seen": params}}))

    wire.daemon.call(7, "echo", {"run_id": "r1"})

    assert wire.daemon.read() == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {"seen": {"run_id": "r1"}},
    }


def test_a_notification_is_dispatched_and_never_answered(wire: _Wire) -> None:
    seen: list[dict[str, Any]] = []
    wire.serve(
        _Handler(
            {"progress": lambda params: seen.append(params), "echo": lambda p: p},
        )
    )

    wire.daemon.send({"jsonrpc": "2.0", "method": "progress", "params": {"pct": 10}})
    wire.daemon.call(3, "echo")

    # The first line back is the later request's answer, so the notification —
    # which was dispatched, and ran first — was answered with nothing.
    assert wire.daemon.read()["id"] == 3
    assert seen == [{"pct": 10}]


def test_notify_puts_an_event_on_the_wire_with_no_id(wire: _Wire) -> None:
    wire.connection.notify("log", {"run_id": "r1", "stream": "stdout", "seq": 1})

    assert wire.daemon.read() == {
        "jsonrpc": "2.0",
        "method": "log",
        "params": {"run_id": "r1", "stream": "stdout", "seq": 1},
    }


def test_a_kernel_initiated_request_returns_what_the_daemon_answers(
    wire: _Wire,
) -> None:
    wire.serve(_Handler({}))

    with ThreadPoolExecutor(max_workers=1) as pool:
        asked = pool.submit(wire.connection.request, "secret_get", {"name": "API_KEY"})
        message = wire.daemon.read()
        wire.daemon.send(
            {"jsonrpc": "2.0", "id": message["id"], "result": {"value": "sk-live-1"}}
        )

        assert asked.result(timeout=_TIMEOUT_S) == {"value": "sk-live-1"}

    assert message["method"] == "secret_get"
    assert message["params"] == {"name": "API_KEY"}


def test_a_daemon_error_reply_raises(wire: _Wire) -> None:
    wire.serve(_Handler({}))

    with ThreadPoolExecutor(max_workers=1) as pool:
        asked = pool.submit(wire.connection.request, "secret_get", {"name": "NOPE"})
        message = wire.daemon.read()
        wire.daemon.send(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {"code": -32603, "message": "no secret named `NOPE`"},
            }
        )

        with pytest.raises(RpcError, match="no secret named"):
            asked.result(timeout=_TIMEOUT_S)


def test_a_request_nobody_answers_gives_up(wire: _Wire) -> None:
    with pytest.raises(RpcError, match="did not answer `secret_get` in time"):
        wire.connection.request("secret_get", {"name": "API_KEY"}, timeout=0.05)


def test_a_pending_request_fails_when_the_link_closes(wire: _Wire) -> None:
    wire.serve(_Handler({}))

    with ThreadPoolExecutor(max_workers=1) as pool:
        asked = pool.submit(wire.connection.request, "secret_get", {"name": "API_KEY"})
        wire.daemon.read()
        wire.daemon.close()

        with pytest.raises(RpcError, match="the kernel link closed"):
            asked.result(timeout=_TIMEOUT_S)


def test_an_unknown_method_is_answered_with_method_not_found(wire: _Wire) -> None:
    wire.serve(_Handler({"run": lambda params: {}}))

    wire.daemon.call(1, "eval")

    answer = wire.daemon.read()
    assert answer["id"] == 1
    assert answer["error"]["code"] == METHOD_NOT_FOUND
    assert "eval" in answer["error"]["message"]


def test_a_handler_that_raises_is_answered_and_serve_keeps_going(wire: _Wire) -> None:
    def boom(params: dict[str, Any]) -> None:
        raise ValueError("the handler blew up")

    wire.serve(_Handler({"boom": boom, "echo": lambda params: params}))

    wire.daemon.call(1, "boom")
    answer = wire.daemon.read()
    wire.daemon.call(2, "echo", {"still": "here"})

    assert answer["error"]["message"] == "the handler blew up"
    assert "ValueError" in answer["error"]["data"]
    assert wire.daemon.read() == {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"still": "here"},
    }


def test_a_malformed_line_does_not_kill_serve(wire: _Wire) -> None:
    wire.serve(_Handler({"echo": lambda params: params}))

    wire.daemon.send_raw(b"{not json at all\n")
    wire.daemon.call(4, "echo", {"ok": True})

    assert wire.daemon.read() == {"jsonrpc": "2.0", "id": 4, "result": {"ok": True}}


def test_an_inline_method_is_answered_while_the_worker_holds_a_slow_run(
    wire: _Wire,
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow(params: dict[str, Any]) -> dict[str, Any]:
        entered.set()
        release.wait(_TIMEOUT_S)
        return {"state": "cancelled"}

    wire.serve(
        _Handler(
            {"run": slow, "cancel": lambda params: {"cancelled": True}},
            inline=frozenset({"cancel"}),
        )
    )

    wire.daemon.call(1, "run", {"run_id": "r1"})
    assert entered.wait(_TIMEOUT_S)
    wire.daemon.call(2, "cancel", {"run_id": "r1"})
    try:
        answered = wire.daemon.read()
    finally:
        release.set()

    assert answered == {"jsonrpc": "2.0", "id": 2, "result": {"cancelled": True}}
    assert wire.daemon.read() == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"state": "cancelled"},
    }


def test_stop_ends_serve_once_the_in_flight_message_is_answered(wire: _Wire) -> None:
    def shutdown(params: dict[str, Any]) -> dict[str, Any]:
        wire.connection.stop()
        return {"ok": True}

    wire.serve(_Handler({"shutdown": shutdown}, inline=frozenset({"shutdown"})))

    wire.daemon.call(1, "shutdown")

    assert wire.daemon.read() == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    assert wire.served is not None
    wire.served.join(timeout=_TIMEOUT_S)
    assert not wire.served.is_alive()


def test_closing_the_socket_from_the_daemon_side_ends_serve(wire: _Wire) -> None:
    wire.serve(_Handler({"echo": lambda params: params}))

    wire.daemon.close()

    assert wire.served is not None
    wire.served.join(timeout=_TIMEOUT_S)
    assert not wire.served.is_alive()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="unix sockets only")
def test_connect_greets_the_daemon_with_the_token_it_was_given(tmp_path: Path) -> None:
    address = tmp_path / "kernel.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.settimeout(_TIMEOUT_S)
    listener.bind(str(address))
    listener.listen(1)
    try:
        link = connect(str(address), token="minted-by-the-daemon")
        accepted, _ = listener.accept()
        daemon = _Daemon(accepted)
        try:
            assert daemon.read() == {
                "jsonrpc": "2.0",
                "method": "authenticate",
                "params": {"token": "minted-by-the-daemon"},
            }
        finally:
            daemon.close()
            link.close()
    finally:
        listener.close()
