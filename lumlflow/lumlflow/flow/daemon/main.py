"""The one per-user daemon, serving every flow opened by path."""

import argparse
import asyncio
import contextlib
import json
import logging
import secrets
import signal
import socket
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import uvicorn

from lumlflow.flow.daemon import daemon_log, web, workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.framing import (
    STREAM_LIMIT_BYTES,
    STREAM_LIMIT_LABEL,
    discard_oversized_line,
)
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.daemon.watcher import Watcher
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowError

# What a caller is told once the workspace is being served, and from where.
Announce = Callable[[DaemonRecord], None]
# The agent sessions one connection is carrying, as (flow, actor, label).
Leases = set[tuple[str | None, str, str]]

_AUTH_TIMEOUT_S = 10.0
_BACKLOG = 64
# How long the browser endpoint is given to close its connections politely.
_WEB_GRACE_S = 3.0
_DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 5000
ALREADY_RUNNING = 75

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
FLOW_ERROR = -32000

logger = logging.getLogger(__name__)


class Daemon:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self.instance_id = secrets.token_hex(16)
        # Everything a browser watches goes through here, and a session that is
        # opened before it would announce its commits to nobody.
        self.streams = Streams()
        self.hub = Hub(streams=self.streams)
        self.api = Api(
            self.hub,
            directory=self.directory,
            stop=self.stop,
            attachments=self._attachments,
            instance_id=self.instance_id,
        )
        self.watcher = Watcher(self.hub)
        self.token = secrets.token_hex(16)
        self.port = 0
        self.web_host = _DEFAULT_WEB_HOST
        self.web_port = 0
        self._lock = workspace.WorkspaceLock()
        self._server: asyncio.AbstractServer | None = None
        self._web: uvicorn.Server | None = None
        self._web_task: asyncio.Task[None] | None = None
        self._record: DaemonRecord | None = None
        self._calls: set[asyncio.Task[None]] = set()
        self._clients: set[asyncio.StreamWriter] = set()
        self._client_leases: dict[asyncio.StreamWriter, Leases] = {}
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def serve(
        self,
        *,
        port: int = 0,
        web_host: str = _DEFAULT_WEB_HOST,
        web_port: int = DEFAULT_WEB_PORT,
        exact_web_port: bool = False,
        announce: Announce | None = None,
        report_attached: bool = False,
    ) -> int:
        """Hold the singleton lock and serve until this process is stopped."""
        daemon_log.configure()
        # The signals before the lock: a Ctrl-C during startup is an answer,
        # not a traceback over a workspace half taken.
        _install_signals(self.stop)
        _install_exception_logging()
        # The lock before anything else: whoever holds it owns the stores, and
        # nothing this process does afterwards may touch them without it.
        if not self._lock.acquire():
            logger.warning("another lumlflow daemon is already running")
            return ALREADY_RUNNING
        listener: socket.socket | None = None
        try:
            try:
                self.api.sync_agents()
            except FlowError as error:
                logger.warning("agent setup sync failed: %s", error)
            self._server = await asyncio.start_server(
                self._session, "127.0.0.1", port, limit=STREAM_LIMIT_BYTES
            )
            self.port = int(self._server.sockets[0].getsockname()[1])
            self.web_host = web_host
            listener = (
                _bind_exactly(self.web_host, web_port)
                if exact_web_port
                else _bind_web(self.web_host, web_port)
            )
            self.web_port = _port_of(listener)
            record = workspace.new_record(
                instance_id=self.instance_id,
                port=self.port,
                token=self.token,
                web_host=self.web_host,
                web_port=self.web_port,
                tracker_store=str(self.hub.tracker.store_path),
            )
            workspace.write_record(record)
            self._record = record
            self._serve_web(listener)
            try:
                self.watcher.start()
            except OSError as unwatchable:
                logger.warning("not watching flows: %s", unwatchable)
            self._announce(record)
            if announce is not None:
                announce(record)
            await self._stopped.wait()
            if report_attached:
                self._report_attached()
        finally:
            if listener is not None and self._web_task is None:
                listener.close()
            await self._close()
        return 0

    def _announce(self, record: DaemonRecord) -> None:
        """The log line a background process leaves for whoever reads its log."""
        logger.info("lumlflow daemon on 127.0.0.1:%s", self.port)
        if self.web_port:
            logger.info("workbench on %s", self.api.web)

    def _serve_web(self, listener: socket.socket) -> None:
        """Put the browser's surface on the port that was just bound.

        The app is built here rather than in `__init__` because it carries the
        token, and the token is what makes this port the workspace's rather
        than anything else's on the machine.
        """
        self.api.web = f"http://{self.web_host}:{self.web_port}"
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
            workspace.clear_record(instance_id=self._record.instance_id)
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
        self._client_leases[writer] = leased
        try:
            while True:
                try:
                    line = await reader.readuntil()
                except asyncio.LimitOverrunError as overrun:
                    await discard_oversized_line(reader, overrun)
                    _reply_unaddressed(
                        writer,
                        _error(
                            INVALID_REQUEST,
                            f"RPC lines are limited to {STREAM_LIMIT_LABEL}",
                        ),
                    )
                    with contextlib.suppress(OSError):
                        await writer.drain()
                    continue
                except asyncio.IncompleteReadError as incomplete:
                    if incomplete.partial:
                        call = asyncio.create_task(
                            self._handle(incomplete.partial, writer, leased)
                        )
                        mine.add(call)
                        self._calls.add(call)
                        call.add_done_callback(mine.discard)
                        call.add_done_callback(self._calls.discard)
                    break
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
            self._client_leases.pop(writer, None)
            writer.close()
            await self._release(leased)

    async def _release(self, leased: "Leases") -> None:
        """End the agent sessions this connection was carrying.

        The connection is the session for a client that connected to be paired,
        so one that was killed rather than closed must leave no flow registered
        to nobody.

        A daemon on its way out is the other case entirely: the client is still
        there and will register again with whoever serves the workspace next,
        and committing here would race the stores closing underneath it.
        """
        if self._stopped.is_set():
            return
        for flow, actor, _ in sorted(
            leased, key=lambda lease: (lease[0] or "", lease[1])
        ):
            with contextlib.suppress(FlowError, OSError):
                await self.api.agent_end({"flow": flow, "actor": actor})
        leased.clear()

    def _report_attached(self) -> None:
        leases = sorted(
            {
                lease
                for client_leases in self._client_leases.values()
                for lease in client_leases
            },
            key=lambda lease: (lease[2].casefold(), lease[0] or ""),
        )
        outside_flows = sorted(
            str(session.ref.path)
            for session in self.hub.opened()
            if not session.ref.path.is_relative_to(self.directory)
        )
        attached: list[str] = []
        if leases:
            sessions = ", ".join(
                f"{label} on {flow}" if flow else label for flow, _, label in leases
            )
            noun = "session" if len(leases) == 1 else "sessions"
            attached.append(f"leased agent {noun}: {sessions}")
        if self.streams.watchers:
            noun = "subscriber" if self.streams.watchers == 1 else "subscribers"
            attached.append(f"{self.streams.watchers} stream {noun}")
        if outside_flows:
            noun = "flow" if len(outside_flows) == 1 else "flows"
            attached.append(
                f"open {noun} outside {self.directory}: {', '.join(outside_flows)}"
            )
        if attached:
            print(f"stopping with attached clients: {'; '.join(attached)}", flush=True)

    def _attachments(self, flow_path: str) -> dict[str, Any]:
        excluded = Path(flow_path).resolve() if flow_path else None
        leases = {
            lease
            for client_leases in self._client_leases.values()
            for lease in client_leases
        }
        open_flows = sorted(
            session.ref.address
            for session in self.hub.opened()
            if excluded is None or session.ref.path != excluded
        )
        return {
            "leased_sessions": len(leases),
            "stream_subscribers": self.streams.watchers,
            "open_flows": open_flows,
        }

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
            logger.exception("socket RPC `%s` failed", message.get("method"))
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


def serve_here(
    directory: Path, *, web_host: str, web_port: int, announce: Announce
) -> int:
    """Run the daemon role in the visible `ui` process."""
    daemon_log.configure()
    try:
        return asyncio.run(
            Daemon(directory).serve(
                web_host=web_host,
                web_port=web_port,
                exact_web_port=True,
                announce=announce,
                report_attached=True,
            )
        )
    except FlowError:
        raise
    except Exception as failure:
        logger.exception("daemon stopped unexpectedly")
        raise FlowError(
            f"the lumlflow daemon failed. see {workspace.log_path()}"
        ) from failure


def _bind_exactly(host: str, port: int) -> socket.socket:
    """The port asked for, or a refusal naming it. Never a different one."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((host, port))
        listener.listen(_BACKLOG)
    except OSError as taken:
        listener.close()
        raise FlowError(
            f"port {port} is already in use. serve on another with `--port`"
        ) from taken
    return listener


def _bind_web(host: str, port: int) -> socket.socket:
    """The requested host, on the requested port or whichever one is free.

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
            listener.bind((host, wanted))
            listener.listen(_BACKLOG)
        except OSError as taken:
            listener.close()
            logger.warning("port %s is not available: %s", wanted, taken)
            continue
        return listener
    raise FlowError(f"web port {port} could not be bound. choose another with `--port`")


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


def _install_exception_logging() -> None:
    asyncio.get_running_loop().set_exception_handler(_log_loop_exception)


def _log_loop_exception(
    _loop: asyncio.AbstractEventLoop, context: dict[str, Any]
) -> None:
    failure = context.get("exception")
    message = str(context.get("message") or "unhandled daemon task failure")
    if isinstance(failure, BaseException):
        logger.error(
            message,
            exc_info=(type(failure), failure, failure.__traceback__),
        )
    else:
        logger.error(message)


def _leased(leased: Leases, method: str, params: dict[str, Any], result: Any) -> None:
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
        flow = result.get("flow") or params.get("flow")
        label = str(result.get("label") or actor)
        leased.add((str(flow) if flow else None, actor, label))
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


def _reply_unaddressed(writer: asyncio.StreamWriter, error: dict[str, Any]) -> None:
    if not writer.is_closing():
        writer.write(
            json.dumps(
                {"jsonrpc": "2.0", "id": None, "error": error},
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )


def _error(code: int, message: str, *, data: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return body


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    daemon_log.configure()
    try:
        return asyncio.run(
            Daemon(Path.cwd()).serve(
                port=args.port, web_host=args.web_host, web_port=args.web_port
            )
        )
    except FlowError as failure:
        logger.error("daemon could not start: %s", failure)
        return 1
    except Exception:
        logger.exception("daemon stopped unexpectedly")
        return 1


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lumlflow-daemon")
    parser.add_argument("--port", type=int, default=0, help="loopback port")
    parser.add_argument(
        "--web-host", default=_DEFAULT_WEB_HOST, help="host for the browser"
    )
    parser.add_argument(
        "--web-port", type=int, default=DEFAULT_WEB_PORT, help="port for the browser"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
