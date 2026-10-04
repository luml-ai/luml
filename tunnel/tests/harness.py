"""Runs the relay, the agent and a small test service in one process."""

import asyncio
import json
import secrets
import socket
import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.types import ASGIApp
from starlette.websockets import WebSocket
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from luml_tunnel.agent import Agent, FixedToken, LoopbackService, ReconnectPolicy
from luml_tunnel.cookies import ViewerCookies
from luml_tunnel.frames import MAX_FRAME_BYTES, RelayLimits
from luml_tunnel.headers import TOKEN_HEADER
from luml_tunnel.protocol import MAX_RENEWALS_PER_MINUTE
from luml_tunnel.relay import CONNECT_PATH, Relay, RelayServer, RelaySettings
from luml_tunnel.relay_api import MAX_REQUESTS_IN_FLIGHT, REPORT_INTERVAL_SECONDS, RelayApi
from luml_tunnel.routing import MAX_AGENTS
from luml_tunnel.tokens import (
    CACHE_WINDOW_SECONDS,
    MAX_CACHE_ENTRIES,
    LumlTokenVerifier,
    TokenKind,
)

LUML_URL = "http://luml.test"
RELAY_TOKEN = "dfsrelay_lab"
RELAY_ID = "relay-1"
OTHER_RELAY_ID = "relay-2"
BASE_DOMAIN = "tunnel.example"
APP_URL = "https://app.luml.example"
SESSION = "k3f9x2ab"
SESSION_HOST = f"{SESSION}.{BASE_DOMAIN}"
USER = "user-1"

LARGE_BODY_CHUNK = 64 * 1024
LARGE_BODY_CHUNKS = 8192

FAST_RECONNECT = ReconnectPolicy(initial_delay=0.05, max_delay=0.4)


@dataclass
class RecordedRequest:
    method: str
    path: str
    query: str
    headers: list[tuple[str, str]]
    body: bytes

    def header(self, name: str) -> list[str]:
        return [value for key, value in self.headers if key == name]


@dataclass
class EchoService:
    requests: list[RecordedRequest] = field(default_factory=list)
    large_body_produced: int = 0
    stall_released: asyncio.Event = field(default_factory=asyncio.Event)
    websocket_requests: list[RecordedRequest] = field(default_factory=list)
    websocket_closes: list[tuple[int, str]] = field(default_factory=list)

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                WebSocketRoute("/ws/echo", self._websocket_echo),
                WebSocketRoute("/ws/refuse", self._websocket_refuse),
                Route("/large", self._large),
                Route("/stall", self._stall),
                Route("/no-frames", self._no_frames),
                Route("/domain-cookie", self._domain_cookie),
                Route("/{path:path}", self._echo, methods=["GET", "POST", "PUT", "DELETE"]),
            ]
        )

    async def _echo(self, request: Request) -> Response:
        recorded = RecordedRequest(
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            headers=[(key.decode(), value.decode()) for key, value in request.headers.raw],
            body=await request.body(),
        )
        self.requests.append(recorded)
        response = Response(
            json.dumps({"path": recorded.path, "body": recorded.body.decode()}),
            status_code=int(request.headers.get("x-reply-status", "200")),
            media_type="application/json",
            headers={"x-service": "echo"},
        )
        response.set_cookie("first", "1")
        response.set_cookie("second", "2")
        return response

    async def _websocket_echo(self, websocket: WebSocket) -> None:
        """Greets, echoes every message, and closes with code 4321 when told `close`."""
        self.websocket_requests.append(
            RecordedRequest(
                method="GET",
                path=websocket.url.path,
                query=websocket.url.query,
                headers=[(key.decode(), value.decode()) for key, value in websocket.headers.raw],
                body=b"",
            )
        )
        offered = websocket.scope.get("subprotocols", [])
        await websocket.accept(offered[0] if offered else None)
        await websocket.send_text("hello")
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                self.websocket_closes.append((message["code"], message.get("reason") or ""))
                return
            if message.get("text") == "close":
                await websocket.close(4321, "service closed")
                return
            if message.get("text") is not None:
                await websocket.send_text(message["text"])
            else:
                await websocket.send_bytes(message["bytes"])

    async def _websocket_refuse(self, websocket: WebSocket) -> None:
        await websocket.send_denial_response(PlainTextResponse("no WebSockets here", 403))

    async def _large(self, request: Request) -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            for _ in range(LARGE_BODY_CHUNKS):
                self.large_body_produced += LARGE_BODY_CHUNK
                yield b"x" * LARGE_BODY_CHUNK

        return StreamingResponse(chunks(), media_type="application/octet-stream")

    async def _no_frames(self, request: Request) -> Response:
        headers = {
            "x-frame-options": "DENY",
            "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
        }
        return Response("no frames", headers=headers)

    async def _domain_cookie(self, request: Request) -> Response:
        response = Response("cookie")
        response.set_cookie("service", "1", domain=BASE_DOMAIN, path="/", httponly=True)
        return response

    async def _stall(self, request: Request) -> Response:
        await self.stall_released.wait()
        return Response("released")


def bound_socket(port: int = 0) -> socket.socket:
    """A socket bound to a loopback port; connections are refused until it serves."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    return sock


def port_of(sock: socket.socket) -> int:
    return int(sock.getsockname()[1])


@asynccontextmanager
async def serve(app: ASGIApp, sock: socket.socket | None = None) -> AsyncGenerator[int]:
    sock = sock or bound_socket()
    config = uvicorn.Config(
        app,
        lifespan="on",
        log_level="warning",
        ws="websockets-sansio",
        ws_max_size=MAX_FRAME_BYTES,
        timeout_graceful_shutdown=1,
        proxy_headers=False,
    )
    server = RelayServer(app, config) if isinstance(app, Relay) else uvicorn.Server(config)
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    await until(lambda: server.started or serving.done())
    if serving.done():
        serving.result()
    try:
        yield port_of(sock)
    finally:
        server.should_exit = True
        await serving


async def until(condition: Callable[[], bool], timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)


class Outage(StrEnum):
    UNREACHABLE = "unreachable"
    FAILING = "failing"
    SILENT = "silent"


@dataclass
class StoredToken:
    kind: TokenKind
    session: str
    user: str
    relay: str
    expires_at: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    launched: bool = False
    destination: str | None = None


@dataclass
class FakeRelayApi:
    """LUML's relay-facing API in process, with the backend's routes and answers.

    It knows one relay by its token unless told otherwise, and stores what it issues.
    Its clock decides when tokens and grants expire.
    """

    relay_tokens: dict[str, str] = field(default_factory=lambda: {RELAY_TOKEN: RELAY_ID})
    base_domain: str = BASE_DOMAIN
    app_origins: list[str] = field(default_factory=list)
    app_url: str = APP_URL
    tokens: dict[str, StoredToken] = field(default_factory=dict)
    ended_sessions: set[str] = field(default_factory=set)
    outage: Outage | None = None
    validated: list[str] = field(default_factory=list)
    launches: list[str] = field(default_factory=list)
    grant_checks: list[str] = field(default_factory=list)
    descriptions: int = 0
    reports: list[int] = field(default_factory=list)
    reported_capabilities: list[dict[str, Any]] = field(default_factory=list)
    validation_delay: float = 0.0
    open_validations: int = 0
    most_open_validations: int = 0
    clock: Callable[[], float] = time.time

    def issue(
        self,
        kind: TokenKind,
        session: str = SESSION,
        user: str = USER,
        lifetime: timedelta = timedelta(minutes=10),
        relay: str = RELAY_ID,
        destination: str | None = None,
    ) -> str:
        token = secrets.token_urlsafe(24)
        expires_at = self._now() + lifetime
        self.tokens[token] = StoredToken(
            kind, session, user, relay, expires_at, destination=destination
        )
        return token

    def validations_of(self, token: str) -> int:
        return self.validated.count(token)

    def grant_of(self, token: str) -> str:
        return self.tokens[token].id

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), UTC)

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                Route("/relays/v1/self", self._describe),
                Route("/relays/v1/tokens/validate", self._validate, methods=["POST"]),
                Route("/relays/v1/grants/check", self._check_grant, methods=["POST"]),
                Route("/relays/v1/report", self._report, methods=["POST"]),
            ]
        )

    def transport(self) -> httpx.AsyncBaseTransport:
        return _FakeLumlTransport(self)

    def _caller(self, request: Request) -> str | None:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        return self.relay_tokens.get(token) if scheme.lower() == "bearer" else None

    async def _describe(self, request: Request) -> JSONResponse:
        self.descriptions += 1
        relay = self._caller(request)
        if relay is None:
            return JSONResponse({"detail": "Invalid relay token"}, 401)
        description = {
            "id": relay,
            "label": "lab",
            "base_domain": self.base_domain,
            "agent_url": f"wss://{self.base_domain}{CONNECT_PATH}",
            "status": "enabled",
            "app_origins": self.app_origins,
            "app_url": self.app_url,
        }
        return JSONResponse(description)

    async def _validate(self, request: Request) -> JSONResponse:
        relay = self._caller(request)
        if relay is None:
            return JSONResponse({"detail": "Invalid relay token"}, 401)
        self.open_validations += 1
        self.most_open_validations = max(self.most_open_validations, self.open_validations)
        try:
            await asyncio.sleep(self.validation_delay)
            return await self._answer_validation(relay, await request.json())
        finally:
            self.open_validations -= 1

    async def _answer_validation(self, relay: str, body: dict[str, Any]) -> JSONResponse:
        launch = body.get("launch", False)
        (self.launches if launch else self.validated).append(body["token"])
        stored = self.tokens.get(body["token"])
        if (
            stored is None
            or not self._active(stored, relay)
            or stored.launched
            or (launch and stored.kind != TokenKind.VIEW)
        ):
            return JSONResponse({"active": False})
        if launch:
            stored.launched = True
            stored.expires_at = self._now() + timedelta(hours=12)
        answer = {
            "active": True,
            "kind": stored.kind,
            "session_id": stored.session,
            "user_id": stored.user,
            "expires_at": stored.expires_at.isoformat(),
            "grant_id": stored.id if launch else None,
            "destination": stored.destination if launch else None,
        }
        return JSONResponse(answer)

    async def _check_grant(self, request: Request) -> JSONResponse:
        relay = self._caller(request)
        if relay is None:
            return JSONResponse({"detail": "Invalid relay token"}, 401)
        grant = (await request.json())["grant_id"]
        self.grant_checks.append(grant)
        stored = next((token for token in self.tokens.values() if token.id == grant), None)
        if stored is None or not stored.launched or not self._active(stored, relay):
            return JSONResponse({"active": False})
        answer = {
            "active": True,
            "session_id": stored.session,
            "user_id": stored.user,
            "expires_at": stored.expires_at.isoformat(),
        }
        return JSONResponse(answer)

    async def _report(self, request: Request) -> Response:
        if self._caller(request) is None:
            return JSONResponse({"detail": "Invalid relay token"}, 401)
        report = await request.json()
        self.reports.append(report["connected_agents"])
        self.reported_capabilities.append(report["capabilities"])
        return Response(status_code=204)

    def _active(self, stored: StoredToken, relay: str) -> bool:
        return (
            stored.relay == relay
            and stored.session not in self.ended_sessions
            and stored.expires_at > self._now()
        )


class _FakeLumlTransport(httpx.AsyncBaseTransport):
    def __init__(self, luml: FakeRelayApi) -> None:
        self._luml = luml
        self._app = httpx.ASGITransport(luml.app())

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._luml.outage is Outage.UNREACHABLE:
            raise httpx.ConnectError("LUML is down", request=request)
        if self._luml.outage is Outage.FAILING:
            return httpx.Response(500, json={"detail": "Internal Server Error"})
        if self._luml.outage is Outage.SILENT:
            await asyncio.Event().wait()
        return await self._app.handle_async_request(request)


@dataclass
class FakeClock:
    now: float = field(default_factory=time.time)

    def __call__(self) -> float:
        return self.now


def create_api(luml: FakeRelayApi, max_in_flight: int = MAX_REQUESTS_IN_FLIGHT) -> RelayApi:
    return RelayApi(
        LUML_URL, RELAY_TOKEN, luml.transport(), timeout=0.5, max_in_flight=max_in_flight
    )


def create_verifier(
    luml: FakeRelayApi,
    cache_window: float = CACHE_WINDOW_SECONDS,
    clock: Callable[[], float] = time.time,
    max_entries: int = MAX_CACHE_ENTRIES,
    max_in_flight: int = MAX_REQUESTS_IN_FLIGHT,
) -> LumlTokenVerifier:
    return LumlTokenVerifier(create_api(luml, max_in_flight), cache_window, clock, max_entries)


def create_relay(
    luml: FakeRelayApi,
    limits: RelayLimits | None = None,
    app_origins: tuple[str, ...] = (),
    cookies: ViewerCookies | None = None,
    verifier: LumlTokenVerifier | None = None,
    reports_to: RelayApi | None = None,
    max_agents: int = MAX_AGENTS,
    max_renewals_per_minute: int = MAX_RENEWALS_PER_MINUTE,
    report_interval: float = REPORT_INTERVAL_SECONDS,
) -> Relay:
    settings = RelaySettings(
        base_domain=BASE_DOMAIN,
        limits=limits or RelayLimits(),
        app_origins=app_origins,
        app_url=APP_URL,
        max_agents=max_agents,
        max_renewals_per_minute=max_renewals_per_minute,
        report_interval=report_interval,
    )
    return Relay(
        settings, verifier or create_verifier(luml), cookies=cookies, reports_to=reports_to
    )


def relay_url(relay_port: int) -> str:
    return f"ws://127.0.0.1:{relay_port}{CONNECT_PATH}"


@asynccontextmanager
async def running_agent(
    relay: Relay,
    relay_port: int,
    token: str,
    service_port: int,
    present_loopback_host: bool = False,
) -> AsyncGenerator[Agent]:
    service = LoopbackService(service_port, present_loopback_host)
    agent = Agent(relay_url(relay_port), FixedToken(token), service, FAST_RECONNECT)
    previous = relay.agents.get(SESSION)
    running = asyncio.create_task(agent.run())
    try:
        await until(lambda: relay.agents.get(SESSION) not in (None, previous) or running.done())
        if running.done():
            running.result()
        yield agent
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        await service.aclose()


def viewer_websocket(
    relay_port: int, token: str | None, path: str, subprotocols: list[str] | None = None
) -> connect:
    headers = {TOKEN_HEADER: token} if token is not None else {}
    return connect(
        f"ws://{SESSION_HOST}{path}",
        host="127.0.0.1",
        port=relay_port,
        proxy=None,
        additional_headers=headers,
        subprotocols=[Subprotocol(offered) for offered in subprotocols or []] or None,
    )


def viewer(relay_port: int, token: str | None, host: str = SESSION_HOST) -> httpx.AsyncClient:
    headers = {"host": host}
    if token is not None:
        headers[TOKEN_HEADER] = token
    return httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{relay_port}", headers=headers, timeout=5.0
    )
