from collections.abc import AsyncGenerator

import pytest

from luml_relay.agent import Agent
from luml_relay.frames import RelayLimits
from luml_relay.relay import Relay
from luml_relay.tokens import TokenKind
from tests.harness import EchoService, FakeRelayApi, create_relay, running_agent, serve

WINDOW = 64 * 1024


@pytest.fixture()
def luml() -> FakeRelayApi:
    return FakeRelayApi()


@pytest.fixture()
def expose_token(luml: FakeRelayApi) -> str:
    return luml.issue(TokenKind.EXPOSE)


@pytest.fixture()
def view_token(luml: FakeRelayApi) -> str:
    return luml.issue(TokenKind.VIEW)


@pytest.fixture()
def echo() -> EchoService:
    return EchoService()


@pytest.fixture()
async def service_port(echo: EchoService) -> AsyncGenerator[int]:
    async with serve(echo.app()) as port:
        yield port


@pytest.fixture()
def relay_limits() -> RelayLimits:
    return RelayLimits(stream_window_bytes=WINDOW)


@pytest.fixture()
def relay(luml: FakeRelayApi, relay_limits: RelayLimits) -> Relay:
    return create_relay(luml, relay_limits)


@pytest.fixture()
async def relay_port(relay: Relay) -> AsyncGenerator[int]:
    async with serve(relay) as port:
        yield port


@pytest.fixture()
async def connected(
    relay: Relay, relay_port: int, expose_token: str, service_port: int
) -> AsyncGenerator[Agent]:
    async with running_agent(relay, relay_port, expose_token, service_port) as agent:
        yield agent
