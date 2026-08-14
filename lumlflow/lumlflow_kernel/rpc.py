"""JSON-RPC over one local socket, line-delimited.

The link is bidirectional: the daemon calls in, the kernel emits events, and
`secret_get` is a request the kernel itself makes. The reader loop owns the
socket's read side and never blocks on user code — long methods run on one
worker thread (the executor is serial by design), so `cancel` and `shutdown`
are answered while a run still holds that thread.
"""

from __future__ import annotations

import json
import queue
import socket
import threading
import traceback
from collections.abc import Callable
from typing import Any, Protocol

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

_REQUEST_TIMEOUT_S = 30.0


class RpcError(Exception):
    def __init__(
        self, message: str, *, code: int = INTERNAL_ERROR, data: Any = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.data is not None:
            body["data"] = self.data
        return body


class Handler(Protocol):
    """What `serve` dispatches to: a name → callable allowlist.

    `inline` names the methods answered on the reader thread. Everything else
    queues behind the worker, which is what keeps a ten-minute `run` from
    swallowing the `cancel` that would end it.
    """

    methods: dict[str, Callable[[dict[str, Any]], Any]]
    inline: frozenset[str]


def connect(address: str, *, token: str | None = None) -> Connection:
    """Dial the daemon's listening socket.

    `host:port` is the Windows transport (loopback TCP plus a daemon-minted
    token, sent first so the daemon can tell the kernel it spawned from anyone
    else who reached the port); anything else is a unix socket path.
    """
    host, separator, port = address.rpartition(":")
    if separator and port.isdigit():
        sock = socket.create_connection((host or "127.0.0.1", int(port)))
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(address)
    link = Connection(sock)
    if token is not None:
        link.notify("authenticate", {"token": token})
    return link


class Connection:
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._reader = sock.makefile("rb")
        self._writer = sock.makefile("wb")
        self._write_lock = threading.Lock()
        self._id_lock = threading.Lock()
        self._work: queue.Queue[tuple[dict[str, Any], Handler] | None] = queue.Queue()
        self._pending: dict[int, _Pending] = {}
        self._next_id = 0
        self._stopped = threading.Event()

    def serve(self, handler: Handler) -> None:
        worker = threading.Thread(target=self._drain_work, name="kernel-work")
        worker.start()
        try:
            for line in self._reader:
                if line.strip():
                    self._receive(line, handler)
                if self._stopped.is_set():
                    break
        except OSError:
            pass
        finally:
            self._stopped.set()
            self._work.put(None)
            worker.join(timeout=5.0)
            self._fail_pending("the kernel link closed")
            self.close()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        """An event. Notifications carry no id and are never answered."""
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: float = _REQUEST_TIMEOUT_S,
    ) -> Any:
        """Call the daemon and wait — the one direction user code triggers."""
        with self._id_lock:
            self._next_id += 1
            request_id = self._next_id
        pending = _Pending()
        self._pending[request_id] = pending
        self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        try:
            if not pending.done.wait(timeout):
                raise RpcError(f"the daemon did not answer `{method}` in time")
            if pending.error is not None:
                raise RpcError(str(pending.error.get("message", "the daemon refused")))
            return pending.result
        finally:
            self._pending.pop(request_id, None)

    def stop(self) -> None:
        """End `serve` after the in-flight message is answered."""
        self._stopped.set()

    def close(self) -> None:
        self._stopped.set()
        for stream in (self._writer, self._reader):
            try:
                stream.close()
            except OSError:
                pass
        try:
            self._sock.close()
        except OSError:
            pass

    def _receive(self, line: bytes, handler: Handler) -> None:
        try:
            message = json.loads(line)
        except ValueError:
            self._send_error(None, RpcError("unreadable message", code=PARSE_ERROR))
            return
        if not isinstance(message, dict):
            self._send_error(None, RpcError("unreadable message", code=INVALID_REQUEST))
            return
        if "method" not in message:
            self._answer_pending(message)
        elif message.get("method") in handler.inline or "id" not in message:
            self._invoke(message, handler)
        else:
            self._work.put((message, handler))

    def _drain_work(self) -> None:
        while True:
            item = self._work.get()
            if item is None:
                return
            try:
                self._invoke(*item)
            except BaseException:
                # A cancel injected into this thread can land a beat after the
                # run it aimed at already returned. Losing the worker to it
                # would leave the kernel accepting requests it never answers.
                pass

    def _invoke(self, message: dict[str, Any], handler: Handler) -> None:
        method = str(message.get("method"))
        request_id = message.get("id")
        call = handler.methods.get(method)
        if call is None:
            self._send_error(
                request_id, RpcError(f"no method `{method}`", code=METHOD_NOT_FOUND)
            )
            return
        try:
            result = call(message.get("params") or {})
        except RpcError as error:
            self._send_error(request_id, error)
        except Exception as error:
            self._send_error(
                request_id,
                RpcError(
                    str(error) or type(error).__name__, data=traceback.format_exc()
                ),
            )
        else:
            if request_id is not None:
                self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _answer_pending(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        pending = self._pending.get(request_id) if isinstance(request_id, int) else None
        if pending is None:
            return
        pending.result = message.get("result")
        pending.error = message.get("error")
        pending.done.set()

    def _fail_pending(self, message: str) -> None:
        for pending in list(self._pending.values()):
            pending.error = {"message": message}
            pending.done.set()

    def _send_error(self, request_id: Any, error: RpcError) -> None:
        # Nothing to answer: a notification carries no id, and a line that did
        # not parse carries nothing at all.
        if request_id is None:
            return
        self._send({"jsonrpc": "2.0", "id": request_id, "error": error.payload()})

    def _send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
        with self._write_lock:
            if self._writer.closed:
                return
            try:
                self._writer.write(line)
                self._writer.flush()
            except (OSError, ValueError):
                # The daemon went away mid-run. The run finishes and its facts
                # land in the store on the next connection; losing the event
                # stream is not a reason to kill user code.
                self._stopped.set()


class _Pending:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: Any = None
        self.error: dict[str, Any] | None = None
