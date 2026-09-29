import asyncio
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest

from luml_tunnel.frames import (
    Data,
    End,
    Frame,
    OpenHttp,
    RelayLimits,
    ResponseHead,
    WebSocketClose,
    WebSocketMessage,
    decode_frame,
    encode_frame,
)
from luml_tunnel.protocol import (
    MAX_DATA_FRAME_BYTES,
    AgentConnection,
    InboundFrame,
    RelayConnection,
    Stream,
    StreamResetError,
)

WINDOW = 1024


@dataclass
class MemoryTransport:
    inbox: asyncio.Queue[bytes | None]
    outbox: asyncio.Queue[bytes | None]
    sent: list[Frame | None] = field(default_factory=list)

    async def send(self, message: bytes) -> None:
        self.sent.append(decode_frame(message))
        await self.outbox.put(message)

    async def receive(self) -> bytes | None:
        return await self.inbox.get()

    def sent_data_bytes(self, stream_id: int) -> int:
        return sum(
            len(frame.data)
            for frame in self.sent
            if isinstance(frame, Data) and frame.stream_id == stream_id
        )


@dataclass
class Tunnel:
    relay: RelayConnection
    agent: AgentConnection
    relay_transport: MemoryTransport
    agent_transport: MemoryTransport


@pytest.fixture()
async def tunnel() -> AsyncIterator[Tunnel]:
    to_agent: asyncio.Queue[bytes | None] = asyncio.Queue()
    to_relay: asyncio.Queue[bytes | None] = asyncio.Queue()
    relay_transport = MemoryTransport(inbox=to_relay, outbox=to_agent)
    agent_transport = MemoryTransport(inbox=to_agent, outbox=to_relay)
    relay = RelayConnection(relay_transport, RelayLimits(stream_window_bytes=WINDOW))
    agent = AgentConnection(agent_transport)
    await relay.announce_limits()
    tasks = [asyncio.create_task(relay.run()), asyncio.create_task(agent.run())]
    yield Tunnel(relay, agent, relay_transport, agent_transport)
    to_agent.put_nowait(None)
    to_relay.put_nowait(None)
    await asyncio.gather(*tasks)


async def _accept(agent: AgentConnection) -> Stream:
    stream = await asyncio.wait_for(agent.accept_stream(), 1)
    assert stream is not None
    return stream


async def _receive(stream: Stream) -> InboundFrame:
    return await asyncio.wait_for(stream.receive(), 1)


async def _read_body(stream: Stream) -> bytes:
    body = bytearray()
    while not isinstance(frame := await _receive(stream), End):
        assert isinstance(frame, Data)
        body += frame.data
    return bytes(body)


async def _settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


async def test_agent_learns_the_relay_limits(tunnel: Tunnel) -> None:
    await tunnel.relay.open_http("GET", "/", [])
    await _accept(tunnel.agent)

    assert tunnel.agent.limits == tunnel.relay.limits


async def test_http_request_and_response_pass_through_a_stream(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("POST", "/items?x=1", [("x-custom", "1")])
    await relay_stream.send_data(b"request body")
    await relay_stream.send_end()

    agent_stream = await _accept(tunnel.agent)
    assert agent_stream.opening == OpenHttp(
        relay_stream.id, "POST", "/items?x=1", [("x-custom", "1")]
    )
    assert await _read_body(agent_stream) == b"request body"
    await agent_stream.send_head(201, [("content-type", "text/plain")])
    await agent_stream.send_data(b"response body")
    await agent_stream.send_end()

    assert await _receive(relay_stream) == ResponseHead(
        relay_stream.id, 201, [("content-type", "text/plain")]
    )
    assert await _read_body(relay_stream) == b"response body"


async def test_websocket_messages_and_close_pass_in_both_directions(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_websocket("/socket", [])
    agent_stream = await _accept(tunnel.agent)
    await agent_stream.send_head(101, [])
    assert await _receive(relay_stream) == ResponseHead(relay_stream.id, 101, [])

    messages: list[str | bytes] = ["one", b"two", "three"]
    for message in messages:
        await relay_stream.send_message(message)
    await agent_stream.send_message("reply")

    received = [await _receive(agent_stream) for _ in range(3)]
    assert [frame.data for frame in received if isinstance(frame, WebSocketMessage)] == [
        "one",
        b"two",
        "three",
    ]
    assert await _receive(relay_stream) == WebSocketMessage(relay_stream.id, "reply")

    await relay_stream.send_close(1000, "done")
    assert await _receive(agent_stream) == WebSocketClose(agent_stream.id, 1000, "done")


async def test_sender_stops_when_the_window_is_used_up(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("GET", "/large", [])
    agent_stream = await _accept(tunnel.agent)
    await agent_stream.send_head(200, [])
    body = bytes(range(256)) * (WINDOW * 5 // 256)

    async def send_body() -> None:
        await agent_stream.send_data(body)
        await agent_stream.send_end()

    sender = asyncio.create_task(send_body())
    await _settle()

    assert not sender.done()
    assert tunnel.agent_transport.sent_data_bytes(agent_stream.id) == WINDOW

    assert isinstance(await _receive(relay_stream), ResponseHead)
    assert await _read_body(relay_stream) == body
    await asyncio.wait_for(sender, 1)


async def test_a_blocked_stream_does_not_block_another(tunnel: Tunnel) -> None:
    slow = await tunnel.relay.open_http("GET", "/large", [])
    slow_agent_side = await _accept(tunnel.agent)
    blocked_sender = asyncio.create_task(slow_agent_side.send_data(b"x" * WINDOW * 4))
    await _settle()

    fast = await tunnel.relay.open_http("GET", "/small", [])
    fast_agent_side = await _accept(tunnel.agent)
    await fast_agent_side.send_head(200, [])
    await fast_agent_side.send_data(b"page")
    await fast_agent_side.send_end()

    assert isinstance(await _receive(fast), ResponseHead)
    assert await _read_body(fast) == b"page"
    assert not blocked_sender.done()
    assert tunnel.agent_transport.sent_data_bytes(slow.id) == WINDOW
    blocked_sender.cancel()


async def test_data_frames_are_limited_in_size() -> None:
    to_agent: asyncio.Queue[bytes | None] = asyncio.Queue()
    transport = MemoryTransport(inbox=asyncio.Queue(), outbox=to_agent)
    relay = RelayConnection(transport, RelayLimits(stream_window_bytes=MAX_DATA_FRAME_BYTES * 4))
    stream = await relay.open_http("POST", "/", [])

    await stream.send_data(b"x" * (MAX_DATA_FRAME_BYTES * 2 + 1))

    sizes = [len(frame.data) for frame in transport.sent if isinstance(frame, Data)]
    assert sizes == [MAX_DATA_FRAME_BYTES, MAX_DATA_FRAME_BYTES, 1]


async def test_a_websocket_message_larger_than_the_window_is_delivered(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_websocket("/socket", [])
    agent_stream = await _accept(tunnel.agent)
    large = b"m" * (WINDOW * 3)

    await asyncio.wait_for(relay_stream.send_message(large), 1)
    second = asyncio.create_task(relay_stream.send_message("next"))
    await _settle()
    assert not second.done()

    assert await _receive(agent_stream) == WebSocketMessage(agent_stream.id, large)
    await asyncio.wait_for(second, 1)
    assert await _receive(agent_stream) == WebSocketMessage(agent_stream.id, "next")


async def test_data_beyond_the_window_resets_the_stream(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("GET", "/", [])
    agent_stream = await _accept(tunnel.agent)
    for _ in range(2):
        await tunnel.agent.send(Data(agent_stream.id, b"x" * WINDOW))

    assert isinstance(await _receive(relay_stream), Data)
    with pytest.raises(StreamResetError):
        await _receive(relay_stream)
    with pytest.raises(StreamResetError):
        await asyncio.wait_for(agent_stream.receive(), 1)


async def test_unknown_frame_type_is_ignored_and_the_stream_completes(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("GET", "/", [])
    agent_stream = await _accept(tunnel.agent)
    unknown = struct.pack(">BI", 0xEE, relay_stream.id) + b"from a later version"

    await tunnel.relay_transport.send(unknown)
    await tunnel.agent_transport.send(unknown)
    await agent_stream.send_head(200, [])
    await agent_stream.send_data(b"ok")
    await agent_stream.send_end()

    assert isinstance(await _receive(relay_stream), ResponseHead)
    assert await _read_body(relay_stream) == b"ok"
    assert not tunnel.relay.closed
    assert not tunnel.agent.closed


async def test_the_relay_ignores_a_stream_opened_by_the_agent(tunnel: Tunnel) -> None:
    await tunnel.agent.send(OpenHttp(99, "GET", "/", []))
    await tunnel.agent.send(Data(99, b"x"))
    await _settle()

    assert tunnel.relay._streams == {}


async def test_reset_reaches_the_other_side(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("GET", "/", [])
    agent_stream = await _accept(tunnel.agent)

    await relay_stream.reset("viewer left")

    with pytest.raises(StreamResetError, match="viewer left"):
        await _receive(agent_stream)
    with pytest.raises(StreamResetError):
        await agent_stream.send_data(b"late")


async def test_reset_wakes_a_sender_waiting_for_credit(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("GET", "/", [])
    agent_stream = await _accept(tunnel.agent)
    sender = asyncio.create_task(agent_stream.send_data(b"x" * WINDOW * 2))
    await _settle()

    await relay_stream.reset("viewer left")

    with pytest.raises(StreamResetError):
        await asyncio.wait_for(sender, 1)


async def test_renewed_token_reaches_the_relay(tunnel: Tunnel) -> None:
    await tunnel.agent.renew_token("new-token")

    assert await asyncio.wait_for(tunnel.relay.receive_renewed_token(), 1) == "new-token"


async def test_request_to_reconnect_reaches_the_agent(tunnel: Tunnel) -> None:
    await tunnel.relay.ask_to_reconnect()

    await asyncio.wait_for(tunnel.agent.reconnect_requested.wait(), 1)


async def test_finished_streams_are_forgotten(tunnel: Tunnel) -> None:
    relay_stream = await tunnel.relay.open_http("GET", "/", [])
    await relay_stream.send_end()
    agent_stream = await _accept(tunnel.agent)
    assert isinstance(await _receive(agent_stream), End)
    await agent_stream.send_head(204, [])
    await agent_stream.send_end()
    assert isinstance(await _receive(relay_stream), ResponseHead)
    assert isinstance(await _receive(relay_stream), End)

    assert tunnel.relay._streams == {}
    assert tunnel.agent._streams == {}


async def test_closing_the_connection_resets_open_streams() -> None:
    inbox: asyncio.Queue[bytes | None] = asyncio.Queue()
    transport = MemoryTransport(inbox=inbox, outbox=asyncio.Queue())
    agent = AgentConnection(transport)
    runner = asyncio.create_task(agent.run())
    inbox.put_nowait(encode_frame(OpenHttp(1, "GET", "/", [])))
    stream = await _accept(agent)

    inbox.put_nowait(None)
    await asyncio.wait_for(runner, 1)

    assert agent.closed
    with pytest.raises(StreamResetError):
        await _receive(stream)
    assert await agent.accept_stream() is None


async def test_opening_a_stream_on_a_closed_connection_fails() -> None:
    inbox: asyncio.Queue[bytes | None] = asyncio.Queue()
    relay = RelayConnection(MemoryTransport(inbox=inbox, outbox=asyncio.Queue()), RelayLimits())
    inbox.put_nowait(None)
    await relay.run()

    with pytest.raises(StreamResetError):
        await relay.open_http("GET", "/", [])
    assert await relay.receive_renewed_token() is None
