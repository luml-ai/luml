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

from luml_api import AsyncLumlClient
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


def exposed_flow(name: str) -> FlowExposed:
    return FlowExposed.model_validate(
        {
            "flow": {
                "id": FLOW_ID,
                "orbit_id": ORBIT_ID,
                "user_id": "0199c455-21ef-7c74-8efe-41470e29bae5",
                "name": name,
                "session": {
                    "id": SESSION_ID,
                    "status": "disconnected",
                    "started_at": "2026-10-03T10:00:00Z",
                },
                "created_at": "2026-10-03T10:00:00Z",
            },
            "session": {
                "id": SESSION_ID,
                "public_url": f"http://{SESSION_ID}.tunnel.example",
                "agent_url": "ws://tunnel.example/agent",
                "expose_token": "luml_tunnel_token",
                "token_expires_at": "2099-01-01T00:00:00Z",
                "heartbeat_interval": 30,
            },
            "app_url": APP_URL,
        }
    )


@dataclass
class FakeFlows:
    """The flows API of LUML as `RelayedFlow` calls it through the sync client."""

    exposed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    remove_error: Exception | None = None
    on_remove: Callable[[str], None] | None = None

    def expose(self, name: str) -> FlowExposed:
        self.exposed.append(name)
        return exposed_flow(name)

    def remove(self, flow_id: str) -> None:
        self.removed.append(flow_id)
        if self.on_remove is not None:
            self.on_remove(flow_id)
        if self.remove_error is not None:
            raise self.remove_error


@dataclass
class FakeClients:
    """Builds fake sync clients that resolve to the only organization and orbit."""

    flows: FakeFlows = field(default_factory=FakeFlows)
    setups: list[dict[str, str | None]] = field(default_factory=list)

    def __call__(
        self, organization: str | None = None, orbit: str | None = None
    ) -> "FakeClient":
        self.setups.append({"organization": organization, "orbit": orbit})
        return FakeClient(self.flows)


class FakeClient:
    def __init__(self, flows: FakeFlows) -> None:
        self.organization = ORGANIZATION_ID
        self.orbit = ORBIT_ID
        self.flows = flows


@dataclass
class FakeServing:
    """The tunnel's serving step: connects at once and serves until cancelled."""

    served: list[tuple[str, str | None, str | None]] = field(default_factory=list)
    cancelled: int = 0
    failure: Exception | None = None
    connects: bool = True

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
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise


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
