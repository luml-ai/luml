import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Protocol

import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.typing import Subprotocol

from luml_tunnel.frames import SUBPROTOCOL, Data, End, Headers, OpenHttp
from luml_tunnel.headers import decode_raw_headers, has_body, without_hop_by_hop
from luml_tunnel.protocol import AgentConnection, Stream, StreamResetError

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


class LoopbackService:
    """A service on a port of the loopback address; no other host can be reached."""

    def __init__(self, port: int, present_loopback_host: bool = False) -> None:
        self._port = port
        self._present_loopback_host = present_loopback_host
        self._transport = httpx.AsyncHTTPTransport()

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def handle(self, stream: Stream) -> None:
        if not isinstance(stream.opening, OpenHttp):
            await stream.reset("unsupported stream")
            return
        opening = stream.opening
        if not opening.target.startswith("/"):
            await stream.reset("request target is not a path")
            return
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
            logger.warning("The service did not answer: %s", error)
            await stream.send_head(502, [("content-type", "text/plain; charset=utf-8")])
            await stream.send_data(b"The service did not answer")
            await stream.send_end()
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

    def _request_headers(self, headers: Headers) -> Headers:
        # Transfer-Encoding tells httpx to send the body in chunks, as the viewer did.
        forwarded = without_hop_by_hop(headers, keep=frozenset({"transfer-encoding"}))
        if not self._present_loopback_host:
            return forwarded
        without_host = [(name, value) for name, value in forwarded if name.lower() != "host"]
        return [("host", f"{LOOPBACK_HOST}:{self._port}"), *without_host]


class Agent:
    def __init__(self, relay_url: str, tokens: TokenSource, service: LocalService) -> None:
        self._relay_url = relay_url
        self._tokens = tokens
        self._service = service

    async def run(self) -> None:
        """Serve streams over one connection to the relay until it closes."""
        token = await self._tokens.token()
        try:
            websocket = await connect(
                self._relay_url,
                subprotocols=[Subprotocol(SUBPROTOCOL)],
                additional_headers={"Authorization": f"Bearer {token}"},
            )
        except (OSError, InvalidHandshake) as error:
            raise AgentRefusedError(f"could not connect to the relay: {error}") from error
        async with websocket:
            if websocket.subprotocol != SUBPROTOCOL:
                raise AgentRefusedError("the relay does not speak " + SUBPROTOCOL)
            logger.info("Connected to the relay")
            await self._serve(AgentConnection(_ClientWebSocketTransport(websocket)))

    async def _serve(self, connection: AgentConnection) -> None:
        handlers: set[asyncio.Task[None]] = set()
        reading = asyncio.create_task(connection.run())
        try:
            while (stream := await connection.accept_stream()) is not None:
                handler = asyncio.create_task(self._handle(stream))
                handlers.add(handler)
                handler.add_done_callback(handlers.discard)
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
