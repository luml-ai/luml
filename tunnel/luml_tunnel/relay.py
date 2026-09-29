import asyncio
import contextlib
import logging
import posixpath
import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import uvicorn
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from luml_tunnel.frames import (
    REPLACED_CLOSE_CODE,
    SUBPROTOCOL,
    TOKEN_EXPIRED_CLOSE_CODE,
    Data,
    End,
    Headers,
    RelayLimits,
    ResponseHead,
)
from luml_tunnel.headers import (
    TOKEN_HEADER,
    USER_HEADER,
    decode_raw_headers,
    encode_raw_headers,
    header_value,
    without_hop_by_hop,
)
from luml_tunnel.protocol import (
    PeerClosed,
    RelayConnection,
    Stream,
    StreamResetError,
    TooManyStreamsError,
    pass_messages,
)
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

_BODY_TOO_LARGE = "request body too large"
_IDLE = "stream idle"
_REFUSALS = {
    _BODY_TOO_LARGE: ("The request body is too large", 413),
    _IDLE: ("The session did not answer in time", 504),
}

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
        elif _is_relay_path(scope["path"]):
            await _respond_text(scope, receive, send, "Not found", 404)
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
        previous = self.agents.get(claims.session)
        self.agents.register(claims.session, connection)
        if previous is not None:
            logger.info("A new agent replaces the one of session %s", claims.session)
            await previous.close(REPLACED_CLOSE_CODE, "replaced by another agent")
        watching_expiry = asyncio.create_task(self._close_on_expiry(connection, claims))
        try:
            await connection.announce_limits()
            await connection.run()
        except StreamResetError:
            pass
        finally:
            watching_expiry.cancel()
            self.agents.unregister(claims.session, connection)

    async def _close_on_expiry(self, connection: RelayConnection, claims: TunnelClaims) -> None:
        """Close the connection when its token expires, unless the agent renews it first."""
        expires_at = claims.expires_at
        while True:
            remaining = (expires_at - datetime.now(UTC)).total_seconds()
            try:
                async with asyncio.timeout(max(remaining, 0)):
                    token = await connection.receive_renewed_token()
            except TimeoutError:
                await connection.close(TOKEN_EXPIRED_CLOSE_CODE, "token expired")
                return
            if token is None:
                return
            try:
                renewed = await self._verifier.verify(token, TokenKind.EXPOSE, claims.session)
            except TokenRejectedError as error:
                logger.info("Ignored a renewed token for session %s: %s", claims.session, error)
                continue
            expires_at = max(expires_at, renewed.expires_at)

    async def ask_agents_to_reconnect(self) -> None:
        for connection in self.agents.connections():
            with contextlib.suppress(StreamResetError):
                await connection.ask_to_reconnect()

    async def _serve_viewer(self, scope: Scope, receive: Receive, send: Send, session: str) -> None:
        token = _header(scope, TOKEN_HEADER)
        try:
            if token is None:
                raise TokenRejectedError("no token")
            claims = await self._verifier.verify(token, TokenKind.VIEW, session)
        except TokenRejectedError:
            await _respond_text(scope, receive, send, "Access is needed", 401)
            return
        limits = self.settings.limits
        if _declared_length(scope) > limits.max_request_body_bytes:
            await PlainTextResponse(*_REFUSALS[_BODY_TOO_LARGE])(scope, receive, send)
            return
        stream = await self._open_stream(scope, receive, send, session, claims)
        if stream is None:
            return
        if scope["type"] == "websocket":
            await _pass_websocket(stream, scope, receive, send, limits.idle_timeout_seconds)
            return
        watching_idle = asyncio.create_task(_reset_when_idle(stream, limits.idle_timeout_seconds))
        try:
            await _exchange(stream, scope, receive, send, limits.max_request_body_bytes)
        finally:
            watching_idle.cancel()

    async def _open_stream(
        self, scope: Scope, receive: Receive, send: Send, session: str, claims: TunnelClaims
    ) -> Stream | None:
        """Open a stream for the viewer's request, or answer it when that is not possible."""
        connection = self.agents.get(session)
        target, headers = _request_target(scope), _forwarded_headers(scope, claims)
        try:
            if connection is None:
                raise StreamResetError("no agent")
            if scope["type"] == "websocket":
                return await connection.open_websocket(target, headers)
            return await connection.open_http(scope["method"], target, headers)
        except TooManyStreamsError:
            await _respond_text(scope, receive, send, "The session has too many open requests", 503)
        except StreamResetError:
            await _not_connected(scope, receive, send)
        return None


async def _pass_websocket(
    stream: Stream, scope: Scope, receive: Receive, send: Send, handshake_timeout: float
) -> None:
    """Answer the viewer's handshake as the service answered the agent's, then pass messages."""
    try:
        async with asyncio.timeout(handshake_timeout):
            head = await stream.receive()
        if not isinstance(head, ResponseHead):
            raise StreamResetError("expected a response head")
    except (StreamResetError, TimeoutError) as error:
        with contextlib.suppress(StreamResetError):
            await stream.reset("handshake failed")
        if isinstance(error, TimeoutError):
            await _respond_text(scope, receive, send, *_REFUSALS[_IDLE])
        else:
            await _not_connected(scope, receive, send)
        return
    if head.status == 101:
        websocket = WebSocket(scope, receive, send)
        await websocket.accept(header_value(head.headers, "sec-websocket-protocol"))
        await pass_messages(stream, _ViewerWebSocket(websocket))
        return
    try:
        if _supports_denial_response(scope):
            await _send_response(stream, head, send, "websocket.")
        else:
            await WebSocket(scope, receive, send).close()
    except StreamResetError:
        pass
    finally:
        with contextlib.suppress(StreamResetError):
            await stream.reset("handshake refused")


async def _reset_when_idle(stream: Stream, idle_timeout: float) -> None:
    while (idle := time.monotonic() - stream.last_activity) < idle_timeout:
        await asyncio.sleep(idle_timeout - idle)
    with contextlib.suppress(StreamResetError):
        await stream.reset(_IDLE)


async def _exchange(
    stream: Stream, scope: Scope, receive: Receive, send: Send, max_body_bytes: int
) -> None:
    """Stream the viewer's request to the agent and the agent's response back."""
    request_sent = False

    async def upload() -> None:
        nonlocal request_sent
        body_bytes = 0
        try:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    await stream.reset("viewer disconnected")
                    return
                if body := message.get("body", b""):
                    body_bytes += len(body)
                    if body_bytes > max_body_bytes:
                        await stream.reset(_BODY_TOO_LARGE)
                        return
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
        response_started = True
        await _send_response(stream, head, send)
    except StreamResetError as error:
        if not response_started:
            if refusal := _REFUSALS.get(str(error)):
                await PlainTextResponse(*refusal)(scope, receive, send)
            else:
                await _not_connected(scope, receive, send)
    finally:
        uploading.cancel()
        if not request_sent:
            with contextlib.suppress(StreamResetError):
                await stream.reset("exchange ended")


async def _send_response(
    stream: Stream, head: ResponseHead, send: Send, message_prefix: str = ""
) -> None:
    """Send the response the agent streams; a WebSocket refusal uses the prefix `websocket.`."""
    await send(
        {
            "type": message_prefix + "http.response.start",
            "status": head.status,
            "headers": encode_raw_headers(head.headers),
        }
    )
    body_type = message_prefix + "http.response.body"
    while not isinstance(frame := await stream.receive(), End):
        if isinstance(frame, Data):
            await send({"type": body_type, "body": frame.data, "more_body": True})
    await send({"type": body_type, "body": b"", "more_body": False})


async def _not_connected(scope: Scope, receive: Receive, send: Send) -> None:
    await _respond_text(scope, receive, send, "The session is not connected", 502)


async def _respond_text(scope: Scope, receive: Receive, send: Send, text: str, status: int) -> None:
    """Answer with a text page; a WebSocket request gets it as the refusal of its handshake."""
    if scope["type"] == "websocket" and not _supports_denial_response(scope):
        await WebSocket(scope, receive, send).close()
    else:
        await PlainTextResponse(text, status)(scope, receive, send)


def _supports_denial_response(scope: Scope) -> bool:
    return "websocket.http.response" in scope.get("extensions", {})


class _ViewerWebSocket:
    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def receive(self) -> str | bytes | PeerClosed:
        message = await self._websocket.receive()
        if message["type"] == "websocket.disconnect":
            return PeerClosed(message.get("code", 1005), message.get("reason") or "")
        if message.get("text") is not None:
            return str(message["text"])
        return bytes(message.get("bytes") or b"")

    async def send(self, data: str | bytes) -> None:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError, OSError):
            if isinstance(data, str):
                await self._websocket.send_text(data)
            else:
                await self._websocket.send_bytes(data)

    async def close(self, code: int, reason: str) -> None:
        with contextlib.suppress(RuntimeError, OSError):
            await self._websocket.close(code, reason)


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

    async def close(self, code: int, reason: str) -> None:
        with contextlib.suppress(RuntimeError, OSError):
            await self._websocket.close(code, reason)


class RelayServer(uvicorn.Server):
    """Asks connected agents to reconnect before the server shuts down."""

    def __init__(self, relay: Relay, config: uvicorn.Config) -> None:
        super().__init__(config)
        self._relay = relay

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        await self._relay.ask_agents_to_reconnect()
        await super().shutdown(sockets)


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


def _declared_length(scope: Scope) -> int:
    length = _header(scope, "content-length")
    return int(length) if length is not None and length.isdigit() else 0


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
    scheme: str = scope.get("scheme", "http")
    headers.append(("x-forwarded-proto", {"ws": "http", "wss": "https"}.get(scheme, scheme)))
    if host := _header(scope, "host"):
        headers.append(("x-forwarded-host", host))
    headers.append((USER_HEADER, claims.user))
    return headers
