import asyncio
import logging
from collections.abc import AsyncGenerator

import pytest

from luml_tunnel import relay as relay_module
from luml_tunnel.agent import ReconnectPolicy
from luml_tunnel.cli import BASE_URL_ENV, COOKIE_SECRET_ENV, RELAY_TOKEN_ENV, main
from luml_tunnel.frames import RelayLimits
from luml_tunnel.relay import Relay, RelayServer
from tests.harness import (
    APP_URL,
    BASE_DOMAIN,
    RELAY_TOKEN,
    FakeRelayApi,
    bound_socket,
    port_of,
    serve,
    until,
)


@pytest.mark.parametrize(
    "arguments",
    [["localhost:5000"], ["10.0.0.5:5000"], ["5000", "--host", "10.0.0.5"], ["0"]],
)
def test_expose_accepts_only_a_port(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["expose", *arguments, "--relay-url", "ws://relay.example/connect", "--token", "t"])

    assert exit_info.value.code == 2


def test_expose_without_a_token_names_the_cause(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("LUML_TUNNEL_TOKEN", raising=False)

    assert main(["expose", "5000", "--relay-url", "ws://relay.example/connect"]) == 1
    assert "LUML_TUNNEL_TOKEN" in capsys.readouterr().err


@pytest.fixture()
def started(monkeypatch: pytest.MonkeyPatch) -> list[RelayServer]:
    """Servers the relay command would run; they record themselves instead of serving."""
    servers: list[RelayServer] = []

    async def record(server: RelayServer, sockets: object = None) -> None:
        servers.append(server)

    monkeypatch.setattr(RelayServer, "serve", record)
    monkeypatch.setattr(relay_module, "DESCRIPTION_RETRY", ReconnectPolicy(0.05, 0.2))
    return servers


@pytest.fixture()
async def luml_url(luml: FakeRelayApi, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[str]:
    async with serve(luml.app()) as port:
        url = f"http://127.0.0.1:{port}"
        monkeypatch.setenv(BASE_URL_ENV, url)
        monkeypatch.setenv(RELAY_TOKEN_ENV, RELAY_TOKEN)
        yield url


async def run_relay(*options: str) -> int:
    # The command runs its own event loop, so it runs beside the one of the fake LUML.
    return await asyncio.to_thread(main, ["relay", *options])


def served_relay(started: list[RelayServer]) -> Relay:
    [server] = started
    assert isinstance(server.config.app, Relay)
    return server.config.app


@pytest.mark.usefixtures("luml_url")
async def test_relay_learns_its_base_domain_and_app_origins_from_luml(
    luml: FakeRelayApi, started: list[RelayServer], monkeypatch: pytest.MonkeyPatch
) -> None:
    luml.app_origins = ["https://app.luml.ai", "http://localhost:5173", "https://bad.example/"]
    monkeypatch.setenv(COOKIE_SECRET_ENV, "shared-secret")

    assert await run_relay() == 0

    settings = served_relay(started).settings
    assert settings.base_domain == BASE_DOMAIN
    assert settings.app_origins == ("https://app.luml.ai", "http://localhost:5173")
    assert settings.app_url == APP_URL
    assert settings.cookie_secret == b"shared-secret"


@pytest.mark.usefixtures("luml_url")
@pytest.mark.parametrize(
    "app_url", ["javascript:alert(1)", 'https://app.example/"><script>', "app.example"]
)
async def test_relay_drops_an_app_address_that_is_not_a_web_address(
    luml: FakeRelayApi, started: list[RelayServer], app_url: str
) -> None:
    luml.app_url = app_url

    assert await run_relay() == 0

    assert served_relay(started).settings.app_url == ""


@pytest.mark.usefixtures("luml_url")
async def test_relay_takes_its_limits_from_options(started: list[RelayServer]) -> None:
    limits = ["--max-concurrent-streams", "5", "--max-request-body-bytes", "2048"]
    assert await run_relay(*limits, "--idle-timeout", "1.5", "--port", "9090") == 0

    [server] = started
    assert server.config.port == 9090
    assert served_relay(started).settings.limits == RelayLimits(
        max_concurrent_streams=5, max_request_body_bytes=2048, idle_timeout_seconds=1.5
    )


async def test_relay_retries_until_luml_answers(
    luml: FakeRelayApi,
    started: list[RelayServer],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="luml_tunnel.relay")
    luml_socket = bound_socket()
    monkeypatch.setenv(BASE_URL_ENV, f"http://127.0.0.1:{port_of(luml_socket)}")
    monkeypatch.setenv(RELAY_TOKEN_ENV, RELAY_TOKEN)

    running = asyncio.create_task(run_relay())
    await until(lambda: caplog.text.count("Could not fetch the relay's description") >= 3)
    assert not running.done()
    assert started == []
    async with serve(luml.app(), luml_socket):
        exit_code = await asyncio.wait_for(running, 5)

    assert exit_code == 0
    assert served_relay(started).settings.base_domain == BASE_DOMAIN
    assert "LUML cannot be reached" in caplog.text


@pytest.mark.usefixtures("luml_url")
async def test_relay_with_a_refused_token_exits_at_startup(
    luml: FakeRelayApi,
    started: list[RelayServer],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(RELAY_TOKEN_ENV, "dfsrelay_unknown")

    assert await run_relay() == 1

    assert RELAY_TOKEN_ENV in capsys.readouterr().err
    assert luml.descriptions == 1
    assert started == []


def test_relay_without_a_token_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(RELAY_TOKEN_ENV, raising=False)

    assert main(["relay"]) == 1
    assert RELAY_TOKEN_ENV in capsys.readouterr().err


@pytest.mark.parametrize(
    "option",
    [
        ["--max-concurrent-streams", "0"],
        ["--max-request-body-bytes", "-1"],
        ["--idle-timeout", "0"],
        ["--idle-timeout", "soon"],
        ["--cache-window", "0"],
    ],
)
def test_relay_refuses_options_that_are_not_positive(option: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["relay", *option])

    assert exit_info.value.code == 2


@pytest.mark.parametrize("removed", ["--base-domain", "--issuer-keys", "--app-origin"])
def test_relay_no_longer_takes_what_luml_describes(removed: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["relay", removed, "tunnel.example"])

    assert exit_info.value.code == 2


def test_dev_commands_are_gone() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["dev", "keygen"])

    assert exit_info.value.code == 2
