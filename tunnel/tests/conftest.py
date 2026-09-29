import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from luml_tunnel.agent import Agent
from luml_tunnel.frames import RelayLimits
from luml_tunnel.relay import Relay
from luml_tunnel.signing import TokenSigner, generate_private_key, key_set
from luml_tunnel.tokens import TokenKind
from tests.harness import ISSUER, EchoService, create_relay, running_agent, serve, sign

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


@pytest.fixture()
def expose_token(signer: TokenSigner) -> str:
    return sign(signer, TokenKind.EXPOSE)


@pytest.fixture()
def view_token(signer: TokenSigner) -> str:
    return sign(signer, TokenKind.VIEW)


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
def relay(key_file: Path, relay_limits: RelayLimits) -> Relay:
    return create_relay(key_file, relay_limits)


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
