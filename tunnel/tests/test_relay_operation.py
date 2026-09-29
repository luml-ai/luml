import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest

from luml_tunnel.agent import (
    Agent,
    AgentRefusedError,
    FixedToken,
    LoopbackService,
    ReconnectPolicy,
)
from luml_tunnel.frames import RelayLimits
from luml_tunnel.relay import Relay
from luml_tunnel.signing import TokenSigner
from luml_tunnel.tokens import TokenKind
from tests.conftest import WINDOW
from tests.harness import (
    FAST_RECONNECT,
    SESSION,
    EchoService,
    bound_socket,
    create_relay,
    port_of,
    relay_url,
    running_agent,
    serve,
    sign,
    until,
    viewer,
)

RECONNECT_MESSAGE = "Reconnecting to the relay in %.1f s"

BODY_LIMIT = 1024


def _start_agent(
    relay_port: int, token: str, service_port: int
) -> tuple[asyncio.Task[None], LoopbackService]:
    service = LoopbackService(service_port)
    agent = Agent(relay_url(relay_port), FixedToken(token), service, FAST_RECONNECT)
    return asyncio.create_task(agent.run()), service


def _reconnect_pauses(caplog: pytest.LogCaptureFixture) -> list[float]:
    pauses: list[float] = []
    for record in caplog.records:
        if record.msg == RECONNECT_MESSAGE and isinstance(record.args, tuple):
            pause = record.args[0]
            assert isinstance(pause, float)
            pauses.append(pause)
    return pauses


def test_reconnect_pauses_grow_up_to_a_maximum() -> None:
    policy = ReconnectPolicy(initial_delay=1.0, max_delay=10.0)

    assert [policy.delay(failed) for failed in range(6)] == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


async def test_second_agent_replaces_the_first(
    relay: Relay,
    relay_port: int,
    expose_token: str,
    view_token: str,
    service_port: int,
    echo: EchoService,
) -> None:
    first_running, first_service = _start_agent(relay_port, expose_token, service_port)
    await until(lambda: relay.agents.get(SESSION) is not None)
    first_connection = relay.agents.get(SESSION)
    second_echo = EchoService()
    try:
        async with (
            serve(second_echo.app()) as second_port,
            running_agent(relay, relay_port, expose_token, second_port),
            viewer(relay_port, view_token) as client,
        ):
            with pytest.raises(AgentRefusedError, match="took over"):
                await asyncio.wait_for(first_running, 5)
            response = await client.get("/after")
    finally:
        first_running.cancel()
        await first_service.aclose()

    assert first_connection is not None and first_connection.closed
    assert response.status_code == 200
    assert [request.path for request in second_echo.requests] == ["/after"]
    assert echo.requests == []


async def test_agent_reconnects_when_the_relay_restarts(
    key_file: Path,
    expose_token: str,
    view_token: str,
    service_port: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="luml_tunnel.agent")
    relay_socket = bound_socket()
    relay_port = port_of(relay_socket)
    first_relay = create_relay(key_file)
    async with serve(first_relay, relay_socket):
        running, service = _start_agent(relay_port, expose_token, service_port)
        await until(lambda: first_relay.agents.get(SESSION) is not None)
    try:
        await until(lambda: len(_reconnect_pauses(caplog)) >= 4)
        second_relay = create_relay(key_file)
        async with serve(second_relay, bound_socket(relay_port)):
            await until(lambda: second_relay.agents.get(SESSION) is not None)
            async with viewer(relay_port, view_token) as client:
                response = await client.get("/")
    finally:
        running.cancel()
        await service.aclose()

    assert response.status_code == 200
    assert "The relay asked the agent to reconnect" in caplog.text
    assert _reconnect_pauses(caplog)[:4] == [0.05, 0.1, 0.2, 0.4]


async def test_connection_closes_when_its_token_expires(
    relay: Relay, relay_port: int, signer: TokenSigner, service_port: int
) -> None:
    short_token = sign(signer, TokenKind.EXPOSE, lifetime=timedelta(seconds=2))
    running, service = _start_agent(relay_port, short_token, service_port)
    try:
        await until(lambda: relay.agents.get(SESSION) is not None)
        connection = relay.agents.get(SESSION)
        await asyncio.sleep(0.5)
        assert connection is not None and not connection.closed

        with pytest.raises(AgentRefusedError, match="refused"):
            await asyncio.wait_for(running, 5)
    finally:
        running.cancel()
        await service.aclose()

    assert connection.closed
    assert relay.agents.get(SESSION) is None


async def test_renewed_token_keeps_the_connection_open(
    relay: Relay, relay_port: int, signer: TokenSigner, service_port: int, view_token: str
) -> None:
    short_token = sign(signer, TokenKind.EXPOSE, lifetime=timedelta(seconds=2))
    async with running_agent(relay, relay_port, short_token, service_port) as agent:
        connection = relay.agents.get(SESSION)
        await agent.renew_token(sign(signer, TokenKind.EXPOSE))
        await asyncio.sleep(3)
        async with viewer(relay_port, view_token) as client:
            response = await client.get("/")

        assert connection is not None and not connection.closed
        assert relay.agents.get(SESSION) is connection
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("kind", "session"), [(TokenKind.VIEW, SESSION), (TokenKind.EXPOSE, "other1")]
)
async def test_renewed_token_that_does_not_fit_is_ignored(
    relay: Relay,
    relay_port: int,
    signer: TokenSigner,
    service_port: int,
    kind: TokenKind,
    session: str,
) -> None:
    short_token = sign(signer, TokenKind.EXPOSE, lifetime=timedelta(seconds=2))
    async with running_agent(relay, relay_port, short_token, service_port) as agent:
        connection = relay.agents.get(SESSION)
        await agent.renew_token(sign(signer, kind, session=session))

        assert connection is not None
        await until(lambda: connection.closed)


@pytest.mark.parametrize(
    "relay_limits", [RelayLimits(max_request_body_bytes=BODY_LIMIT, stream_window_bytes=WINDOW)]
)
async def test_declared_body_over_the_limit_is_refused(
    connected: Agent, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer(relay_port, view_token) as client:
        refused = await client.post("/too-large", content=b"x" * (BODY_LIMIT + 1))
        accepted = await client.post("/fits", content=b"x" * BODY_LIMIT)

    assert refused.status_code == 413
    assert accepted.status_code == 200
    assert [request.path for request in echo.requests] == ["/fits"]


@pytest.mark.parametrize(
    "relay_limits", [RelayLimits(max_request_body_bytes=BODY_LIMIT, stream_window_bytes=WINDOW)]
)
async def test_streamed_body_over_the_limit_is_refused(
    connected: Agent, relay_port: int, view_token: str
) -> None:
    async def body() -> AsyncIterator[bytes]:
        for _ in range(4):
            yield b"x" * (BODY_LIMIT // 2)

    async with viewer(relay_port, view_token) as client:
        refused = await client.post("/too-large", content=body())
        accepted = await client.get("/")

    assert refused.status_code == 413
    assert accepted.status_code == 200


@pytest.mark.parametrize(
    "relay_limits", [RelayLimits(max_concurrent_streams=1, stream_window_bytes=WINDOW)]
)
async def test_stream_over_the_concurrency_limit_is_refused(
    connected: Agent, relay: Relay, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer(relay_port, view_token) as client:
        stalled = asyncio.create_task(client.get("/stall"))
        connection = relay.agents.get(SESSION)
        assert connection is not None
        await until(lambda: len(connection._streams) == 1)

        refused = await client.get("/")
        echo.stall_released.set()
        released = await stalled
        accepted = await client.get("/")

    assert refused.status_code == 503
    assert released.text == "released"
    assert accepted.status_code == 200


@pytest.mark.parametrize(
    "relay_limits", [RelayLimits(idle_timeout_seconds=0.3, stream_window_bytes=WINDOW)]
)
async def test_idle_stream_is_closed(
    connected: Agent, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer(relay_port, view_token) as client:
        stalled = asyncio.create_task(client.get("/stall"))
        other = await client.get("/")
        idle = await stalled
        echo.stall_released.set()
        after = await client.get("/")

    assert other.status_code == 200
    assert idle.status_code == 504
    assert after.status_code == 200
