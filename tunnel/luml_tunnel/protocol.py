import asyncio
import itertools
from typing import Protocol

from luml_tunnel.frames import (
    ConnectionFrame,
    Data,
    End,
    Frame,
    Headers,
    OpenFrame,
    OpenHttp,
    OpenWebSocket,
    Reconnect,
    RelayLimits,
    RenewToken,
    Reset,
    ResponseHead,
    WebSocketClose,
    WebSocketMessage,
    WindowUpdate,
    decode_frame,
    encode_frame,
)

MAX_DATA_FRAME_BYTES = 64 * 1024

InboundFrame = ResponseHead | Data | End | WebSocketMessage | WebSocketClose


class FrameTransport(Protocol):
    async def send(self, message: bytes) -> None: ...

    async def receive(self) -> bytes | None:
        """Return the next message, or None once the connection is closed."""
        ...


class StreamResetError(Exception):
    pass


class Stream:
    """One HTTP request with its response, or one WebSocket connection.

    Body bytes and WebSocket messages count against a credit window per direction. A
    sender waits when its credit is used up; the receiver grants credit back as the
    frames are taken with `receive`, so an unread stream holds at most one window.
    """

    def __init__(self, connection: "_Connection", opening: OpenFrame, window: int) -> None:
        self.id = opening.stream_id
        self.opening = opening
        self._connection = connection
        self._window = window
        self._send_credit = window
        self._peer_credit = window
        self._consumed_since_grant = 0
        self._credit_changed = asyncio.Event()
        self._inbound: asyncio.Queue[InboundFrame | Reset] = asyncio.Queue()
        self._reset_reason: str | None = None
        self._sent_last = False
        self._received_last = False

    async def send_head(self, status: int, headers: Headers) -> None:
        await self._send(ResponseHead(self.id, status, headers))

    async def send_data(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            await self._wait_for_credit()
            size = min(len(view), self._send_credit, MAX_DATA_FRAME_BYTES)
            self._send_credit -= size
            await self._send(Data(self.id, bytes(view[:size])))
            view = view[size:]

    async def send_end(self) -> None:
        await self._send(End(self.id))
        self._mark_sent_last()

    async def send_message(self, data: str | bytes) -> None:
        await self._wait_for_credit()
        # A WebSocket message cannot be split, so one larger than the remaining credit is
        # sent whole and drives the credit below zero until the receiver catches up.
        self._send_credit -= _credited_size(data)
        await self._send(WebSocketMessage(self.id, data))

    async def send_close(self, code: int, reason: str = "") -> None:
        await self._send(WebSocketClose(self.id, code, reason))
        self._mark_sent_last()

    async def reset(self, reason: str) -> None:
        if self._reset_reason is not None:
            return
        self._fail(reason)
        await self._connection.send(Reset(self.id, reason))

    async def receive(self) -> InboundFrame:
        frame = await self._inbound.get()
        if isinstance(frame, Reset):
            self._inbound.put_nowait(frame)
            raise StreamResetError(frame.reason)
        if isinstance(frame, Data | WebSocketMessage):
            await self._grant(_credited_size(frame.data))
        return frame

    async def _grant(self, size: int) -> None:
        self._consumed_since_grant += size
        if self._consumed_since_grant < max(self._window // 2, 1):
            return
        increment, self._consumed_since_grant = self._consumed_since_grant, 0
        self._peer_credit += increment
        if self._reset_reason is None:
            await self._connection.send(WindowUpdate(self.id, increment))

    async def _wait_for_credit(self) -> None:
        while self._send_credit <= 0 and self._reset_reason is None:
            self._credit_changed.clear()
            await self._credit_changed.wait()
        self._raise_if_reset()

    async def _send(self, frame: Frame) -> None:
        self._raise_if_reset()
        await self._connection.send(frame)

    def _raise_if_reset(self) -> None:
        if self._reset_reason is not None:
            raise StreamResetError(self._reset_reason)

    def _mark_sent_last(self) -> None:
        self._sent_last = True
        if self._received_last:
            self._connection.forget(self)

    async def _deliver(self, frame: InboundFrame) -> None:
        if isinstance(frame, Data | WebSocketMessage):
            # The sender only sends while it holds credit, and its view of the credit never
            # exceeds ours, so a frame arriving without credit breaks the protocol.
            if self._peer_credit <= 0:
                await self.reset("credit window exceeded")
                return
            self._peer_credit -= _credited_size(frame.data)
        elif isinstance(frame, End | WebSocketClose):
            self._received_last = True
            if self._sent_last:
                self._connection.forget(self)
        self._inbound.put_nowait(frame)

    def _add_credit(self, increment: int) -> None:
        self._send_credit += increment
        self._credit_changed.set()

    def _fail(self, reason: str) -> None:
        if self._reset_reason is not None:
            return
        self._reset_reason = reason
        self._credit_changed.set()
        self._inbound.put_nowait(Reset(self.id, reason))
        self._connection.forget(self)


class _Connection:
    """Multiplexes streams over one agent-relay connection; `run` reads until it closes."""

    def __init__(self, transport: FrameTransport) -> None:
        self._transport = transport
        self._send_lock = asyncio.Lock()
        self._streams: dict[int, Stream] = {}
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    async def send(self, frame: Frame) -> None:
        message = encode_frame(frame)
        async with self._send_lock:
            await self._transport.send(message)

    def forget(self, stream: Stream) -> None:
        if self._streams.get(stream.id) is stream:
            del self._streams[stream.id]

    async def run(self) -> None:
        try:
            while (message := await self._transport.receive()) is not None:
                frame = decode_frame(message)
                if frame is not None:
                    await self._dispatch(frame)
        finally:
            self._closed = True
            for stream in list(self._streams.values()):
                stream._fail("connection closed")
            self._on_closed()

    async def _dispatch(self, frame: Frame) -> None:
        match frame:
            case RelayLimits() | RenewToken() | Reconnect():
                self._on_connection_frame(frame)
            case OpenHttp() | OpenWebSocket():
                self._on_open(frame)
            case WindowUpdate(stream_id, increment):
                if stream := self._streams.get(stream_id):
                    stream._add_credit(increment)
            case Reset(stream_id, reason):
                if stream := self._streams.get(stream_id):
                    stream._fail(reason)
            case _:
                if stream := self._streams.get(frame.stream_id):
                    await stream._deliver(frame)

    def _on_connection_frame(self, frame: ConnectionFrame) -> None:
        raise NotImplementedError

    def _on_open(self, frame: OpenFrame) -> None:
        raise NotImplementedError

    def _on_closed(self) -> None:
        raise NotImplementedError


class RelayConnection(_Connection):
    def __init__(self, transport: FrameTransport, limits: RelayLimits) -> None:
        super().__init__(transport)
        self.limits = limits
        self._stream_ids = itertools.count(1)
        self._renewed_tokens: asyncio.Queue[str | None] = asyncio.Queue()

    async def announce_limits(self) -> None:
        await self.send(self.limits)

    async def ask_to_reconnect(self) -> None:
        await self.send(Reconnect())

    async def open_http(self, method: str, target: str, headers: Headers) -> Stream:
        return await self._open(OpenHttp(next(self._stream_ids), method, target, headers))

    async def open_websocket(self, target: str, headers: Headers) -> Stream:
        return await self._open(OpenWebSocket(next(self._stream_ids), target, headers))

    async def receive_renewed_token(self) -> str | None:
        """Return the next token the agent presents, or None once the connection is closed."""
        return await self._renewed_tokens.get()

    async def _open(self, opening: OpenFrame) -> Stream:
        if self._closed:
            raise StreamResetError("connection closed")
        stream = Stream(self, opening, self.limits.stream_window_bytes)
        self._streams[stream.id] = stream
        await self.send(opening)
        return stream

    def _on_connection_frame(self, frame: ConnectionFrame) -> None:
        if isinstance(frame, RenewToken):
            self._renewed_tokens.put_nowait(frame.token)

    def _on_open(self, frame: OpenFrame) -> None:
        """Only the relay opens streams, so an agent's attempt is ignored."""

    def _on_closed(self) -> None:
        self._renewed_tokens.put_nowait(None)


class AgentConnection(_Connection):
    def __init__(self, transport: FrameTransport) -> None:
        super().__init__(transport)
        self.limits = RelayLimits()
        self._accepted: asyncio.Queue[Stream | None] = asyncio.Queue()
        self._reconnect_requested = asyncio.Event()

    @property
    def reconnect_requested(self) -> asyncio.Event:
        return self._reconnect_requested

    async def renew_token(self, token: str) -> None:
        await self.send(RenewToken(token))

    async def accept_stream(self) -> Stream | None:
        """Return the next stream the relay opens, or None once the connection is closed."""
        return await self._accepted.get()

    def _on_connection_frame(self, frame: ConnectionFrame) -> None:
        if isinstance(frame, RelayLimits):
            self.limits = frame
        elif isinstance(frame, Reconnect):
            self._reconnect_requested.set()

    def _on_open(self, frame: OpenFrame) -> None:
        if frame.stream_id in self._streams:
            return
        stream = Stream(self, frame, self.limits.stream_window_bytes)
        self._streams[stream.id] = stream
        self._accepted.put_nowait(stream)

    def _on_closed(self) -> None:
        self._accepted.put_nowait(None)


def _credited_size(data: str | bytes) -> int:
    return len(data.encode()) if isinstance(data, str) else len(data)
