"""The workspace daemon: one process, one workspace, every flow beneath it.

A per-flow daemon cannot own what is workspace-scoped without racing itself —
the watched tree, the generated docs, the env, the web port are all singletons
per workspace — so one process hosts N flows, each with its own store, journal
and kernel.

Singleton-ness is enforced where it is observable: the discovery record is
created exclusively, and a daemon that finds the record already taken asks
whoever holds it to answer before deciding it is stale.
"""

import argparse
import asyncio
import contextlib
import json
import secrets
import signal
import socket
import sys
import time
import traceback
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import uvicorn

from lumlflow.flow.daemon import client, web, workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.daemon.uploads import LumlUploader
from lumlflow.flow.daemon.watcher import Watcher
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowError

# What a caller is told once the workspace is being served, and from where.
Announce = Callable[[DaemonRecord], None]
# The agent sessions one connection is carrying, as (flow, actor).
Leases = set[tuple[str | None, str]]

_AUTH_TIMEOUT_S = 10.0
_BACKLOG = 64
_LOCK_POLL_S = 0.05
# How long the browser endpoint is given to close its connections politely.
_WEB_GRACE_S = 3.0
# How long a foreground start waits out the predecessor it just asked to stop:
# the record is surrendered a moment before the lock behind it is.
_HANDOVER_S = 10.0

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
FLOW_ERROR = -32000


class Daemon:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        # Everything a browser watches goes through here, and a session that is
        # opened before it would announce its commits to nobody.
        self.streams = Streams()
        # The one place the network is reached from: uploads are daemon-side,
        # so a no-network kernel never strands a published output, and a hub
        # built anywhere else publishes nothing until someone hands it this.
        self.hub = Hub(self.root, uploader=LumlUploader(), streams=self.streams)
        self.api = Api(self.hub, stop=self.stop)
        self.watcher = Watcher(self.hub)
        self.token = secrets.token_hex(16)
        self.port = 0
        self.web_port = 0
        self._lock = workspace.WorkspaceLock(self.root)
        self._server: asyncio.AbstractServer | None = None
        self._web: uvicorn.Server | None = None
        self._web_task: asyncio.Task[None] | None = None
        self._record: DaemonRecord | None = None
        self._calls: set[asyncio.Task[None]] = set()
        self._clients: set[asyncio.StreamWriter] = set()
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def serve(
        self,
        *,
        port: int = 0,
        web_port: int = 0,
        web_listener: socket.socket | None = None,
        foreground: bool = False,
        announce: Announce | None = None,
        lock_timeout: float = 0.0,
    ) -> int:
        """Own the workspace until something stops this process.

        `web_listener` is a port the caller already bound — how `lumlflow ui`
        turns "that port is taken" into a sentence before any of this starts,
        rather than into a quiet move to another port.
        """
        # The signals before the lock: a Ctrl-C during startup is an answer,
        # not a traceback over a workspace half taken.
        _install_signals(self.stop)
        # The lock before anything else: whoever holds it owns the stores, and
        # nothing this process does afterwards may touch them without it.
        if not await self._acquire(lock_timeout):
            print(
                f"another lumlflow server holds {self.root}",
                file=sys.stderr,
                flush=True,
            )
            return 1
        self._server = await asyncio.start_server(self._session, "127.0.0.1", port)
        self.port = int(self._server.sockets[0].getsockname()[1])
        # Bound before the record is written, because the record is where a
        # browser reads the port from.
        listener = web_listener if web_listener is not None else _bind_web(web_port)
        self.web_port = _port_of(listener)
        record = workspace.new_record(
            self.root,
            port=self.port,
            token=self.token,
            web_port=self.web_port,
            foreground=foreground,
        )
        if not await self._register(record):
            self._server.close()
            if listener is not None:
                listener.close()
            self._lock.release()
            return 1
        self._record = record
        if listener is not None:
            self._serve_web(listener)
        # Watching is a latency optimization the daemon can live without: a
        # platform that refuses to notify still reconciles on every verb. The
        # trees themselves are scheduled per flow as sessions open, so this only
        # fails where the observer itself cannot be started at all.
        try:
            self.watcher.start()
        except OSError as unwatchable:
            print(f"not watching {self.root}: {unwatchable}", file=sys.stderr)
        (announce or self._announce)(record)
        try:
            await self._stopped.wait()
        finally:
            await self._close()
        return 0

    async def _acquire(self, timeout: float) -> bool:
        """The workspace lock, waited out for `timeout` before giving up.

        A predecessor asked to stop clears its record a moment before it lets
        go of the lock behind it, so a successor that only read the record can
        arrive while the workspace is still, briefly, owned.
        """
        deadline = time.monotonic() + timeout
        while True:
            if self._lock.acquire():
                return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(_LOCK_POLL_S)

    def _announce(self, record: DaemonRecord) -> None:
        """The log line a background process leaves for whoever reads its log."""
        print(f"lumlflow on 127.0.0.1:{self.port} for {self.root}", flush=True)
        if self.web_port:
            print(f"workbench on {self.api.web}", flush=True)

    async def _register(self, record: DaemonRecord) -> bool:
        """Register as the daemon to call. The lock already says we may write.

        A record we do not recognise is answered before it is replaced: on a
        platform whose locks did not hold, a live daemon is still a live daemon
        and this one steps aside.
        """
        holder = workspace.claim_record(record)
        if holder is None:
            return True
        if await asyncio.to_thread(client.is_alive, holder):
            print(
                f"a lumlflow server already owns {self.root} (pid {holder.pid})",
                file=sys.stderr,
                flush=True,
            )
            return False
        # The record outlived its process — a crash, or a machine that rebooted.
        workspace.write_record(record)
        return True

    def _serve_web(self, listener: socket.socket) -> None:
        """Put the browser's surface on the port that was just bound.

        The app is built here rather than in `__init__` because it carries the
        token, and the token is what makes this port the workspace's rather
        than anything else's on the machine.
        """
        self.api.web = f"http://127.0.0.1:{self.web_port}"
        self._web = _WebServer(
            uvicorn.Config(
                web.build_app(self.hub, self.api, self.streams, token=self.token),
                # The daemon's own log is the workspace's log; uvicorn
                # reconfiguring logging for the process would take it over.
                log_config=None,
                access_log=False,
            )
        )
        self._web_task = asyncio.create_task(self._web.serve(sockets=[listener]))

    async def _close(self) -> None:
        # The socket goes first, then the calls it is still carrying: a request
        # still awaiting a kernel has to unwind before the stores it would
        # write to are closed under it, and nothing new may arrive behind it.
        await self._stop_web()
        await self._stop_serving()
        await self._end_calls()
        await self.watcher.stop()
        await self.hub.close()
        if self._record is not None:
            workspace.clear_record(self.root, pid=self._record.pid)
        self._lock.release()

    async def _stop_web(self) -> None:
        """Let go of the browsers before the stores they are reading close.

        Asked first, forced after. A tab left open overnight is the normal
        case, and a client that will not take the close frame is no reason a
        workspace cannot be let go of — but forcing cancels the shutdown
        mid-flight, and the traceback for that lands in the user's terminal
        now that this runs in the foreground. The grace is what buys the
        polite path whenever it is available, which is nearly always.
        """
        task, self._web_task = self._web_task, None
        if self._web is not None:
            self._web.should_exit = True
        if task is not None:
            _, waiting = await asyncio.wait({task}, timeout=_WEB_GRACE_S)
            if waiting and self._web is not None:
                self._web.force_exit = True
            with contextlib.suppress(Exception):
                await task
        self._web = None

    async def _stop_serving(self) -> None:
        """Refuse new callers, and let go of the ones already attached.

        `wait_closed` waits out the connections too, and nothing else ever
        closes them — an idle client would hold the daemon open forever, and
        hold it *past* the point where the record was cleared: a process still
        owning the workspace lock while advertising that nobody owns it. The
        callers are dropped rather than answered because a call cancelled
        mid-flight has no answer to give; the closed connection is what tells
        them so instead of leaving them reading.
        """
        if self._server is None:
            return
        self._server.close()
        for writer in list(self._clients):
            # Whatever is already in the transport buffer — the shutdown
            # caller's own answer — is flushed on the way out.
            writer.close()
        with contextlib.suppress(Exception):
            await self._server.wait_closed()

    async def _session(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if not await self._authenticated(reader):
            writer.close()
            return
        mine: set[asyncio.Task[None]] = set()
        leased: Leases = set()
        self._clients.add(writer)
        try:
            while line := await reader.readline():
                call = asyncio.create_task(self._handle(line, writer, leased))
                mine.add(call)
                self._calls.add(call)
                call.add_done_callback(mine.discard)
                call.add_done_callback(self._calls.discard)
        except OSError:
            pass
        finally:
            # The caller is gone; a run already in flight belongs to the queue
            # and finishes on its own.
            for call in mine:
                call.cancel()
            self._clients.discard(writer)
            writer.close()
            await self._release(leased)

    async def _release(self, leased: "Leases") -> None:
        """End the agent sessions this connection was carrying.

        The connection is the session for a client that connected to be paired,
        so one that was killed rather than closed must leave no flow registered
        to nobody — and, where it had taken the files, none held by nobody.

        A daemon on its way out is the other case entirely: the client is still
        there and will register again with whoever serves the workspace next,
        and committing here would race the stores closing underneath it.
        """
        if self._stopped.is_set():
            return
        for flow, actor in sorted(leased, key=lambda lease: (lease[0] or "", lease[1])):
            with contextlib.suppress(FlowError, OSError):
                await self.api.agent_end({"flow": flow, "actor": actor})
        leased.clear()

    async def _end_calls(self) -> None:
        calls = [call for call in self._calls if not call.done()]
        for call in calls:
            call.cancel()
        await asyncio.gather(*calls, return_exceptions=True)

    async def _authenticated(self, reader: asyncio.StreamReader) -> bool:
        """The token is what separates this workspace's clients from anything
        else that reached a loopback port."""
        try:
            # A connection that proves nothing must not hold a slot forever.
            message = json.loads(
                await asyncio.wait_for(reader.readline(), _AUTH_TIMEOUT_S)
            )
        except (ValueError, TimeoutError):
            return False
        return (
            isinstance(message, dict)
            and message.get("method") == "authenticate"
            and (message.get("params") or {}).get("token") == self.token
        )

    async def _handle(
        self, line: bytes, writer: asyncio.StreamWriter, leased: "Leases"
    ) -> None:
        try:
            message = json.loads(line)
        except ValueError:
            _reply(writer, None, error=_error(PARSE_ERROR, "unreadable message"))
            return
        if not isinstance(message, dict) or "method" not in message:
            _reply(writer, None, error=_error(INVALID_REQUEST, "unreadable message"))
            return
        request_id = message.get("id")
        method = self.api.methods.get(str(message.get("method")))
        if method is None:
            _reply(
                writer,
                request_id,
                error=_error(METHOD_NOT_FOUND, f"no method `{message.get('method')}`"),
            )
            return
        try:
            result = await method(message.get("params") or {})
        except FlowError as failure:
            _reply(
                writer,
                request_id,
                error=_error(
                    FLOW_ERROR, str(failure), data={"kind": type(failure).__name__}
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception as failure:
            traceback.print_exc()
            _reply(writer, request_id, error=_error(INTERNAL_ERROR, str(failure)))
        else:
            _reply(writer, request_id, result=result)
            _leased(leased, str(message["method"]), message.get("params") or {}, result)
        # The caller may already be gone — an answer nobody is there for is not
        # a daemon-level failure.
        with contextlib.suppress(OSError):
            await writer.drain()


class _WebServer(uvicorn.Server):
    """uvicorn claims SIGINT and SIGTERM inside `serve`.

    The daemon already owns them, and a handler installed over the loop's would
    leave one process with two opinions about what a Ctrl-C means — uvicorn
    would stop the web endpoint while the stores, kernels and the discovery
    record went on as if nothing had been asked of them.
    """

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def serve_here(root: Path, *, web_port: int, announce: Announce) -> int:
    """Serve this workspace in *this* process, until a signal stops it.

    What `lumlflow ui` is: the port is bound first, so one somebody else holds
    is a sentence the caller can act on rather than a silent move elsewhere,
    and the whole workspace — kernels, locks, the discovery record — belongs to
    a process the user can see and end with Ctrl-C.
    """
    listener = _bind_exactly(web_port)
    try:
        return asyncio.run(
            Daemon(root).serve(
                web_listener=listener,
                foreground=True,
                announce=announce,
                lock_timeout=_HANDOVER_S,
            )
        )
    finally:
        listener.close()


def _bind_exactly(port: int) -> socket.socket:
    """The port asked for, or a refusal naming it. Never a different one."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", port))
        listener.listen(_BACKLOG)
    except OSError as taken:
        listener.close()
        raise FlowError(
            f"port {port} is already in use. serve on another with `--port`"
        ) from taken
    return listener


def _bind_web(port: int) -> socket.socket | None:
    """Loopback, on the port asked for or on whichever one is free.

    A port somebody else holds is not a reason to refuse to be a daemon: every
    verb in the workspace goes through this process, and they all work without
    a browser. The port that answers is the one the record names, so nothing
    downstream has to guess which of the two it got.
    """
    for wanted in (port, 0) if port else (0,):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":
            # Elsewhere this only skips a lingering TIME_WAIT. On Windows it
            # lets another process bind the port this one is serving on.
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", wanted))
            listener.listen(_BACKLOG)
        except OSError as taken:
            listener.close()
            print(f"port {wanted} is not available: {taken}", file=sys.stderr)
            continue
        return listener
    return None


def _port_of(listener: socket.socket | None) -> int:
    return int(listener.getsockname()[1]) if listener is not None else 0


def _install_signals(stop: Any) -> None:
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        received = getattr(signal, name, None)
        if received is None:
            continue
        try:
            loop.add_signal_handler(received, stop)
        except (NotImplementedError, ValueError, AttributeError):
            # Windows has no loop signal handlers; the C handler hops threads.
            signal.signal(received, lambda *_: loop.call_soon_threadsafe(stop))


def _leased(
    leased: Leases, method: str, params: dict[str, Any], result: Any
) -> None:
    """Which agent sessions this connection has taken responsibility for.

    Read off the answer rather than off the request: the actor a registration
    landed under is the daemon's to decide, and a lease over a name the caller
    merely proposed would end a session belonging to somebody else.
    """
    if not isinstance(result, dict):
        return
    actor = str(result.get("actor") or "")
    if not actor:
        return
    if method == "agent.begin" and result.get("leased"):
        flow = params.get("flow")
        leased.add((str(flow) if flow else None, actor))
    elif method == "agent.end":
        for lease in [held for held in leased if held[1] == actor]:
            leased.discard(lease)


def _reply(
    writer: asyncio.StreamWriter,
    request_id: Any,
    *,
    result: Any = None,
    error: dict[str, Any] | None = None,
) -> None:
    if request_id is None:
        return
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    message["error" if error is not None else "result"] = (
        error if error is not None else result
    )
    if not writer.is_closing():
        writer.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")


def _error(code: int, message: str, *, data: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return body


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    root = (
        Path(args.workspace).resolve()
        if args.workspace
        else workspace.resolve_root(Path.cwd())
    )
    return asyncio.run(Daemon(root).serve(port=args.port, web_port=args.web_port))


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lumlflow-daemon")
    parser.add_argument("--workspace", default=None, help="workspace root")
    parser.add_argument("--port", type=int, default=0, help="loopback port")
    parser.add_argument(
        "--web-port", type=int, default=0, help="loopback port for the browser"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
