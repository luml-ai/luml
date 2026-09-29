"""Runs the relay, the agent and a small test service in one process."""

import asyncio
import json
import socket
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.types import ASGIApp
from starlette.websockets import WebSocket
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from luml_tunnel.agent import Agent, FixedToken, LoopbackService, ReconnectPolicy
from luml_tunnel.cookies import ViewerCookies
from luml_tunnel.frames import MAX_FRAME_BYTES, RelayLimits
from luml_tunnel.headers import TOKEN_HEADER
from luml_tunnel.relay import CONNECT_PATH, Relay, RelayServer, RelaySettings
from luml_tunnel.signing import TokenSigner
from luml_tunnel.tokens import TokenKind
from luml_tunnel.verification import IssuerKeys, JwksTokenVerifier

ISSUER = "https://luml.example"
RELAY_ID = "relay-1"
BASE_DOMAIN = "tunnel.example"
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


def create_relay(
    key_file: Path,
    limits: RelayLimits | None = None,
    app_origins: tuple[str, ...] = (),
    cookies: ViewerCookies | None = None,
) -> Relay:
    settings = RelaySettings(
        base_domain=BASE_DOMAIN,
        relay_id=RELAY_ID,
        issuer=ISSUER,
        issuer_keys=str(key_file),
        limits=limits or RelayLimits(),
        app_origins=app_origins,
    )
    verifier = JwksTokenVerifier(IssuerKeys(str(key_file)), ISSUER, RELAY_ID)
    return Relay(settings, verifier, cookies=cookies)


def sign(
    signer: TokenSigner,
    kind: TokenKind,
    session: str = SESSION,
    user: str = USER,
    lifetime: timedelta = timedelta(minutes=10),
) -> str:
    return signer.sign(kind, RELAY_ID, session, user, lifetime)


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
