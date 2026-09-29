"""Runs the relay, the agent and a small test service in one process."""

import asyncio
import json
import socket
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route
from starlette.types import ASGIApp

from luml_tunnel.agent import Agent, FixedToken, LoopbackService
from luml_tunnel.frames import RelayLimits
from luml_tunnel.headers import TOKEN_HEADER
from luml_tunnel.relay import CONNECT_PATH, Relay, RelaySettings
from luml_tunnel.verification import IssuerKeys, JwksTokenVerifier

ISSUER = "https://luml.example"
RELAY_ID = "relay-1"
BASE_DOMAIN = "tunnel.example"
SESSION = "k3f9x2ab"
SESSION_HOST = f"{SESSION}.{BASE_DOMAIN}"
USER = "user-1"

LARGE_BODY_CHUNK = 64 * 1024
LARGE_BODY_CHUNKS = 8192


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

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                Route("/large", self._large),
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

    async def _large(self, request: Request) -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            for _ in range(LARGE_BODY_CHUNKS):
                self.large_body_produced += LARGE_BODY_CHUNK
                yield b"x" * LARGE_BODY_CHUNK

        return StreamingResponse(chunks(), media_type="application/octet-stream")


def bound_socket() -> socket.socket:
    """A socket bound to a free loopback port; connections are refused until it serves."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
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
        timeout_graceful_shutdown=1,
        proxy_headers=False,
    )
    server = uvicorn.Server(config)
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


def create_relay(key_file: Path, limits: RelayLimits | None = None) -> Relay:
    settings = RelaySettings(
        base_domain=BASE_DOMAIN,
        relay_id=RELAY_ID,
        issuer=ISSUER,
        issuer_keys=str(key_file),
        limits=limits or RelayLimits(),
    )
    verifier = JwksTokenVerifier(IssuerKeys(str(key_file)), ISSUER, RELAY_ID)
    return Relay(settings, verifier)


def relay_url(relay_port: int) -> str:
    return f"ws://127.0.0.1:{relay_port}{CONNECT_PATH}"


@asynccontextmanager
async def running_agent(
    relay: Relay,
    relay_port: int,
    token: str,
    service_port: int,
    present_loopback_host: bool = False,
) -> AsyncGenerator[asyncio.Task[None]]:
    service = LoopbackService(service_port, present_loopback_host)
    agent = Agent(relay_url(relay_port), FixedToken(token), service)
    running = asyncio.create_task(agent.run())
    try:
        await until(lambda: relay.agents.get(SESSION) is not None or running.done())
        if running.done():
            running.result()
        yield running
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        await service.aclose()


def viewer(relay_port: int, token: str | None, host: str = SESSION_HOST) -> httpx.AsyncClient:
    headers = {"host": host}
    if token is not None:
        headers[TOKEN_HEADER] = token
    return httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{relay_port}", headers=headers, timeout=5.0
    )
