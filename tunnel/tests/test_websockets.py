import pytest
from websockets.exceptions import ConnectionClosed, InvalidStatus

from luml_tunnel.agent import Agent
from luml_tunnel.frames import MAX_MESSAGE_BYTES, RelayLimits
from luml_tunnel.headers import TOKEN_HEADER, USER_HEADER
from luml_tunnel.relay import Relay
from luml_tunnel.signing import TokenSigner
from luml_tunnel.tokens import TokenKind
from tests.conftest import WINDOW
from tests.harness import (
    SESSION,
    SESSION_HOST,
    USER,
    EchoService,
    bound_socket,
    port_of,
    running_agent,
    sign,
    until,
    viewer,
    viewer_websocket,
)


@pytest.fixture()
def relay_limits() -> RelayLimits:
    # One stream at a time shows that a closed WebSocket gives its stream back.
    return RelayLimits(stream_window_bytes=WINDOW, max_concurrent_streams=1)


async def test_websocket_passes_through(
    connected: Agent, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer_websocket(relay_port, view_token, "/ws/echo?room=1", ["chat"]) as websocket:
        greeting = await websocket.recv()
        await websocket.send("one")
        await websocket.send(b"two")
        replies = [await websocket.recv(), await websocket.recv()]
        subprotocol = websocket.subprotocol

    assert greeting == "hello"
    assert replies == ["one", b"two"]
    assert subprotocol == "chat"
    [received] = echo.websocket_requests
    assert received.path == "/ws/echo"
    assert received.query == "room=1"
    assert received.header("host") == [SESSION_HOST]
    assert received.header(USER_HEADER) == [USER]
    assert received.header(TOKEN_HEADER) == []
    assert received.header("sec-websocket-protocol") == ["chat"]


async def test_messages_beyond_the_window_arrive_in_order(
    connected: Agent, relay_port: int, view_token: str
) -> None:
    messages = [f"{index:04d}".encode() * 1024 for index in range(64)]
    large = b"L" * (4 * WINDOW)
    async with viewer_websocket(relay_port, view_token, "/ws/echo") as websocket:
        await websocket.recv()
        for message in messages:
            await websocket.send(message)
        replies = [await websocket.recv() for _ in messages]
        await websocket.send(large)
        large_reply = await websocket.recv()

    assert replies == messages
    assert large_reply == large


async def test_viewer_close_reaches_the_service(
    connected: Agent, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer_websocket(relay_port, view_token, "/ws/echo") as websocket:
        await websocket.recv()
        await websocket.close(4100, "viewer left")

    await until(lambda: bool(echo.websocket_closes))
    assert echo.websocket_closes == [(4100, "viewer left")]


async def test_service_close_reaches_the_viewer(
    connected: Agent, relay_port: int, view_token: str
) -> None:
    async with viewer_websocket(relay_port, view_token, "/ws/echo") as websocket:
        await websocket.recv()
        await websocket.send("close")
        with pytest.raises(ConnectionClosed) as closed:
            await websocket.recv()

    assert closed.value.rcvd is not None
    assert (closed.value.rcvd.code, closed.value.rcvd.reason) == (4321, "service closed")


async def test_closed_websockets_give_their_stream_back(
    connected: Agent, relay_port: int, view_token: str
) -> None:
    for _ in range(3):
        async with viewer_websocket(relay_port, view_token, "/ws/echo") as websocket:
            await websocket.recv()
            await websocket.send("close")
            with pytest.raises(ConnectionClosed):
                await websocket.recv()

    async with viewer(relay_port, view_token) as client:
        response = await client.get("/after")

    assert response.status_code == 200


async def test_message_over_the_limit_closes_the_websocket(
    connected: Agent, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer_websocket(relay_port, view_token, "/ws/echo") as websocket:
        await websocket.recv()
        await websocket.send(b"x" * (MAX_MESSAGE_BYTES + 1))
        with pytest.raises(ConnectionClosed) as closed:
            await websocket.recv()

    assert closed.value.rcvd is not None
    assert closed.value.rcvd.code == 1009
    await until(lambda: bool(echo.websocket_closes))
    assert echo.websocket_closes[0][0] == 1009


async def test_websocket_refused_by_the_service(
    connected: Agent, relay_port: int, view_token: str
) -> None:
    with pytest.raises(InvalidStatus) as refused:
        await viewer_websocket(relay_port, view_token, "/ws/refuse")

    assert refused.value.response.status_code == 403
    assert refused.value.response.body == b"no WebSockets here"


async def test_websocket_without_an_endpoint_is_refused(
    connected: Agent, relay_port: int, view_token: str
) -> None:
    with pytest.raises(InvalidStatus) as refused:
        await viewer_websocket(relay_port, view_token, "/missing")

    assert refused.value.response.status_code == 403


@pytest.mark.parametrize("token_kind", [None, TokenKind.EXPOSE])
async def test_websocket_without_a_fitting_view_token_is_refused(
    connected: Agent,
    relay_port: int,
    signer: TokenSigner,
    echo: EchoService,
    token_kind: TokenKind | None,
) -> None:
    token = sign(signer, token_kind) if token_kind is not None else None
    with pytest.raises(InvalidStatus) as refused:
        await viewer_websocket(relay_port, token, "/ws/echo")

    assert refused.value.response.status_code == 401
    assert echo.websocket_requests == []


async def test_websocket_to_a_relay_path_is_not_forwarded(
    connected: Agent, relay_port: int, view_token: str, echo: EchoService
) -> None:
    with pytest.raises(InvalidStatus) as refused:
        await viewer_websocket(relay_port, view_token, "/.luml-tunnel/launch")

    assert refused.value.response.status_code == 404
    assert echo.websocket_requests == []


async def test_websocket_without_connected_agent(relay_port: int, view_token: str) -> None:
    with pytest.raises(InvalidStatus) as refused:
        await viewer_websocket(relay_port, view_token, "/ws/echo")

    assert refused.value.response.status_code == 502


async def test_websocket_when_the_service_does_not_answer(
    relay: Relay, relay_port: int, expose_token: str, view_token: str
) -> None:
    with bound_socket() as service_socket:
        async with running_agent(relay, relay_port, expose_token, port_of(service_socket)):
            with pytest.raises(InvalidStatus) as refused:
                await viewer_websocket(relay_port, view_token, "/ws/echo")
            connection = relay.agents.get(SESSION)
            assert connection is not None and not connection.closed

    assert refused.value.response.status_code == 502
