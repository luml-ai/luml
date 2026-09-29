import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from luml_tunnel.signing import TokenSigner, generate_private_key, key_set
from luml_tunnel.tokens import TokenKind, TokenRejectedError
from luml_tunnel.verification import IssuerKeys, JwksTokenVerifier

ISSUER = "https://luml.example"
RELAY = "relay-1"
SESSION = "k3f9x2ab"
USER = "user-1"
LIFETIME = timedelta(minutes=10)


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
def verifier(key_file: Path) -> JwksTokenVerifier:
    return JwksTokenVerifier(IssuerKeys(str(key_file)), ISSUER, RELAY)


def _sign(
    signer: TokenSigner,
    kind: TokenKind = TokenKind.EXPOSE,
    relay: str = RELAY,
    session: str = SESSION,
) -> str:
    return signer.sign(kind, relay, session, USER, LIFETIME)


async def test_fitting_token_yields_its_claims(
    signer: TokenSigner, verifier: JwksTokenVerifier
) -> None:
    claims = await verifier.verify(_sign(signer, TokenKind.VIEW), TokenKind.VIEW, SESSION)

    assert claims.issuer == ISSUER
    assert claims.relay == RELAY
    assert claims.session == SESSION
    assert claims.kind is TokenKind.VIEW
    assert claims.user == USER
    assert claims.token_id
    assert claims.expires_at > datetime.now(UTC)


async def test_session_is_taken_from_token_when_not_given(
    signer: TokenSigner, verifier: JwksTokenVerifier
) -> None:
    claims = await verifier.verify(_sign(signer), TokenKind.EXPOSE)

    assert claims.session == SESSION


async def test_every_token_has_its_own_identifier(
    signer: TokenSigner, verifier: JwksTokenVerifier
) -> None:
    first = await verifier.verify(_sign(signer), TokenKind.EXPOSE)
    second = await verifier.verify(_sign(signer), TokenKind.EXPOSE)

    assert first.token_id != second.token_id


def _foreign_key(signer: TokenSigner) -> str:
    return _sign(TokenSigner(generate_private_key(), ISSUER))


def _other_issuer(signer: TokenSigner) -> str:
    return _sign(TokenSigner(signer.private_key, "https://other.example"))


def _other_relay(signer: TokenSigner) -> str:
    return _sign(signer, relay="relay-2")


def _other_session(signer: TokenSigner) -> str:
    return _sign(signer, session="zz99yy88")


def _expired(signer: TokenSigner) -> str:
    issued = datetime.now(UTC) - LIFETIME - timedelta(seconds=1)
    return signer.sign(TokenKind.EXPOSE, RELAY, SESSION, USER, LIFETIME, now=issued)


@pytest.mark.parametrize(
    "make_token",
    [_foreign_key, _other_issuer, _other_relay, _other_session, _expired],
)
async def test_token_that_does_not_fit_is_refused(
    signer: TokenSigner,
    verifier: JwksTokenVerifier,
    make_token: Callable[[TokenSigner], str],
) -> None:
    with pytest.raises(TokenRejectedError):
        await verifier.verify(make_token(signer), TokenKind.EXPOSE, SESSION)


@pytest.mark.parametrize("token", ["", "not-a-token", "a.b.c"])
async def test_malformed_token_is_refused(verifier: JwksTokenVerifier, token: str) -> None:
    with pytest.raises(TokenRejectedError):
        await verifier.verify(token, TokenKind.VIEW, SESSION)


async def test_token_with_another_algorithm_is_refused(verifier: JwksTokenVerifier) -> None:
    token = jwt.encode(
        {"iss": ISSUER, "aud": RELAY, "sub": USER, "sid": SESSION, "kind": "view", "jti": "x"},
        "shared-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
        headers={"kid": "any"},
    )

    with pytest.raises(TokenRejectedError):
        await verifier.verify(token, TokenKind.VIEW, SESSION)


async def test_view_token_is_not_accepted_as_expose(
    signer: TokenSigner, verifier: JwksTokenVerifier
) -> None:
    with pytest.raises(TokenRejectedError):
        await verifier.verify(_sign(signer, TokenKind.VIEW), TokenKind.EXPOSE, SESSION)


async def test_expose_token_is_not_accepted_as_view(
    signer: TokenSigner, verifier: JwksTokenVerifier
) -> None:
    with pytest.raises(TokenRejectedError):
        await verifier.verify(_sign(signer, TokenKind.EXPOSE), TokenKind.VIEW, SESSION)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _PublishedKeys:
    def __init__(self, *keys: ec.EllipticCurvePrivateKey) -> None:
        self.keys = list(keys)
        self.reads = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.reads += 1
        return httpx.Response(200, json=key_set(*(key.public_key() for key in self.keys)))


async def test_relay_learns_a_new_issuer_key(issuer_key: ec.EllipticCurvePrivateKey) -> None:
    published = _PublishedKeys(issuer_key)
    clock = _Clock()
    async with httpx.AsyncClient(transport=httpx.MockTransport(published.handle)) as client:
        keys = IssuerKeys("https://luml.example/.well-known/jwks.json", client, clock=clock)
        verifier = JwksTokenVerifier(keys, ISSUER, RELAY)
        await verifier.verify(_sign(TokenSigner(issuer_key, ISSUER)), TokenKind.EXPOSE)
        second_key = generate_private_key()
        published.keys.append(second_key)
        clock.now = 60.0

        claims = await verifier.verify(_sign(TokenSigner(second_key, ISSUER)), TokenKind.EXPOSE)

    assert claims.session == SESSION
    assert published.reads == 2


async def test_known_keys_are_served_from_cache(issuer_key: ec.EllipticCurvePrivateKey) -> None:
    published = _PublishedKeys(issuer_key)
    async with httpx.AsyncClient(transport=httpx.MockTransport(published.handle)) as client:
        verifier = JwksTokenVerifier(IssuerKeys("https://luml.example/jwks", client), ISSUER, RELAY)
        for _ in range(3):
            await verifier.verify(_sign(TokenSigner(issuer_key, ISSUER)), TokenKind.EXPOSE)

    assert published.reads == 1


async def test_unknown_keys_do_not_trigger_reads_within_the_interval(
    issuer_key: ec.EllipticCurvePrivateKey,
) -> None:
    published = _PublishedKeys(issuer_key)
    clock = _Clock()
    foreign_signer = TokenSigner(generate_private_key(), ISSUER)
    async with httpx.AsyncClient(transport=httpx.MockTransport(published.handle)) as client:
        keys = IssuerKeys("https://luml.example/jwks", client, min_refresh_interval=30, clock=clock)
        verifier = JwksTokenVerifier(keys, ISSUER, RELAY)
        for _ in range(3):
            with pytest.raises(TokenRejectedError):
                await verifier.verify(_sign(foreign_signer), TokenKind.EXPOSE)

    assert published.reads == 1


async def test_unreadable_keys_refuse_tokens(signer: TokenSigner, tmp_path: Path) -> None:
    verifier = JwksTokenVerifier(IssuerKeys(str(tmp_path / "missing.json")), ISSUER, RELAY)

    with pytest.raises(TokenRejectedError):
        await verifier.verify(_sign(signer), TokenKind.EXPOSE)


async def test_failing_key_address_refuses_tokens(signer: TokenSigner) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    async with httpx.AsyncClient(transport=transport) as client:
        verifier = JwksTokenVerifier(IssuerKeys("https://luml.example/jwks", client), ISSUER, RELAY)

        with pytest.raises(TokenRejectedError):
            await verifier.verify(_sign(signer), TokenKind.EXPOSE)
