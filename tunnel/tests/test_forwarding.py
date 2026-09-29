import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Subprotocol

from luml_tunnel.agent import AgentRefusedError
from luml_tunnel.cli import KEY_SET_FILE, PRIVATE_KEY_FILE, TOKEN_ENV, main
from luml_tunnel.frames import RelayLimits
from luml_tunnel.headers import TOKEN_HEADER, USER_HEADER
from luml_tunnel.relay import Relay
from luml_tunnel.signing import TokenSigner, generate_private_key, key_set
from luml_tunnel.tokens import TokenKind
from tests.harness import (
    BASE_DOMAIN,
    ISSUER,
    LARGE_BODY_CHUNK,
    LARGE_BODY_CHUNKS,
    RELAY_ID,
    SESSION,
    SESSION_HOST,
    USER,
    EchoService,
    bound_socket,
    create_relay,
    port_of,
    relay_url,
    running_agent,
    serve,
    until,
    viewer,
)

WINDOW = 64 * 1024


@pytest.fixture()
def issuer_key() -> ec.EllipticCurvePrivateKey:
    return generate_private_key()


@pytest.fixture()
def signer(issuer_key: ec.EllipticCurvePrivateKey) -> TokenSigner:
    return TokenSigner(issuer_key, ISSUER)


@pytest.fixture()
def key_file(tmp_path: Path, issuer_key: ec.EllipticCurvePrivateKey) -> Path:
    path = tmp_path / "jwks.json"
    path.write_text(json.dumps(key_set(issuer_key.public_key())))
    return path


def _sign(signer: TokenSigner, kind: TokenKind, session: str = SESSION, user: str = USER) -> str:
    return signer.sign(kind, RELAY_ID, session, user, timedelta(minutes=10))


@pytest.fixture()
def expose_token(signer: TokenSigner) -> str:
    return _sign(signer, TokenKind.EXPOSE)


@pytest.fixture()
def view_token(signer: TokenSigner) -> str:
    return _sign(signer, TokenKind.VIEW)


@pytest.fixture()
def echo() -> EchoService:
    return EchoService()


@pytest.fixture()
async def service_port(echo: EchoService) -> AsyncGenerator[int]:
    async with serve(echo.app()) as port:
        yield port


@pytest.fixture()
def relay(key_file: Path) -> Relay:
    return create_relay(key_file, RelayLimits(stream_window_bytes=WINDOW))


@pytest.fixture()
async def relay_port(relay: Relay) -> AsyncGenerator[int]:
    async with serve(relay) as port:
        yield port


@pytest.fixture()
async def connected(
    relay: Relay, relay_port: int, expose_token: str, service_port: int
) -> AsyncGenerator[None]:
    async with running_agent(relay, relay_port, expose_token, service_port):
        yield


async def test_package_works_without_luml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], service_port: int
) -> None:
    assert main(["dev", "keygen", "--directory", str(tmp_path)]) == 0

    def dev_token(kind: TokenKind) -> str:
        capsys.readouterr()
        signing_options = ["--private-key", str(tmp_path / PRIVATE_KEY_FILE), "--kind", kind]
        scope_options = ["--issuer", ISSUER, "--relay", RELAY_ID, "--session", SESSION]
        assert main(["dev", "token", *signing_options, *scope_options, "--user", USER]) == 0
        return capsys.readouterr().out.strip()

    expose_token, view_token = dev_token(TokenKind.EXPOSE), dev_token(TokenKind.VIEW)
    relay = create_relay(tmp_path / KEY_SET_FILE)
    async with serve(relay) as relay_port:
        command = [sys.executable, "-m", "luml_tunnel.cli", "expose", str(service_port)]
        agent = subprocess.Popen(
            [*command, "--relay-url", relay_url(relay_port)],
            env={**os.environ, TOKEN_ENV: expose_token},
        )
        try:
            await until(lambda: relay.agents.get(SESSION) is not None, timeout=15.0)
            async with viewer(relay_port, view_token) as client:
                response = await client.get("/")
        finally:
            agent.terminate()
            agent.wait()

    assert response.status_code == 200
    assert response.json() == {"path": "/", "body": ""}


async def test_request_and_response_pass_through(
    connected: None, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer(relay_port, view_token) as client:
        response = await client.post(
            "/submit/form?a=1&b=two",
            headers={"x-custom": "value", "x-reply-status": "201"},
            content=b"request body",
        )

    [received] = echo.requests
    assert received.method == "POST"
    assert received.path == "/submit/form"
    assert received.query == "a=1&b=two"
    assert received.header("x-custom") == ["value"]
    assert received.body == b"request body"
    assert response.status_code == 201
    assert response.headers["x-service"] == "echo"
    assert response.headers.get_list("set-cookie") == [
        "first=1; Path=/; SameSite=lax",
        "second=2; Path=/; SameSite=lax",
    ]
    assert response.json() == {"path": "/submit/form", "body": "request body"}


async def test_request_body_without_length_passes_through(
    connected: None, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async def body() -> AsyncIterator[bytes]:
        for part in (b"first ", b"second ", b"third"):
            yield part

    async with viewer(relay_port, view_token) as client:
        response = await client.put("/upload", content=body())

    assert response.status_code == 200
    assert echo.requests[0].body == b"first second third"


async def test_large_body_does_not_block_other_viewers(
    connected: None, relay_port: int, view_token: str, echo: EchoService
) -> None:
    total = LARGE_BODY_CHUNK * LARGE_BODY_CHUNKS
    async with (
        viewer(relay_port, view_token) as slow_client,
        viewer(relay_port, view_token) as other_client,
        slow_client.stream("GET", "/large") as download,
    ):
        chunks = download.aiter_raw()
        await anext(chunks)

        small = await other_client.get("/small")

        async def produced_stops_growing() -> None:
            previous = -1
            while previous != echo.large_body_produced:
                previous = echo.large_body_produced
                await asyncio.sleep(0.5)

        await asyncio.wait_for(produced_stops_growing(), timeout=30.0)
        assert echo.large_body_produced < total // 4
        assert len(await anext(chunks)) > 0

    assert small.status_code == 200
    assert small.json()["path"] == "/small"


@pytest.mark.parametrize("path", ["/.luml-tunnel/launch", "/.luml-tunnel"])
async def test_relay_paths_are_not_forwarded(
    connected: None, relay_port: int, view_token: str, echo: EchoService, path: str
) -> None:
    async with viewer(relay_port, view_token) as client:
        response = await client.get(path)

    assert response.status_code == 404
    assert echo.requests == []


async def test_service_sees_public_hostname_by_default(
    connected: None, relay_port: int, view_token: str, echo: EchoService
) -> None:
    async with viewer(relay_port, view_token) as client:
        await client.get("/")

    assert echo.requests[0].header("host") == [SESSION_HOST]


async def test_service_sees_loopback_address_when_asked(
    relay: Relay,
    relay_port: int,
    expose_token: str,
    service_port: int,
    view_token: str,
    echo: EchoService,
) -> None:
    async with (
        running_agent(relay, relay_port, expose_token, service_port, present_loopback_host=True),
        viewer(relay_port, view_token) as client,
    ):
        await client.get("/")

    assert echo.requests[0].header("host") == [f"127.0.0.1:{service_port}"]


async def test_session_without_connected_agent(relay_port: int, view_token: str) -> None:
    async with viewer(relay_port, view_token) as client:
        response = await client.get("/")

    assert response.status_code == 502
    assert "not connected" in response.text


async def test_service_that_does_not_answer(
    relay: Relay, relay_port: int, expose_token: str, view_token: str, echo: EchoService
) -> None:
    service_socket = bound_socket()
    async with (
        running_agent(relay, relay_port, expose_token, port_of(service_socket)),
        viewer(relay_port, view_token) as client,
    ):
        connection = relay.agents.get(SESSION)
        unanswered = await client.get("/")
        async with serve(echo.app(), service_socket):
            answered = await client.get("/")
        assert connection is not None and not connection.closed
        assert relay.agents.get(SESSION) is connection

    assert unanswered.status_code == 502
    assert answered.status_code == 200


async def test_service_sees_the_viewer_but_not_its_credentials(
    connected: None, relay_port: int, signer: TokenSigner, echo: EchoService
) -> None:
    token = _sign(signer, TokenKind.VIEW, user="U")
    async with viewer(relay_port, token) as client:
        await client.get("/", headers={USER_HEADER: "someone-else", "x-forwarded-for": "10.0.0.1"})

    [received] = echo.requests
    assert received.header(USER_HEADER) == ["U"]
    assert received.header(TOKEN_HEADER) == []
    assert received.header("x-forwarded-for") == ["127.0.0.1"]
    assert received.header("x-forwarded-proto") == ["http"]
    assert received.header("x-forwarded-host") == [SESSION_HOST]


@pytest.mark.parametrize("token_kind", [None, TokenKind.EXPOSE, "other-session"])
async def test_viewer_without_a_fitting_view_token_is_refused(
    connected: None,
    relay_port: int,
    signer: TokenSigner,
    echo: EchoService,
    token_kind: TokenKind | str | None,
) -> None:
    token = {
        None: None,
        TokenKind.EXPOSE: _sign(signer, TokenKind.EXPOSE),
        "other-session": _sign(signer, TokenKind.VIEW, session="other1"),
    }[token_kind]
    async with viewer(relay_port, token) as client:
        response = await client.get("/")

    assert response.status_code == 401
    assert echo.requests == []


async def test_agent_with_a_view_token_is_refused(
    relay: Relay, relay_port: int, view_token: str, service_port: int
) -> None:
    with pytest.raises(AgentRefusedError):
        async with running_agent(relay, relay_port, view_token, service_port):
            pass

    assert relay.agents.get(SESSION) is None


async def test_agent_with_another_protocol_version_is_refused(
    relay_port: int, expose_token: str
) -> None:
    with pytest.raises(InvalidStatus):
        await connect(
            relay_url(relay_port),
            subprotocols=[Subprotocol("luml-tunnel.v2")],
            additional_headers={"Authorization": f"Bearer {expose_token}"},
        )


async def test_health_check_on_the_base_domain(relay_port: int) -> None:
    async with viewer(relay_port, None, host=BASE_DOMAIN) as client:
        response = await client.get("/health")

    assert response.status_code == 200
