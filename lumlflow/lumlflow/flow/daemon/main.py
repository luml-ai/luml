import argparse
import asyncio
import contextlib
import json
import logging
import secrets
import signal
import socket
import sys
import time
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

Announce = Callable[[DaemonRecord], None]
Leases = set[tuple[str | None, str, str]]

_AUTH_TIMEOUT_S = 10.0
_BACKLOG = 64
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

# How long a connected agent may make no call before it stops counting as
# here. The connection is not enough: a harness can keep its MCP server alive
# long after the session that started it ended — Codex's app-server does —
# and an agent that is gone but still connected would keep its name, its
# colour and its place in the pairing line for as long as that lasts.
QUIET_AFTER_S = 15 * 60
_QUIET_SWEEP_S = 30.0
_NOT_PRESENCE = frozenset({"ping", "authenticate"})


class Daemon:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self.instance_id = secrets.token_hex(16)
        self.streams = Streams()
        self.hub = Hub(streams=self.streams)
        self.api = Api(
            self.hub,
            directory=self.directory,
            stop=self.stop,
            attachments=self._attachments,
            leases=self._leases,
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
        self._quiet: dict[asyncio.StreamWriter, Leases] = {}
        self._last_call: dict[tuple[str | None, str], float] = {}
        self.clock: Callable[[], float] = time.monotonic
        self._sweeper: asyncio.Task[None] | None = None
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
        daemon_log.configure()
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
            self._sweeper = asyncio.create_task(self._sweep_quiet())
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
        logger.info("lumlflow daemon on 127.0.0.1:%s", self.port)
        if self.web_port:
            logger.info("workbench on %s", self.api.web)

    def _serve_web(self, listener: socket.socket) -> None:
        self.api.web = f"http://{self.web_host}:{self.web_port}"
        self._web = _WebServer(
            uvicorn.Config(
                web.build_app(self.hub, self.api, self.streams, token=self.token),
                log_config=None,
                access_log=False,
            )
        )
        self._web_task = asyncio.create_task(self._web.serve(sockets=[listener]))

    async def _close(self) -> None:
        # The socket goes first, then the calls it is still carrying: a request
        # still awaiting a kernel has to unwind before the stores it would
        # write to are closed under it, and nothing new may arrive behind it.
        if self._sweeper is not None:
            self._sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweeper
        await self._stop_web()
        await self._stop_serving()
        await self._end_calls()
        await self.watcher.stop()
        await self.hub.close()
        if self._record is not None:
            workspace.clear_record(instance_id=self._record.instance_id)
        self._lock.release()

    async def _stop_web(self) -> None:
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
        self._quiet[writer] = set()
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
            for call in mine:
                call.cancel()
            self._clients.discard(writer)
            self._client_leases.pop(writer, None)
            self._quiet.pop(writer, None)
            writer.close()
            for _, actor, _ in leased:
                self._forget_calls(actor)
            await self._release(leased)

    async def _release(self, leased: "Leases") -> None:
        if self._stopped.is_set():
            return
        ended = sorted(leased, key=lambda lease: (lease[0] or "", lease[1]))
        # Dropped before the ends are committed: the watchers reading the
        # announcement must not see a lease this connection no longer holds.
        leased.clear()
        for flow, actor, _ in ended:
            self.api.forget_agent(actor)
            if flow:
                with contextlib.suppress(FlowError, OSError):
                    self.api.end_activity(flow, actor=actor)
        for flow, actor, _ in ended:
            with contextlib.suppress(FlowError, OSError):
                await self.api.agent_end({"flow": flow, "actor": actor})
            self._announce_agents(flow)

    async def _sweep_quiet(self) -> None:
        while True:
            await asyncio.sleep(_QUIET_SWEEP_S)
            try:
                await self.end_quiet()
                self.api.expire_claims()
            except Exception:
                logger.exception("ending quiet agent sessions failed")

    async def end_quiet(self) -> None:
        if self._stopped.is_set():
            return
        now = self.clock()
        for writer, leased in list(self._client_leases.items()):
            quiet = {
                lease
                for lease in leased
                if now - self._last_call.get((lease[0], lease[1]), now) >= QUIET_AFTER_S
            }
            if not quiet:
                continue
            leased.difference_update(quiet)
            self._quiet.setdefault(writer, set()).update(quiet)
            for flow, actor, label in sorted(quiet, key=lambda lease: lease[1]):
                self.api.forget_agent(actor)
                if not flow:
                    continue
                with contextlib.suppress(FlowError, OSError):
                    self.api.end_activity(flow, actor=actor)
                with contextlib.suppress(FlowError, OSError):
                    await self.api.agent_end(
                        {
                            "flow": flow,
                            "actor": actor,
                            "intent": f"{label} went quiet",
                        }
                    )
                self._announce_agents(flow)

    async def _revive(
        self, writer: asyncio.StreamWriter, leased: Leases, actor: str
    ) -> None:
        quiet = self._quiet.get(writer)
        if not quiet:
            return
        returning = [lease for lease in quiet if lease[1] == actor]
        for lease in returning:
            quiet.discard(lease)
            flow, _, label = lease
            if not flow:
                continue
            try:
                begun = await self.api.agent_begin(
                    {
                        "flow": flow,
                        "actor": actor,
                        "label": label,
                        "lease": True,
                        "intent": f"{label} is back",
                    }
                )
            except FlowError:
                continue
            leased.add((flow, actor, str(begun.get("label") or label)))
            self._last_call[(flow, actor)] = self.clock()
            self._announce_agents(flow)

    def _heard_from(self, leased: Leases, actor: str) -> None:
        now = self.clock()
        for flow, held, _ in leased:
            if held == actor:
                self._last_call[(flow, actor)] = now

    def _forget_calls(self, actor: str) -> None:
        for key in [key for key in self._last_call if key[1] == actor]:
            del self._last_call[key]

    def _leases(self) -> Leases:
        return {
            lease
            for client_leases in self._client_leases.values()
            for lease in client_leases
        }

    def _announce_activity(self, activity: "Activity", phase: str) -> None:
        flow, actor, label, tool, slug = activity
        with contextlib.suppress(FlowError, OSError):
            self.api.announce_activity(
                flow,
                actor=actor,
                label=label,
                tool=tool,
                slug=slug,
                phase=phase,  # type: ignore[arg-type]
            )

    def _announce_agents(self, flow: str | None) -> None:
        with contextlib.suppress(FlowError, OSError):
            self.api.announce_agents(flow)

    def _report_attached(self) -> None:
        leases = sorted(
            self._leases(),
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
        leases = self._leases()
        open_flows = sorted(
            session.ref.address
            for session in self.hub.opened()
            if excluded is None or session.ref.path != excluded
        )
        # Runs carry on whether or not their caller is still connected, so
        # stopping now would kill another caller's work.
        current = asyncio.current_task()
        return {
            "leased_sessions": len(leases),
            "stream_subscribers": self.streams.watchers,
            "open_flows": open_flows,
            "active_runs": sum(
                session.queue.in_flight for session in self.hub.opened()
            ),
            "other_requests": sum(
                1 for call in self._calls if call is not current and not call.done()
            ),
        }

    async def _end_calls(self) -> None:
        calls = [call for call in self._calls if not call.done()]
        for call in calls:
            call.cancel()
        await asyncio.gather(*calls, return_exceptions=True)

    async def _authenticated(self, reader: asyncio.StreamReader) -> bool:
        try:
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
        params = message.get("params") or {}
        caller = str(params.get("actor") or "")
        if caller and str(message["method"]) not in _NOT_PRESENCE:
            if str(message["method"]) != "agent.end":
                await self._revive(writer, leased, caller)
            else:
                quiet = self._quiet.get(writer, set())
                quiet.difference_update(
                    {lease for lease in quiet if lease[1] == caller}
                )
            self._heard_from(leased, caller)
        activity = _activity(leased, str(message["method"]), params)
        announced = False
        try:
            if activity is not None:
                self.api.fence(str(message["method"]), params)
                self.api.claim(str(message["method"]), params, label=activity[2])
                self._announce_activity(activity, "started")
                announced = True
            result = await method(params)
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
            name = str(message["method"])
            if activity is not None:
                with contextlib.suppress(FlowError, OSError):
                    self.api.observed(name, params)
                    self.api.settled(name, params)
            _leased(leased, name, params, result)
            if name == "agent.begin" and caller:
                self._heard_from(leased, caller)
            if (
                name == "agent.begin"
                and isinstance(result, dict)
                and result.get("leased")
            ):
                self._announce_agents(result.get("flow"))
        finally:
            if activity is not None and announced:
                self._announce_activity(activity, "ended")
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


Activity = tuple[str, str, str, str, str | None]

_SILENT = frozenset(
    {
        "ping",
        "authenticate",
        "agent.begin",
        "agent.end",
        "status",
        "workspace.list",
        "flow.open",
        "tree",
        "agents.harnesses",
    }
)


def _activity(leased: Leases, method: str, params: dict[str, Any]) -> Activity | None:
    if method in _SILENT:
        return None
    actor = str(params.get("actor") or "")
    if not actor:
        return None
    held = [lease for lease in leased if lease[1] == actor and lease[0]]
    if not held:
        return None
    asked = params.get("flow")
    flow, _, label = next(
        (lease for lease in held if asked and lease[0] == asked), held[0]
    )
    slug = params.get("slug") or params.get("target")
    named = str(slug).split(".", 1)[0] if slug else None
    return (str(flow), actor, label, method, named or None)


def _leased(leased: Leases, method: str, params: dict[str, Any], result: Any) -> None:
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
