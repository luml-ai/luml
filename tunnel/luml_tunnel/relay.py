import asyncio
import contextlib
import logging
import posixpath
import socket
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import uvicorn
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from starlette.types import Message, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from luml_tunnel.agent import ReconnectPolicy
from luml_tunnel.cookies import COOKIE_NAME, ViewerCookie, ViewerCookies
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
    cookie_value,
    decode_raw_headers,
    encode_raw_headers,
    header_value,
    rewrite_response_headers,
    without_cookie,
    without_hop_by_hop,
)
from luml_tunnel.pages import access_needed_page, not_connected_page
from luml_tunnel.protocol import (
    MAX_RENEWALS_PER_MINUTE,
    PeerClosed,
    RelayConnection,
    Stream,
    StreamResetError,
    TooManyStreamsError,
    pass_messages,
)
from luml_tunnel.relay_api import (
    REPORT_INTERVAL_SECONDS,
    LumlUnavailableError,
    RelayApi,
    RelayDescription,
    RelayTokenRefusedError,
)
from luml_tunnel.routing import (
    MAX_AGENTS,
    AgentRegistry,
    HostnameSessionResolver,
    InMemoryAgentRegistry,
    SessionResolver,
)
from luml_tunnel.tokens import (
    TokenCheckUnavailableError,
    TokenKind,
    TokenRejectedError,
    TokenVerifier,
    TunnelClaims,
)

logger = logging.getLogger(__name__)

CONNECT_PATH = "/connect"
HEALTH_PATH = "/health"
RELAY_PATH_PREFIX = "/.luml-tunnel/"
LAUNCH_PATH = RELAY_PATH_PREFIX + "launch"
LAUNCH_TOKEN_PARAMETER = "token"

TRY_AGAIN = "LUML cannot be asked about access right now; try again in a moment"
DESCRIPTION_RETRY = ReconnectPolicy(initial_delay=1.0, max_delay=30.0)
# What this relay can do, reported to LUML, which uses a relay only for what it declares.
CAPABILITIES: dict[str, dict[str, object]] = {"sessions": {"version": 1, "api_versions": [1]}}

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
    limits: RelayLimits = field(default_factory=RelayLimits)
    app_origins: tuple[str, ...] = ()
    app_url: str = ""
    cookie_secret: bytes | None = None
    max_agents: int = MAX_AGENTS
    max_renewals_per_minute: int = MAX_RENEWALS_PER_MINUTE
    report_interval: float = REPORT_INTERVAL_SECONDS


class Relay:
    """ASGI app of the relay.

    A request whose host is a session hostname belongs to that session. Every other
    host reaches the relay's own endpoints, so a health check works on any address.
    With an API to report to, the relay reports its connected agents while it runs.
    """

    def __init__(
        self,
        settings: RelaySettings,
        verifier: TokenVerifier,
        sessions: SessionResolver | None = None,
        agents: AgentRegistry | None = None,
        cookies: ViewerCookies | None = None,
        reports_to: RelayApi | None = None,
    ) -> None:
        self.settings = settings
        self.agents = agents or InMemoryAgentRegistry()
        self._verifier = verifier
        self._sessions = sessions or HostnameSessionResolver(settings.base_domain)
        self._cookies = cookies or ViewerCookies(settings.cookie_secret)
        self._reports_to = reports_to
        self._report_refused = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._run_lifespan(receive, send)
            return
        host = _header(scope, "host") or ""
        session = self._sessions.session_for(host)
        if session is None:
            await self._serve_own_endpoint(scope, receive, send)
            return
        app_origins = self.settings.app_origins
        send = _with_response_headers(send, lambda h: rewrite_response_headers(h, app_origins))
        if scope["type"] == "http" and scope["path"] == LAUNCH_PATH:
            await self._launch(scope, receive, send, session)
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
            problem = self._verifier.problem or (
                "LUML refuses the relay token" if self._report_refused else None
            )
            health = (
                {"status": "ok"} if problem is None else {"status": "degraded", "problem": problem}
            )
            await JSONResponse(health)(scope, receive, send)
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
        except TokenCheckUnavailableError:
            # A 5xx answer, unlike a refusal, makes the agent retry.
            await _respond_text(websocket.scope, websocket.receive, websocket.send, TRY_AGAIN, 503)
            return
        max_agents = self.settings.max_agents
        if self.agents.get(claims.session) is None and len(self.agents.connections()) >= max_agents:
            logger.warning("Refused an agent: the relay serves its cap of %d agents", max_agents)
            refusal = f"The relay serves its cap of {max_agents} agents; try again later"
            await _respond_text(websocket.scope, websocket.receive, websocket.send, refusal, 503)
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
        """Close the connection when its token expires, unless the agent renews it first.

        Renewals beyond the rate are dropped unchecked, so an agent cannot make the relay
        ask LUML at will.
        """
        expires_at = claims.expires_at
        recent_renewals: deque[float] = deque()
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
            now = time.monotonic()
            while recent_renewals and recent_renewals[0] <= now - 60:
                recent_renewals.popleft()
            if len(recent_renewals) >= self.settings.max_renewals_per_minute:
                logger.info("Dropped a renewed token for session %s over the rate", claims.session)
                continue
            recent_renewals.append(now)
            try:
                renewed = await self._verifier.verify(token, TokenKind.EXPOSE, claims.session)
            except (TokenRejectedError, TokenCheckUnavailableError) as error:
                logger.info("Ignored a renewed token for session %s: %s", claims.session, error)
                continue
            expires_at = max(expires_at, renewed.expires_at)

    async def _run_lifespan(self, receive: Receive, send: Send) -> None:
        reporting: asyncio.Task[None] | None = None
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                if self._reports_to is not None:
                    reporting = asyncio.create_task(self._report_periodically(self._reports_to))
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if reporting is not None:
                    reporting.cancel()
                    await asyncio.gather(reporting, return_exceptions=True)
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _report_periodically(self, api: RelayApi) -> None:
        interval = self.settings.report_interval
        while True:
            try:
                await api.report(len(self.agents.connections()), CAPABILITIES)
            except RelayTokenRefusedError as error:
                self._report_refused = True
                logger.error("LUML refused the relay token when the relay reported: %s", error)
            except LumlUnavailableError as error:
                logger.warning("Could not report to LUML, retrying in %g s: %s", interval, error)
            else:
                self._report_refused = False
            await asyncio.sleep(interval)

    async def ask_agents_to_reconnect(self) -> None:
        for connection in self.agents.connections():
            with contextlib.suppress(StreamResetError):
                await connection.ask_to_reconnect()

    async def _launch(self, scope: Scope, receive: Receive, send: Send, session: str) -> None:
        """Exchange a view token, which LUML accepts once, for the relay's cookie."""
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        tokens = query.get(LAUNCH_TOKEN_PARAMETER, [])
        try:
            if scope["method"] != "GET" or len(tokens) != 1:
                raise TokenRejectedError("no launch token")
            launched = await self._verifier.launch(tokens[0], session)
        except TokenRejectedError as error:
            logger.info("Refused a launch of session %s: %s", session, error)
            await self._access_needed(scope, receive, send, session)
            return
        except TokenCheckUnavailableError:
            await _respond_text(scope, receive, send, TRY_AGAIN, 503)
            return
        cookie = self._cookies.issue(session, launched.claims.user, launched.grant)
        response = RedirectResponse(_local_destination(launched.destination), 303)
        response.headers.append("set-cookie", self._cookies.set_cookie_header(cookie))
        # The address carries the token, so it must not be cached or sent on as a referrer.
        response.headers["cache-control"] = "no-store"
        response.headers["referrer-policy"] = "no-referrer"
        await response(scope, receive, send)

    async def _authorize(self, scope: Scope, session: str) -> tuple[str, ViewerCookie | None]:
        """Return the viewer's user and, when access is by cookie, the renewed cookie.

        The header carries only `view` tokens and the cookie only grants. Raises
        TokenRejectedError without valid access and _CrossSiteError for a request with a
        cookie that another site started.
        """
        token = _header(scope, TOKEN_HEADER)
        if token is not None:
            claims = await self._verifier.verify(token, TokenKind.VIEW, session)
            return claims.user, None
        value = cookie_value(decode_raw_headers(scope["headers"]), COOKIE_NAME)
        cookie = self._cookies.renew(value, session) if value is not None else None
        if cookie is None:
            raise TokenRejectedError("no token and no valid cookie")
        if not _started_by_own_pages_or_navigation(scope):
            raise _CrossSiteError
        grant = await self._verifier.check_grant(cookie.grant, session)
        if grant.user != cookie.user:
            raise TokenRejectedError("the grant is another user's")
        return cookie.user, cookie

    async def _access_needed(
        self, scope: Scope, receive: Receive, send: Send, session: str
    ) -> None:
        if scope["type"] == "http" and _is_navigation(scope):
            page = access_needed_page(session, self.settings.app_origins, self.settings.app_url)
            await HTMLResponse(page, 401, headers={"cache-control": "no-store"})(
                scope, receive, send
            )
        else:
            await _respond_text(scope, receive, send, "Access is needed", 401)

    async def _serve_viewer(self, scope: Scope, receive: Receive, send: Send, session: str) -> None:
        try:
            user, cookie = await self._authorize(scope, session)
        except TokenRejectedError:
            await self._access_needed(scope, receive, send, session)
            return
        except _CrossSiteError:
            await _respond_text(scope, receive, send, "Requests from other sites are refused", 403)
            return
        except TokenCheckUnavailableError:
            await _respond_text(scope, receive, send, TRY_AGAIN, 503)
            return
        if cookie is not None:
            renewal = self._cookies.set_cookie_header(cookie)
            send = _with_response_headers(send, lambda h: [*h, ("set-cookie", renewal)])
        limits = self.settings.limits
        if _declared_length(scope) > limits.max_request_body_bytes:
            await PlainTextResponse(*_REFUSALS[_BODY_TOO_LARGE])(scope, receive, send)
            return
        stream = await self._open_stream(scope, receive, send, session, user)
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
        self, scope: Scope, receive: Receive, send: Send, session: str, user: str
    ) -> Stream | None:
        """Open a stream for the viewer's request, or answer it when that is not possible."""
        connection = self.agents.get(session)
        target, headers = _request_target(scope), _forwarded_headers(scope, user)
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


class _CrossSiteError(Exception):
    pass


async def _not_connected(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "websocket":
        await _respond_text(scope, receive, send, "The session is not connected", 502)
    else:
        await HTMLResponse(not_connected_page(), 502)(scope, receive, send)


def _with_response_headers(send: Send, adjust: Callable[[Headers], Headers]) -> Send:
    """Wrap `send` so the headers of every response pass through `adjust`."""

    async def adjusted_send(message: Message) -> None:
        if message["type"] in ("http.response.start", "websocket.http.response.start"):
            headers = adjust(decode_raw_headers(message.get("headers", [])))
            message = {**message, "headers": encode_raw_headers(headers)}
        await send(message)

    return adjusted_send


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


async def describe_relay(api: RelayApi) -> RelayDescription:
    """Fetch the relay's description from LUML, retrying while LUML gives no answer.

    Raises RelayTokenRefusedError at once, because retrying cannot help a refused token.
    """
    failed_attempts = 0
    while True:
        try:
            return await api.describe()
        except RelayTokenRefusedError:
            raise
        except LumlUnavailableError as error:
            delay = DESCRIPTION_RETRY.delay(failed_attempts)
            logger.warning(
                "Could not fetch the relay's description, trying again in %.1f s: %s", delay, error
            )
            failed_attempts += 1
            await asyncio.sleep(delay)


class RelayServer(uvicorn.Server):
    """Asks connected agents to reconnect before the server shuts down."""

    def __init__(self, relay: Relay, config: uvicorn.Config) -> None:
        super().__init__(config)
        self._relay = relay

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        await self._relay.ask_agents_to_reconnect()
        await super().shutdown(sockets)


def _header(scope: Scope, name: str) -> str | None:
    encoded = name.encode("latin-1")
    for raw_name, raw_value in scope["headers"]:
        if raw_name.lower() == encoded:
            return str(raw_value.decode("latin-1"))
    return None


def _declared_length(scope: Scope) -> int:
    length = _header(scope, "content-length")
    return int(length) if length is not None and length.isdigit() else 0


def _is_navigation(scope: Scope) -> bool:
    mode = _header(scope, "sec-fetch-mode")
    if mode is not None:
        return mode == "navigate"
    return scope.get("method") == "GET" and "text/html" in (_header(scope, "accept") or "")


def _started_by_own_pages_or_navigation(scope: Scope) -> bool:
    """Whether a request that carries the cookie comes from the session's own pages or is a
    plain navigation; browsers without Fetch Metadata are judged by their Origin header."""
    site = _header(scope, "sec-fetch-site")
    if site is None:
        origin = _header(scope, "origin")
        return origin is None or urlsplit(origin).netloc == _header(scope, "host")
    if site in ("same-origin", "none"):
        return True
    return _header(scope, "sec-fetch-mode") == "navigate" and scope.get("method") in (
        "GET",
        "HEAD",
    )


def _local_destination(destination: str | None) -> str:
    # LUML accepts only such paths; checked again so a redirect never leaves the hostname.
    if destination is None or not destination.startswith("/") or destination.startswith("//"):
        return "/"
    return destination


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


def _forwarded_headers(scope: Scope, user: str) -> Headers:
    # Transfer-Encoding is kept so the agent knows a body follows without a length.
    headers = without_hop_by_hop(
        decode_raw_headers(scope["headers"]), keep=frozenset({"transfer-encoding"})
    )
    headers = without_cookie(headers, COOKIE_NAME)
    removed = _FORWARDING_HEADERS | {TOKEN_HEADER, USER_HEADER}
    headers = [(name, value) for name, value in headers if name.lower() not in removed]
    client = scope.get("client")
    if client:
        headers.append(("x-forwarded-for", client[0]))
    scheme: str = scope.get("scheme", "http")
    headers.append(("x-forwarded-proto", {"ws": "http", "wss": "https"}.get(scheme, scheme)))
    if host := _header(scope, "host"):
        headers.append(("x-forwarded-host", host))
    headers.append((USER_HEADER, user))
    return headers
