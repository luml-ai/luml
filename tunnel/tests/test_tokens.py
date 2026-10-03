import asyncio
import logging
from datetime import timedelta

import httpx
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Subprotocol

from luml_tunnel.agent import Agent, AgentRefusedError, FixedToken, LoopbackService
from luml_tunnel.frames import SUBPROTOCOL, RelayLimits
from luml_tunnel.relay import TRY_AGAIN, Relay
from luml_tunnel.relay_api import RelayApi
from luml_tunnel.tokens import (
    LumlTokenVerifier,
    TokenCheckUnavailableError,
    TokenKind,
    TokenRejectedError,
)
from tests.harness import (
    BASE_DOMAIN,
    FAST_RECONNECT,
    LUML_URL,
    OTHER_RELAY_ID,
    SESSION,
    USER,
    EchoService,
    FakeClock,
    FakeRelayApi,
    Outage,
    create_relay,
    create_verifier,
    relay_url,
    running_agent,
    until,
    viewer,
    viewer_websocket,
)

WINDOW = 60.0


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def verifier(luml: FakeRelayApi, clock: FakeClock) -> LumlTokenVerifier:
    return create_verifier(luml, WINDOW, clock)


@pytest.fixture()
def relay(luml: FakeRelayApi, relay_limits: RelayLimits, verifier: LumlTokenVerifier) -> Relay:
    return create_relay(luml, relay_limits, verifier=verifier)


async def test_active_token_yields_its_claims(
    luml: FakeRelayApi, verifier: LumlTokenVerifier
) -> None:
    claims = await verifier.verify(luml.issue(TokenKind.VIEW), TokenKind.VIEW, SESSION)

    assert (claims.session, claims.kind, claims.user) == (SESSION, TokenKind.VIEW, USER)


async def test_session_is_taken_from_token_when_not_given(
    luml: FakeRelayApi, verifier: LumlTokenVerifier
) -> None:
    claims = await verifier.verify(luml.issue(TokenKind.EXPOSE), TokenKind.EXPOSE)

    assert claims.session == SESSION


async def test_verdict_is_cached_for_the_window(
    luml: FakeRelayApi, verifier: LumlTokenVerifier, clock: FakeClock
) -> None:
    token = luml.issue(TokenKind.VIEW)
    await verifier.verify(token, TokenKind.VIEW, SESSION)
    clock.now += WINDOW - 1
    await verifier.verify(token, TokenKind.VIEW, SESSION)
    assert luml.validations_of(token) == 1

    clock.now += 1
    await verifier.verify(token, TokenKind.VIEW, SESSION)

    assert luml.validations_of(token) == 2


async def test_oldest_verdicts_are_evicted_beyond_the_cache_size(
    luml: FakeRelayApi, clock: FakeClock
) -> None:
    verifier = create_verifier(luml, WINDOW, clock, max_entries=2)
    first, second, third = (luml.issue(TokenKind.VIEW) for _ in range(3))
    await verifier.verify(first, TokenKind.VIEW, SESSION)
    await verifier.verify(second, TokenKind.VIEW, SESSION)
    clock.now += WINDOW
    # Asking again about the first makes it the newest, so the second is evicted.
    await verifier.verify(first, TokenKind.VIEW, SESSION)
    await verifier.verify(third, TokenKind.VIEW, SESSION)
    assert [luml.validations_of(token) for token in (first, second, third)] == [2, 1, 1]

    await verifier.verify(first, TokenKind.VIEW, SESSION)
    await verifier.verify(third, TokenKind.VIEW, SESSION)
    await verifier.verify(second, TokenKind.VIEW, SESSION)

    assert [luml.validations_of(token) for token in (first, second, third)] == [2, 2, 1]


def test_cache_size_must_be_positive(luml: FakeRelayApi) -> None:
    with pytest.raises(ValueError, match="at least one entry"):
        create_verifier(luml, max_entries=0)


async def test_claims_are_cached_no_longer_than_the_token_lives(
    luml: FakeRelayApi, verifier: LumlTokenVerifier, clock: FakeClock
) -> None:
    token = luml.issue(TokenKind.VIEW, lifetime=timedelta(seconds=10))
    await verifier.verify(token, TokenKind.VIEW, SESSION)
    clock.now += 11

    with pytest.raises(TokenRejectedError):
        await verifier.verify(token, TokenKind.VIEW, SESSION)
    assert luml.validations_of(token) == 2


@pytest.mark.parametrize(
    "inactive",
    ["unknown", "expired", "ended session", "another relay"],
)
async def test_inactive_token_is_refused_and_the_refusal_cached(
    luml: FakeRelayApi, verifier: LumlTokenVerifier, inactive: str
) -> None:
    token = {
        "unknown": "not-issued",
        "expired": luml.issue(TokenKind.VIEW, lifetime=timedelta(seconds=-1)),
        "ended session": luml.issue(TokenKind.VIEW),
        "another relay": luml.issue(TokenKind.VIEW, relay=OTHER_RELAY_ID),
    }[inactive]
    if inactive == "ended session":
        luml.ended_sessions.add(SESSION)

    for _ in range(5):
        with pytest.raises(TokenRejectedError):
            await verifier.verify(token, TokenKind.VIEW, SESSION)

    assert luml.validations_of(token) == 1


async def test_claims_that_do_not_fit_are_refused_without_asking_again(
    luml: FakeRelayApi, verifier: LumlTokenVerifier
) -> None:
    token = luml.issue(TokenKind.VIEW)

    with pytest.raises(TokenRejectedError, match="expected a expose token"):
        await verifier.verify(token, TokenKind.EXPOSE)
    with pytest.raises(TokenRejectedError, match="another session"):
        await verifier.verify(token, TokenKind.VIEW, "other1")
    claims = await verifier.verify(token, TokenKind.VIEW, SESSION)

    assert claims.session == SESSION
    assert luml.validations_of(token) == 1


async def test_ended_session_is_refused_after_the_window(
    luml: FakeRelayApi, verifier: LumlTokenVerifier, clock: FakeClock
) -> None:
    token = luml.issue(TokenKind.VIEW)
    await verifier.verify(token, TokenKind.VIEW, SESSION)
    luml.ended_sessions.add(SESSION)
    await verifier.verify(token, TokenKind.VIEW, SESSION)
    clock.now += WINDOW

    with pytest.raises(TokenRejectedError):
        await verifier.verify(token, TokenKind.VIEW, SESSION)


@pytest.mark.parametrize("outage", list(Outage))
async def test_cached_claims_outlive_their_window_while_luml_gives_no_answer(
    luml: FakeRelayApi, verifier: LumlTokenVerifier, clock: FakeClock, outage: Outage
) -> None:
    token = luml.issue(TokenKind.VIEW, lifetime=timedelta(minutes=5))
    await verifier.verify(token, TokenKind.VIEW, SESSION)
    luml.outage = outage
    clock.now += 4 * WINDOW

    claims = await verifier.verify(token, TokenKind.VIEW, SESSION)
    assert claims.user == USER
    with pytest.raises(TokenCheckUnavailableError):
        await verifier.verify(luml.issue(TokenKind.VIEW), TokenKind.VIEW, SESSION)

    clock.now += 2 * WINDOW
    with pytest.raises(TokenCheckUnavailableError):
        await verifier.verify(token, TokenKind.VIEW, SESSION)


async def test_refusal_is_not_reused_past_its_window_while_luml_gives_no_answer(
    luml: FakeRelayApi, verifier: LumlTokenVerifier, clock: FakeClock
) -> None:
    with pytest.raises(TokenRejectedError):
        await verifier.verify("not-issued", TokenKind.VIEW, SESSION)
    luml.outage = Outage.FAILING
    clock.now += WINDOW

    with pytest.raises(TokenCheckUnavailableError):
        await verifier.verify("not-issued", TokenKind.VIEW, SESSION)


async def test_refused_relay_token_is_logged_and_reported_each_time(
    luml: FakeRelayApi,
    verifier: LumlTokenVerifier,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cached = luml.issue(TokenKind.VIEW)
    await verifier.verify(cached, TokenKind.VIEW, SESSION)
    luml.relay_tokens.clear()
    clock.now += WINDOW

    for _ in range(2):
        with pytest.raises(TokenCheckUnavailableError):
            await verifier.verify(luml.issue(TokenKind.VIEW), TokenKind.VIEW, SESSION)
    assert (await verifier.verify(cached, TokenKind.VIEW, SESSION)).user == USER

    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 3
    assert all("refused the relay token" in record.getMessage() for record in errors)
    assert verifier.problem == "LUML refuses the relay token"


async def test_a_silent_luml_is_given_up_on_after_the_timeout(luml: FakeRelayApi) -> None:
    luml.outage = Outage.SILENT
    verifier = LumlTokenVerifier(RelayApi(LUML_URL, "token", luml.transport(), timeout=0.1))

    async with asyncio.timeout(2):
        with pytest.raises(TokenCheckUnavailableError):
            await verifier.verify(luml.issue(TokenKind.VIEW), TokenKind.VIEW, SESSION)


async def test_relay_asks_luml_once_per_window(
    connected: None, luml: FakeRelayApi, relay_port: int, view_token: str, clock: FakeClock
) -> None:
    async with viewer(relay_port, view_token) as client:
        first = [await client.get("/"), await client.get("/")]
        validations_within_the_window = luml.validations_of(view_token)
        clock.now += WINDOW
        after = await client.get("/")

    assert [response.status_code for response in [*first, after]] == [200, 200, 200]
    assert validations_within_the_window == 1
    assert luml.validations_of(view_token) == 2


async def test_relay_caches_a_refused_token(
    connected: None, luml: FakeRelayApi, relay_port: int, echo: EchoService
) -> None:
    async with viewer(relay_port, "not-issued") as client:
        responses = [await client.get("/") for _ in range(5)]

    assert [response.status_code for response in responses] == [401] * 5
    assert luml.validations_of("not-issued") == 1
    assert echo.requests == []


async def test_relay_refuses_claims_that_do_not_fit_without_asking_again(
    connected: None, relay: Relay, luml: FakeRelayApi, relay_port: int, service_port: int
) -> None:
    token = luml.issue(TokenKind.VIEW)

    with pytest.raises(AgentRefusedError):
        async with running_agent(relay, relay_port, token, service_port):
            pass
    async with viewer(relay_port, token, host=f"other1.{BASE_DOMAIN}") as client:
        other_session = await client.get("/")
    async with viewer(relay_port, token) as client:
        own_session = await client.get("/")

    assert other_session.status_code == 401
    assert own_session.status_code == 200
    assert luml.validations_of(token) == 1


async def test_relay_serves_cached_viewers_and_asks_new_ones_to_try_again_while_luml_is_down(
    connected: None,
    relay: Relay,
    luml: FakeRelayApi,
    relay_port: int,
    view_token: str,
    clock: FakeClock,
) -> None:
    async with viewer(relay_port, view_token) as client:
        assert (await client.get("/")).status_code == 200
        luml.outage = Outage.UNREACHABLE
        clock.now += 3 * WINDOW
        stale = await client.get("/")
    async with viewer(relay_port, luml.issue(TokenKind.VIEW)) as client:
        unseen = await client.get("/")
    with pytest.raises(InvalidStatus) as refused_websocket:
        await viewer_websocket(relay_port, luml.issue(TokenKind.VIEW), "/ws/echo")

    assert stale.status_code == 200
    assert unseen.status_code == 503
    assert unseen.text == TRY_AGAIN
    assert refused_websocket.value.response.status_code == 503
    assert relay.agents.get(SESSION) is not None


async def test_agent_retries_while_luml_is_down_and_connects_once_it_answers(
    luml: FakeRelayApi,
    relay: Relay,
    relay_port: int,
    expose_token: str,
    service_port: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="luml_tunnel.agent")
    luml.outage = Outage.FAILING
    service = LoopbackService(service_port)
    agent = Agent(relay_url(relay_port), FixedToken(expose_token), service, FAST_RECONNECT)
    running = asyncio.create_task(agent.run())
    try:
        await until(lambda: caplog.text.count("Could not connect to the relay") >= 2)
        assert "503" in caplog.text
        assert not running.done()

        luml.outage = None
        await until(lambda: relay.agents.get(SESSION) is not None)
        assert not running.done()
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        await service.aclose()


async def test_relay_keeps_serving_when_luml_refuses_its_token(
    connected: None,
    relay: Relay,
    luml: FakeRelayApi,
    relay_port: int,
    view_token: str,
    clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with viewer(relay_port, view_token) as client:
        assert (await client.get("/")).status_code == 200
    luml.relay_tokens.clear()
    clock.now += WINDOW

    async with viewer(relay_port, view_token) as client:
        cached = await client.get("/")
    async with viewer(relay_port, luml.issue(TokenKind.VIEW)) as client:
        unseen = await client.get("/")
    with pytest.raises(InvalidStatus) as new_agent:
        await connect(
            relay_url(relay_port),
            subprotocols=[Subprotocol(SUBPROTOCOL)],
            additional_headers={"Authorization": f"Bearer {luml.issue(TokenKind.EXPOSE)}"},
        )
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{relay_port}") as client:
        health = await client.get("/health")

    assert cached.status_code == 200
    assert unseen.status_code == 503
    assert new_agent.value.response.status_code == 503
    assert relay.agents.get(SESSION) is not None
    assert health.json() == {"status": "degraded", "problem": "LUML refuses the relay token"}
    assert "refused the relay token" in caplog.text
