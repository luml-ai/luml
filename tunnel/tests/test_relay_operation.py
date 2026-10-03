import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Subprotocol

from luml_tunnel.agent import (
    Agent,
    AgentRefusedError,
    FixedToken,
    LoopbackService,
    ReconnectPolicy,
)
from luml_tunnel.frames import SUBPROTOCOL, TOKEN_EXPIRED_CLOSE_CODE, RelayLimits
from luml_tunnel.relay import TRY_AGAIN, Relay
from luml_tunnel.tokens import TokenKind
from tests.conftest import WINDOW
from tests.harness import (
    FAST_RECONNECT,
    RELAY_ID,
    RELAY_TOKEN,
    SESSION,
    EchoService,
    FakeRelayApi,
    Outage,
    bound_socket,
    create_api,
    create_relay,
    create_verifier,
    port_of,
    relay_url,
    running_agent,
    serve,
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
    luml: FakeRelayApi,
    expose_token: str,
    view_token: str,
    service_port: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="luml_tunnel.agent")
    relay_socket = bound_socket()
    relay_port = port_of(relay_socket)
    first_relay = create_relay(luml)
    async with serve(first_relay, relay_socket):
        running, service = _start_agent(relay_port, expose_token, service_port)
        await until(lambda: first_relay.agents.get(SESSION) is not None)
    try:
        await until(lambda: len(_reconnect_pauses(caplog)) >= 4)
        second_relay = create_relay(luml)
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
    relay: Relay, relay_port: int, luml: FakeRelayApi, service_port: int
) -> None:
    short_token = luml.issue(TokenKind.EXPOSE, lifetime=timedelta(seconds=2))
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
    relay: Relay, relay_port: int, luml: FakeRelayApi, service_port: int, view_token: str
) -> None:
    short_token = luml.issue(TokenKind.EXPOSE, lifetime=timedelta(seconds=2))
    async with running_agent(relay, relay_port, short_token, service_port) as agent:
        connection = relay.agents.get(SESSION)
        await agent.renew_token(luml.issue(TokenKind.EXPOSE))
        await asyncio.sleep(3)
        async with viewer(relay_port, view_token) as client:
            response = await client.get("/")

        assert connection is not None and not connection.closed
        assert relay.agents.get(SESSION) is connection
    assert response.status_code == 200


class RecordingTokens:
    def __init__(self, token: str) -> None:
        self._token = token
        self.expired_tokens: list[str] = []

    async def token(self) -> str:
        return self._token

    def expired(self, token: str) -> None:
        self.expired_tokens.append(token)


async def test_expiry_close_names_the_last_presented_token_to_the_source(
    relay: Relay, relay_port: int, luml: FakeRelayApi, service_port: int, expose_token: str
) -> None:
    tokens = RecordingTokens(expose_token)
    service = LoopbackService(service_port)
    agent = Agent(relay_url(relay_port), tokens, service, FAST_RECONNECT)
    running = asyncio.create_task(agent.run())
    try:
        await until(lambda: relay.agents.get(SESSION) is not None)
        renewed = luml.issue(TokenKind.EXPOSE)
        await agent.renew_token(renewed)
        connection = relay.agents.get(SESSION)
        assert connection is not None
        await connection.close(TOKEN_EXPIRED_CLOSE_CODE, "token expired")

        await until(lambda: tokens.expired_tokens == [renewed])
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        await service.aclose()


async def test_other_closes_name_no_expired_token(
    relay: Relay, relay_port: int, service_port: int, expose_token: str
) -> None:
    tokens = RecordingTokens(expose_token)
    service = LoopbackService(service_port)
    agent = Agent(relay_url(relay_port), tokens, service, FAST_RECONNECT)
    running = asyncio.create_task(agent.run())
    try:
        await until(lambda: relay.agents.get(SESSION) is not None)
        first = relay.agents.get(SESSION)
        assert first is not None
        await first.close(1001, "going away")
        await until(lambda: relay.agents.get(SESSION) not in (None, first))

        assert tokens.expired_tokens == []
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        await service.aclose()


@pytest.mark.parametrize(
    ("kind", "session"), [(TokenKind.VIEW, SESSION), (TokenKind.EXPOSE, "other1")]
)
async def test_renewed_token_that_does_not_fit_is_ignored(
    relay: Relay,
    relay_port: int,
    luml: FakeRelayApi,
    service_port: int,
    kind: TokenKind,
    session: str,
) -> None:
    short_token = luml.issue(TokenKind.EXPOSE, lifetime=timedelta(seconds=2))
    async with running_agent(relay, relay_port, short_token, service_port) as agent:
        connection = relay.agents.get(SESSION)
        await agent.renew_token(luml.issue(kind, session=session))

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


async def test_agent_over_the_cap_is_refused_and_connected_agents_are_untouched(
    luml: FakeRelayApi, expose_token: str, view_token: str, service_port: int, echo: EchoService
) -> None:
    relay = create_relay(luml, max_agents=1)
    async with (
        serve(relay) as relay_port,
        running_agent(relay, relay_port, expose_token, service_port),
    ):
        with pytest.raises(InvalidStatus) as refused:
            await connect(
                relay_url(relay_port),
                subprotocols=[Subprotocol(SUBPROTOCOL)],
                additional_headers={
                    "Authorization": f"Bearer {luml.issue(TokenKind.EXPOSE, session='other1')}"
                },
            )
        replacement = luml.issue(TokenKind.EXPOSE)
        async with (
            running_agent(relay, relay_port, replacement, service_port),
            viewer(relay_port, view_token) as client,
        ):
            response = await client.get("/after")

    assert refused.value.response.status_code == 503
    assert b"cap of 1 agents" in refused.value.response.body
    assert relay.agents.get("other1") is None
    assert response.status_code == 200
    assert [request.path for request in echo.requests] == ["/after"]


async def test_renewals_beyond_the_rate_are_dropped_unchecked(
    luml: FakeRelayApi, view_token: str, service_port: int
) -> None:
    relay = create_relay(luml, max_renewals_per_minute=2)
    short_token = luml.issue(TokenKind.EXPOSE, lifetime=timedelta(seconds=1))
    checked = [luml.issue(TokenKind.EXPOSE, lifetime=timedelta(seconds=2)) for _ in range(2)]
    dropped = [luml.issue(TokenKind.EXPOSE) for _ in range(8)]
    async with (
        serve(relay) as relay_port,
        running_agent(relay, relay_port, short_token, service_port) as agent,
    ):
        connection = relay.agents.get(SESSION)
        assert connection is not None
        for token in [*checked, *dropped]:
            await agent.renew_token(token)
        await until(lambda: all(luml.validations_of(token) == 1 for token in checked))
        async with viewer(relay_port, view_token) as client:
            response = await client.get("/")
        assert not connection.closed

        await until(lambda: connection.closed)

    assert response.status_code == 200
    assert [luml.validations_of(token) for token in dropped] == [0] * 8


async def test_validations_in_flight_are_bounded_and_the_rest_try_again(
    luml: FakeRelayApi, echo: EchoService, expose_token: str, service_port: int
) -> None:
    relay = create_relay(luml, verifier=create_verifier(luml, max_in_flight=2))
    unknown_tokens = [f"unknown-{number}" for number in range(12)]

    async def request(relay_port: int, token: str) -> httpx.Response:
        async with viewer(relay_port, token) as client:
            return await client.get("/")

    async with (
        serve(relay) as relay_port,
        running_agent(relay, relay_port, expose_token, service_port),
    ):
        luml.validation_delay = 0.2
        responses = await asyncio.gather(*(request(relay_port, token) for token in unknown_tokens))

    statuses = {response.status_code for response in responses}
    assert luml.most_open_validations == 2
    assert statuses == {401, 503}
    assert {response.text for response in responses if response.status_code == 503} == {TRY_AGAIN}
    assert echo.requests == []


async def test_relay_reports_its_connected_agents(
    luml: FakeRelayApi, expose_token: str, service_port: int
) -> None:
    relay = create_relay(luml, reports_to=create_api(luml), report_interval=0.05)
    async with serve(relay) as relay_port:
        await until(lambda: luml.reports[-1:] == [0])
        async with running_agent(relay, relay_port, expose_token, service_port):
            await until(lambda: luml.reports[-1:] == [1])

    assert set(luml.reports) == {0, 1}


async def test_failed_reports_are_logged_and_retried_without_affecting_serving(
    luml: FakeRelayApi,
    expose_token: str,
    view_token: str,
    service_port: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="luml_tunnel.relay")
    relay = create_relay(luml, reports_to=create_api(luml), report_interval=0.05)
    async with (
        serve(relay) as relay_port,
        running_agent(relay, relay_port, expose_token, service_port),
        viewer(relay_port, view_token) as client,
    ):
        assert (await client.get("/")).status_code == 200
        luml.outage = Outage.FAILING
        await until(lambda: caplog.text.count("Could not report to LUML") >= 2)
        during_outage = await client.get("/")
        reports_before = len(luml.reports)
        luml.outage = None
        await until(lambda: len(luml.reports) > reports_before)
        resumed_report = luml.reports[reports_before]

    assert during_outage.status_code == 200
    assert resumed_report == 1


async def test_a_refused_report_is_an_error_and_shows_in_the_health_check(
    luml: FakeRelayApi, caplog: pytest.LogCaptureFixture
) -> None:
    relay = create_relay(luml, reports_to=create_api(luml), report_interval=0.05)
    luml.relay_tokens.clear()
    async with (
        serve(relay) as relay_port,
        httpx.AsyncClient(base_url=f"http://127.0.0.1:{relay_port}") as client,
    ):
        await until(
            lambda: caplog.text.count("refused the relay token when the relay reported") >= 2
        )
        degraded = (await client.get("/health")).json()
        luml.relay_tokens = {RELAY_TOKEN: RELAY_ID}
        # The second report starts only after the first one's answer is taken in.
        await until(lambda: len(luml.reports) >= 2)
        healthy = (await client.get("/health")).json()

    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) >= 2
    assert degraded == {"status": "degraded", "problem": "LUML refuses the relay token"}
    assert healthy == {"status": "ok"}
