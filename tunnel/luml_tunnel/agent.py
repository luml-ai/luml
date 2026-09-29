import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import (
    ConnectionClosed,
    InvalidHandshake,
    InvalidStatus,
    WebSocketException,
)
from websockets.typing import Subprotocol

from luml_tunnel.frames import (
    MAX_FRAME_BYTES,
    MAX_MESSAGE_BYTES,
    REPLACED_CLOSE_CODE,
    SUBPROTOCOL,
    Data,
    End,
    Headers,
    OpenHttp,
    OpenWebSocket,
)
from luml_tunnel.headers import (
    decode_raw_headers,
    has_body,
    header_value,
    without_hop_by_hop,
)
from luml_tunnel.protocol import (
    AgentConnection,
    PeerClosed,
    Stream,
    StreamResetError,
    pass_messages,
)

logger = logging.getLogger(__name__)

LOOPBACK_HOST = "127.0.0.1"

_SERVICE_TIMEOUT = httpx.Timeout(None, connect=10.0)


class TokenSource(Protocol):
    async def token(self) -> str: ...


class LocalService(Protocol):
    async def handle(self, stream: Stream) -> None:
        """Serve one stream the relay opened; raises StreamResetError when it is reset."""
        ...


class FixedToken:
    def __init__(self, token: str) -> None:
        self._token = token

    async def token(self) -> str:
        return self._token


class AgentRefusedError(Exception):
    pass


@dataclass(frozen=True)
class ReconnectPolicy:
    initial_delay: float = 1.0
    max_delay: float = 60.0

    def delay(self, failed_attempts: int) -> float:
        return min(self.initial_delay * 2.0**failed_attempts, self.max_delay)


class LoopbackService:
    """A service on a port of the loopback address; no other host can be reached."""

    def __init__(self, port: int, present_loopback_host: bool = False) -> None:
        self._port = port
        self._present_loopback_host = present_loopback_host
        self._transport = httpx.AsyncHTTPTransport()

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def handle(self, stream: Stream) -> None:
        opening = stream.opening
        if not opening.target.startswith("/"):
            await stream.reset("request target is not a path")
        elif isinstance(opening, OpenWebSocket):
            await self._pass_websocket(stream, opening)
        else:
            await self._forward_http(stream, opening)

    async def _forward_http(self, stream: Stream, opening: OpenHttp) -> None:
        request_complete = False

        async def request_body() -> AsyncIterator[bytes]:
            nonlocal request_complete
            while not isinstance(frame := await stream.receive(), End):
                if isinstance(frame, Data):
                    yield frame.data
            request_complete = True

        headers = self._request_headers(opening.headers)
        body = request_body()
        with_body = has_body(headers)
        if not with_body:
            async for _ in body:
                pass
        request = httpx.Request(
            opening.method,
            httpx.URL(
                scheme="http",
                host=LOOPBACK_HOST,
                port=self._port,
                raw_path=opening.target.encode("latin-1"),
            ),
            headers=headers,
            content=body if with_body else None,
            extensions={"timeout": _SERVICE_TIMEOUT.as_dict()},
        )
        await self._respond(stream, request)
        if not request_complete:
            await stream.reset("response complete")

    async def _respond(self, stream: Stream, request: httpx.Request) -> None:
        try:
            response = await self._transport.handle_async_request(request)
        except httpx.HTTPError as error:
            await _answer_unanswered(stream, error)
            return
        try:
            response_headers = without_hop_by_hop(decode_raw_headers(response.headers.raw))
            await stream.send_head(response.status_code, response_headers)
            async for chunk in response.aiter_raw():
                await stream.send_data(chunk)
            await stream.send_end()
        except httpx.HTTPError as error:
            await stream.reset(f"service failed: {error}")
        finally:
            await response.aclose()

    async def _pass_websocket(self, stream: Stream, opening: OpenWebSocket) -> None:
        headers = self._request_headers(opening.headers)
        host = header_value(headers, "host") or f"{LOOPBACK_HOST}:{self._port}"
        subprotocols = [
            Subprotocol(offered.strip())
            for offered in (header_value(headers, "sec-websocket-protocol") or "").split(",")
            if offered.strip()
        ]
        # The client builds the handshake itself, including the host from the URI; the
        # connection still goes to the loopback port given as host and port.
        handshake_headers = [
            (name, value)
            for name, value in headers
            if name.lower() != "host" and not name.lower().startswith("sec-websocket-")
        ]
        try:
            websocket = await _ConnectWithoutRedirects(
                f"ws://{host}{opening.target}",
                host=LOOPBACK_HOST,
                port=self._port,
                proxy=None,
                subprotocols=subprotocols or None,
                additional_headers=handshake_headers,
                user_agent_header=None,
                max_size=MAX_MESSAGE_BYTES,
            )
        except InvalidStatus as refusal:
            response = refusal.response
            await stream.send_head(
                response.status_code, without_hop_by_hop(list(response.headers.raw_items()))
            )
            await stream.send_data(bytes(response.body))
            await stream.send_end()
            return
        except (OSError, TimeoutError, WebSocketException, ValueError) as error:
            await _answer_unanswered(stream, error)
            return
        async with websocket:
            subprotocol = websocket.subprotocol
            accepted = [("sec-websocket-protocol", str(subprotocol))] if subprotocol else []
            await stream.send_head(101, accepted)
            await pass_messages(stream, _ServiceWebSocket(websocket))

    def _request_headers(self, headers: Headers) -> Headers:
        # Transfer-Encoding tells httpx to send the body in chunks, as the viewer did.
        forwarded = without_hop_by_hop(headers, keep=frozenset({"transfer-encoding"}))
        if not self._present_loopback_host:
            return forwarded
        without_host = [(name, value) for name, value in forwarded if name.lower() != "host"]
        return [("host", f"{LOOPBACK_HOST}:{self._port}"), *without_host]


async def _answer_unanswered(stream: Stream, error: Exception) -> None:
    logger.warning("The service did not answer: %s", error)
    await stream.send_head(502, [("content-type", "text/plain; charset=utf-8")])
    await stream.send_data(b"The service did not answer")
    await stream.send_end()


class _ConnectWithoutRedirects(connect):
    """Hands a redirect of the service to the viewer instead of following it."""

    def process_redirect(self, exc: Exception) -> Exception | str:
        return exc


class _ServiceWebSocket:
    def __init__(self, websocket: ClientConnection) -> None:
        self._websocket = websocket

    async def receive(self) -> str | bytes | PeerClosed:
        try:
            return await self._websocket.recv()
        except ConnectionClosed:
            websocket = self._websocket
            return PeerClosed(websocket.close_code or 1006, websocket.close_reason or "")

    async def send(self, data: str | bytes) -> None:
        with contextlib.suppress(ConnectionClosed):
            await self._websocket.send(data)

    async def close(self, code: int, reason: str) -> None:
        await self._websocket.close(code, reason)


class Agent:
    def __init__(
        self,
        relay_url: str,
        tokens: TokenSource,
        service: LocalService,
        reconnect: ReconnectPolicy | None = None,
    ) -> None:
        self._relay_url = relay_url
        self._tokens = tokens
        self._service = service
        self._reconnect = reconnect or ReconnectPolicy()
        self._connection: AgentConnection | None = None
        self._connected = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    async def wait_connected(self) -> None:
        await self._connected.wait()

    async def run(self) -> None:
        """Serve streams from the relay and reconnect whenever the connection ends.

        Runs until cancelled, or raises AgentRefusedError when the relay refuses the agent
        or another agent takes over the session.
        """
        failed_attempts = 0
        while True:
            if await self._connect_and_serve():
                failed_attempts = 0
            else:
                failed_attempts += 1
            delay = self._reconnect.delay(failed_attempts)
            logger.info("Reconnecting to the relay in %.1f s", delay)
            await asyncio.sleep(delay)

    async def renew_token(self, token: str) -> None:
        """Present a renewed token on the open connection, if there is one."""
        if self._connection is not None:
            with contextlib.suppress(StreamResetError):
                await self._connection.renew_token(token)

    async def _connect_and_serve(self) -> bool:
        """Serve one connection until it ends; False when it could not be opened."""
        token = await self._tokens.token()
        try:
            websocket = await connect(
                self._relay_url,
                subprotocols=[Subprotocol(SUBPROTOCOL)],
                additional_headers={"Authorization": f"Bearer {token}"},
                max_size=MAX_FRAME_BYTES,
            )
        except InvalidStatus as error:
            if 400 <= error.response.status_code < 500:
                raise AgentRefusedError(f"the relay refused the agent: {error}") from error
            logger.warning("Could not connect to the relay: %s", error)
            return False
        except (OSError, TimeoutError, InvalidHandshake) as error:
            logger.warning("Could not connect to the relay: %s", error)
            return False
        async with websocket:
            if websocket.subprotocol != SUBPROTOCOL:
                raise AgentRefusedError("the relay does not speak " + SUBPROTOCOL)
            logger.info("Connected to the relay")
            self._connection = AgentConnection(_ClientWebSocketTransport(websocket))
            self._connected.set()
            try:
                await self._serve(self._connection)
            finally:
                self._connected.clear()
                self._connection = None
        if websocket.close_code == REPLACED_CLOSE_CODE:
            raise AgentRefusedError("another agent took over the session")
        logger.warning("The connection to the relay ended")
        return True

    async def _serve(self, connection: AgentConnection) -> None:
        handlers: set[asyncio.Task[None]] = set()
        reading = asyncio.create_task(connection.run())
        try:
            while (stream := await connection.accept_stream()) is not None:
                handler = asyncio.create_task(self._handle(stream))
                handlers.add(handler)
                handler.add_done_callback(handlers.discard)
            if connection.reconnect_requested.is_set():
                logger.info("The relay asked the agent to reconnect")
            else:
                await reading
        finally:
            for handler in [reading, *handlers]:
                handler.cancel()

    async def _handle(self, stream: Stream) -> None:
        try:
            await self._service.handle(stream)
        except StreamResetError:
            pass
        except Exception:
            logger.exception("Stream %d failed", stream.id)
            with contextlib.suppress(StreamResetError):
                await stream.reset("agent error")


class _ClientWebSocketTransport:
    def __init__(self, websocket: ClientConnection) -> None:
        self._websocket = websocket

    async def send(self, message: bytes) -> None:
        try:
            await self._websocket.send(message)
        except ConnectionClosed as error:
            raise StreamResetError("relay disconnected") from error

    async def receive(self) -> bytes | None:
        while True:
            try:
                message = await self._websocket.recv()
            except ConnectionClosed:
                return None
            if isinstance(message, bytes):
                return message

    async def close(self, code: int, reason: str) -> None:
        await self._websocket.close(code, reason)
