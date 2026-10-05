import asyncio
import json
import socket
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
from luml_api import AsyncLumlClient, NotFoundError
from luml_api._types import FlowExposed, LiveSessionStart

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
FLOW_ID = "0199c455-21ee-7c74-8efe-41470e29bae5"
SESSION_ID = "k3f9x2ab"
APP_URL = (
    f"https://app.luml.test/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/flow"
)
STATUS_PATH = "/api/auth/status"

STUB_LUMLFLOW = """#!{python}
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

with open(os.environ["STUB_LUMLFLOW_RECORD"], "a") as record:
    record.write(json.dumps({{"pid": os.getpid(), "argv": sys.argv[1:]}}) + "\\n")
port = int(sys.argv[sys.argv.index("--port") + 1])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({{"has_key": False}}).encode()
        self.send_response(200 if self.path == "{status_path}" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def write_stub_lumlflow(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    command = directory / "lumlflow"
    command.write_text(
        STUB_LUMLFLOW.format(python=sys.executable, status_path=STATUS_PATH)
    )
    command.chmod(0o755)
    return command


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def exposed_flow(name: str, session_id: str = SESSION_ID) -> FlowExposed:
    return FlowExposed.model_validate(
        {
            "flow": {
                "id": FLOW_ID,
                "orbit_id": ORBIT_ID,
                "user_id": "0199c455-21ef-7c74-8efe-41470e29bae5",
                "name": name,
                "session": {
                    "id": session_id,
                    "status": "disconnected",
                    "started_at": "2026-10-03T10:00:00Z",
                },
                "created_at": "2026-10-03T10:00:00Z",
            },
            "session": {
                "id": session_id,
                "public_url": f"http://{session_id}.sessions.example",
                "agent_url": "ws://sessions.example/agent",
                "expose_token": "luml_relay_token",
                "token_expires_at": "2099-01-01T00:00:00Z",
                "heartbeat_interval": 30,
            },
            "app_url": APP_URL,
        }
    )


def not_found(session_id: str) -> NotFoundError:
    url = f"http://luml.test/live-sessions/{session_id}/end"
    return NotFoundError(
        "Live session not found",
        response=httpx.Response(404, request=httpx.Request("POST", url)),
        body={"detail": "Live session not found"},
    )


@dataclass
class FakeLiveSessions:
    """The live sessions API of LUML: ending an ended session changes nothing."""

    live: set[str] = field(default_factory=set)
    gone: set[str] = field(default_factory=set)
    ended: list[str] = field(default_factory=list)
    end_error: Exception | None = None
    on_end: Callable[[str], None] | None = None

    def end(self, session_id: str) -> None:
        self.ended.append(session_id)
        if self.on_end is not None:
            self.on_end(session_id)
        if self.end_error is not None:
            raise self.end_error
        if session_id in self.gone:
            raise not_found(session_id)
        self.live.discard(session_id)


@dataclass
class FakeFlows:
    """The flows API of LUML: exposing a name replaces the session it had."""

    live_sessions: FakeLiveSessions
    exposed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    sessions: dict[str, str] = field(default_factory=dict)

    def expose(self, name: str) -> FlowExposed:
        self.exposed.append(name)
        replaced = self.sessions.get(name)
        if replaced is not None:
            self.live_sessions.live.discard(replaced)
        session_id = SESSION_ID if len(self.exposed) == 1 else f"s{len(self.exposed)}"
        self.sessions[name] = session_id
        self.live_sessions.live.add(session_id)
        return exposed_flow(name, session_id)

    def remove(self, flow_id: str) -> None:
        self.removed.append(flow_id)


@dataclass
class FakeClients:
    """Builds fake sync clients that resolve to the only organization and orbit."""

    live_sessions: FakeLiveSessions = field(default_factory=FakeLiveSessions)
    setups: list[dict[str, str | None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.flows = FakeFlows(self.live_sessions)

    def __call__(
        self, organization: str | None = None, orbit: str | None = None
    ) -> "FakeClient":
        self.setups.append({"organization": organization, "orbit": orbit})
        return FakeClient(self.flows, self.live_sessions)


class FakeClient:
    def __init__(self, flows: FakeFlows, live_sessions: FakeLiveSessions) -> None:
        self.organization = ORGANIZATION_ID
        self.orbit = ORBIT_ID
        self.flows = flows
        self.live_sessions = live_sessions


@dataclass
class FakeServing:
    """The relay package's serving step: connects at once and serves until cancelled.

    `end_session` makes it return as it does when LUML ends the session.
    """

    served: list[tuple[str, str | None, str | None]] = field(default_factory=list)
    cancelled: int = 0
    failure: Exception | None = None
    connects: bool = True
    returned: threading.Event = field(default_factory=threading.Event)
    _ended: asyncio.Event | None = None
    _loop: asyncio.AbstractEventLoop | None = None

    def end_session(self) -> None:
        assert self._loop is not None
        assert self._ended is not None
        self._loop.call_soon_threadsafe(self._ended.set)
        assert self.returned.wait(5)

    async def __call__(
        self,
        client: AsyncLumlClient,
        started: LiveSessionStart,
        service: Any,  # noqa: ANN401
        stop: asyncio.Event,
        reconnect: Any = None,  # noqa: ANN401
        connected: asyncio.Event | None = None,
    ) -> None:
        self.served.append((started.id, client.organization, client.orbit))
        if self.failure is not None:
            raise self.failure
        if self.connects and connected is not None:
            connected.set()
        self._loop = asyncio.get_running_loop()
        self._ended = asyncio.Event()
        try:
            await self._ended.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        self.returned.set()


def _handler(answers_as_lumlflow: bool) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if answers_as_lumlflow and self.path == STATUS_PATH:
                status, body = 200, json.dumps({"has_key": True}).encode()
            else:
                status, body = 404, b"<html>Not found</html>"
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    return Handler


@contextmanager
def local_server(port: int, answers_as_lumlflow: bool) -> Iterator[None]:
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler(answers_as_lumlflow))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
