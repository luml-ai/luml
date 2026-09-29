import asyncio
import contextlib
import logging
import posixpath
from dataclasses import dataclass, field

from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from luml_tunnel.frames import SUBPROTOCOL, Data, End, Headers, RelayLimits, ResponseHead
from luml_tunnel.headers import (
    TOKEN_HEADER,
    USER_HEADER,
    decode_raw_headers,
    encode_raw_headers,
    without_hop_by_hop,
)
from luml_tunnel.protocol import RelayConnection, Stream, StreamResetError
from luml_tunnel.routing import (
    AgentRegistry,
    HostnameSessionResolver,
    InMemoryAgentRegistry,
    SessionResolver,
)
from luml_tunnel.tokens import TokenKind, TokenRejectedError, TokenVerifier, TunnelClaims

logger = logging.getLogger(__name__)

CONNECT_PATH = "/connect"
HEALTH_PATH = "/health"
RELAY_PATH_PREFIX = "/.luml-tunnel/"

# Set by the relay from the connection itself, so values a viewer sends are dropped.
_FORWARDING_HEADERS = frozenset(
    {"forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"}
)


@dataclass(frozen=True)
class RelaySettings:
    base_domain: str
    relay_id: str
    issuer: str
    issuer_keys: str
    limits: RelayLimits = field(default_factory=RelayLimits)


class Relay:
    """ASGI app of the relay.

    A request whose host is a session hostname belongs to that session. Every other
    host reaches the relay's own endpoints, so a health check works on any address.
    """

    def __init__(
        self,
        settings: RelaySettings,
        verifier: TokenVerifier,
        sessions: SessionResolver | None = None,
        agents: AgentRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.agents = agents or InMemoryAgentRegistry()
        self._verifier = verifier
        self._sessions = sessions or HostnameSessionResolver(settings.base_domain)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await _run_lifespan(receive, send)
            return
        host = _header(scope, "host") or ""
        session = self._sessions.session_for(host)
        if session is None:
            await self._serve_own_endpoint(scope, receive, send)
        elif scope["type"] == "websocket":
            await WebSocket(scope, receive, send).close()
        elif _is_relay_path(scope["path"]):
            await PlainTextResponse("Not found", 404)(scope, receive, send)
        else:
            await self._serve_viewer(scope, receive, send, session)

    async def _serve_own_endpoint(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket" and scope["path"] == CONNECT_PATH:
            await self._accept_agent(WebSocket(scope, receive, send))
        elif scope["type"] == "websocket":
            await WebSocket(scope, receive, send).close()
        elif scope["path"] == HEALTH_PATH:
            await JSONResponse({"status": "ok"})(scope, receive, send)
        else:
            await PlainTextResponse("Not found", 404)(scope, receive, send)

    async def _accept_agent(self, websocket: WebSocket) -> None:
        if SUBPROTOCOL not in websocket.scope.get("subprotocols", []):
            await websocket.close(1002)
            return
        scheme, _, token = (websocket.headers.get("authorization") or "").partition(" ")
        try:
            if scheme.lower() != "bearer":
                raise TokenRejectedError("no bearer token")
            claims = await self._verifier.verify(token, TokenKind.EXPOSE)
        except TokenRejectedError as error:
            logger.info("Refused an agent: %s", error)
            await websocket.close(1008)
            return
        await websocket.accept(SUBPROTOCOL)
        connection = RelayConnection(_AsgiWebSocketTransport(websocket), self.settings.limits)
        self.agents.register(claims.session, connection)
        try:
            await connection.announce_limits()
            await connection.run()
        except StreamResetError:
            pass
        finally:
            self.agents.unregister(claims.session, connection)

    async def _serve_viewer(self, scope: Scope, receive: Receive, send: Send, session: str) -> None:
        token = _header(scope, TOKEN_HEADER)
        try:
            if token is None:
                raise TokenRejectedError("no token")
            claims = await self._verifier.verify(token, TokenKind.VIEW, session)
        except TokenRejectedError:
            await PlainTextResponse("Access is needed", 401)(scope, receive, send)
            return
        connection = self.agents.get(session)
        try:
            if connection is None:
                raise StreamResetError("no agent")
            stream = await connection.open_http(
                scope["method"], _request_target(scope), _forwarded_headers(scope, claims)
            )
        except StreamResetError:
            await _not_connected(scope, receive, send)
            return
        await _exchange(stream, scope, receive, send)


async def _exchange(stream: Stream, scope: Scope, receive: Receive, send: Send) -> None:
    """Stream the viewer's request to the agent and the agent's response back."""
    request_sent = False

    async def upload() -> None:
        nonlocal request_sent
        try:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    await stream.reset("viewer disconnected")
                    return
                if body := message.get("body", b""):
                    await stream.send_data(body)
                if not message.get("more_body", False):
                    break
            await stream.send_end()
            request_sent = True
            while (await receive())["type"] != "http.disconnect":
                pass
            await stream.reset("viewer disconnected")
        except StreamResetError:
            pass

    uploading = asyncio.create_task(upload())
    response_started = False
    try:
        head = await stream.receive()
        if not isinstance(head, ResponseHead):
            raise StreamResetError("expected a response head")
        await send(
            {
                "type": "http.response.start",
                "status": head.status,
                "headers": encode_raw_headers(head.headers),
            }
        )
        response_started = True
        while not isinstance(frame := await stream.receive(), End):
            if isinstance(frame, Data):
                await send({"type": "http.response.body", "body": frame.data, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
    except StreamResetError:
        if not response_started:
            await _not_connected(scope, receive, send)
    finally:
        uploading.cancel()
        if not request_sent:
            with contextlib.suppress(StreamResetError):
                await stream.reset("exchange ended")


async def _not_connected(scope: Scope, receive: Receive, send: Send) -> None:
    await PlainTextResponse("The session is not connected", 502)(scope, receive, send)


class _AsgiWebSocketTransport:
    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def send(self, message: bytes) -> None:
        try:
            await self._websocket.send_bytes(message)
        except (WebSocketDisconnect, RuntimeError, OSError) as error:
            raise StreamResetError("agent disconnected") from error

    async def receive(self) -> bytes | None:
        while True:
            message = await self._websocket.receive()
            if message["type"] == "websocket.disconnect":
                return None
            if message.get("bytes") is not None:
                return bytes(message["bytes"])


async def _run_lifespan(receive: Receive, send: Send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def _header(scope: Scope, name: str) -> str | None:
    encoded = name.encode("latin-1")
    for raw_name, raw_value in scope["headers"]:
        if raw_name.lower() == encoded:
            return str(raw_value.decode("latin-1"))
    return None


def _is_relay_path(path: str) -> bool:
    # Dot segments are resolved first, because the service may resolve them too.
    normalized = posixpath.normpath("/" + path.lstrip("/"))
    return (normalized + "/").startswith(RELAY_PATH_PREFIX)


def _request_target(scope: Scope) -> str:
    raw_path: bytes = scope.get("raw_path") or scope["path"].encode()
    target = raw_path.decode("latin-1")
    if query := scope.get("query_string", b""):
        target += "?" + query.decode("latin-1")
    return target


def _forwarded_headers(scope: Scope, claims: TunnelClaims) -> Headers:
    # Transfer-Encoding is kept so the agent knows a body follows without a length.
    headers = without_hop_by_hop(
        decode_raw_headers(scope["headers"]), keep=frozenset({"transfer-encoding"})
    )
    removed = _FORWARDING_HEADERS | {TOKEN_HEADER, USER_HEADER}
    headers = [(name, value) for name, value in headers if name.lower() not in removed]
    client = scope.get("client")
    if client:
        headers.append(("x-forwarded-for", client[0]))
    headers.append(("x-forwarded-proto", scope.get("scheme", "http")))
    if host := _header(scope, "host"):
        headers.append(("x-forwarded-host", host))
    headers.append((USER_HEADER, claims.user))
    return headers
