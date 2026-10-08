import json
from collections.abc import AsyncIterator
from time import time
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from luml.clients.oauth_providers import OAuthGoogleProvider, OAuthMicrosoftProvider
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError
from luml.schemas.user import AuthProvider, User
from luml.settings import config

from tests.support.mocks import mock_collaborators

TENANT_ID = "11111111-2222-3333-4444-555555555555"
OTHER_TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
ISSUER_TEMPLATE = "https://login.microsoftonline.com/{tenantid}/v2.0"
CLIENT_ID = "oauth-test-client"
KEY_ID = "oauth-test-key"


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def microsoft_claims() -> dict[str, Any]:
    return {
        "iss": ISSUER,
        "tid": TENANT_ID,
        "aud": CLIENT_ID,
        "sub": "test-subject",
        "iat": int(time()),
        "nbf": int(time()) - 1,
        "exp": int(time()) + 3600,
        "email": "victim@example.com",
        "name": "Test User",
        "xms_edov": True,
    }


@pytest.fixture
def signing_jwk(signing_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    key: dict[str, Any] = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key())
    )
    key.update(kid=KEY_ID, use="sig", issuer=ISSUER_TEMPLATE)
    return key


@pytest.fixture
async def microsoft_client(
    monkeypatch: pytest.MonkeyPatch,
    signing_jwk: dict[str, Any],
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(config, "MICROSOFT_TENANT", "common")
    monkeypatch.setattr(config, "MICROSOFT_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(
        config, "MICROSOFT_AUTH_URL", "https://login.microsoftonline.com"
    )

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER_TEMPLATE,
                    "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
                },
            )
        if request.url.path.endswith("/discovery/v2.0/keys"):
            return httpx.Response(200, json={"keys": [signing_jwk]})
        if request.url.host == "graph.microsoft.com":
            return httpx.Response(
                200,
                json={
                    "mail": None,
                    "otherMails": ["victim@example.com"],
                    "userPrincipalName": "attacker_ext#EXT#@evil.onmicrosoft.com",
                    "displayName": "Attacker",
                },
            )
        pytest.fail(f"unexpected provider request: {request.url.host}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        yield client


@pytest.mark.parametrize("verified_email", [True, False, None, "true", 1])
async def test_google_requires_boolean_verified_email(verified_email: object) -> None:
    payload = {
        "email": "victim@example.com",
        "name": "Test User",
        "verified_email": verified_email,
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        userinfo = await OAuthGoogleProvider.get_user_info(client, "access-token")

    assert userinfo.email_verified is (verified_email is True)


async def test_microsoft_exchanges_code_for_id_token() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"access_token": "graph-token", "id_token": "identity-token"}
            )
        )
    ) as client:
        token = await OAuthMicrosoftProvider.exchange_code_for_token(client, "code")

    assert token == "identity-token"


@pytest.mark.parametrize("payload", [{}, {"access_token": "graph-token"}])
async def test_microsoft_rejects_missing_id_token(payload: dict[str, str]) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(AuthError, match="ID token"):
            await OAuthMicrosoftProvider.exchange_code_for_token(client, "code")


@pytest.mark.parametrize("verification_claim", ["xms_edov", "email_verified"])
async def test_microsoft_accepts_signed_verified_email(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    verification_claim: str,
) -> None:
    microsoft_claims.pop("xms_edov")
    microsoft_claims[verification_claim] = True
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    userinfo = await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)

    assert userinfo.email == "victim@example.com"
    assert userinfo.full_name == "Test User"
    assert userinfo.email_verified is True


@pytest.mark.parametrize("verified", [False, None, "true", 1])
async def test_microsoft_does_not_verify_email_from_graph_profile(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    verified: object,
) -> None:
    microsoft_claims["xms_edov"] = verified
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    userinfo = await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)

    assert userinfo.email_verified is False


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("aud", "another-client"),
        ("iss", "https://attacker.example.com"),
        ("iss", f"https://login.microsoftonline.com/{OTHER_TENANT_ID}/v2.0"),
        ("tid", OTHER_TENANT_ID),
        ("tid", "../../attacker"),
        ("exp", 1),
        ("nbf", 9999999999),
    ],
)
async def test_microsoft_rejects_invalid_identity_claims(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    claim: str,
    value: object,
) -> None:
    microsoft_claims[claim] = value
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


@pytest.mark.parametrize("claim", ["aud", "iss", "tid", "exp", "sub", "iat"])
async def test_microsoft_rejects_missing_identity_claims(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    claim: str,
) -> None:
    microsoft_claims.pop(claim)
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


async def test_microsoft_rejects_invalid_signature(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
) -> None:
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        microsoft_claims, attacker_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


async def test_microsoft_rejects_wrong_signing_key_issuer(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    signing_jwk: dict[str, Any],
) -> None:
    signing_jwk["issuer"] = f"https://login.microsoftonline.com/{OTHER_TENANT_ID}/v2.0"
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


async def test_microsoft_rejects_token_from_another_configured_tenant(
    monkeypatch: pytest.MonkeyPatch,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    signing_jwk: dict[str, Any],
) -> None:
    monkeypatch.setattr(config, "MICROSOFT_TENANT", OTHER_TENANT_ID)
    monkeypatch.setattr(config, "MICROSOFT_CLIENT_ID", CLIENT_ID)
    metadata: dict[str, Any] = {
        "issuer": f"https://login.microsoftonline.com/{OTHER_TENANT_ID}/v2.0",
        "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
    }
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=metadata
                if request.url.path.endswith("openid-configuration")
                else {"keys": [signing_jwk]},
            )
        )
    ) as client:
        with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
            await OAuthMicrosoftProvider.get_user_info(client, token)


@pytest.mark.parametrize("verified", [True, False, None])
async def test_microsoft_signed_claim_controls_existing_account_signin(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
    user: User,
    verified: bool | None,
) -> None:
    user = user.model_copy(update={"email": "victim@example.com"})
    microsoft_claims["email"] = user.email
    microsoft_claims["xms_edov"] = verified
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )
    mocks = mock_collaborators(
        AuthHandler(secret_key="test", oauth_provider=OAuthMicrosoftProvider)
    )
    mocks.user_repository.get_user.return_value = user
    create_tokens = Mock(wraps=mocks.handler._create_tokens)
    monkeypatch.setattr(mocks.handler, "_create_tokens", create_tokens)
    client_context = AsyncMock()
    client_context.__aenter__.return_value = microsoft_client
    monkeypatch.setattr(httpx, "AsyncClient", Mock(return_value=client_context))
    monkeypatch.setattr(
        OAuthMicrosoftProvider,
        "exchange_code_for_token",
        AsyncMock(return_value=token),
    )

    if verified is True:
        result = await mocks.handler.handle_oauth("code")
        assert result.user_id == user.id
        create_tokens.assert_called_once_with(user.email)
        update = mocks.user_repository.update_user.call_args.args[0]
        assert update.auth_method == AuthProvider.MICROSOFT
    else:
        with pytest.raises(AuthError, match="email is not verified"):
            await mocks.handler.handle_oauth("code")
        mocks.user_repository.get_user.assert_not_awaited()
        mocks.user_repository.update_user.assert_not_awaited()
        mocks.user_repository.create_user.assert_not_awaited()
        create_tokens.assert_not_called()
    assert user.auth_method == AuthProvider.EMAIL


@pytest.mark.parametrize("token", ["graph-access-token", "", "malformed.jwt.token"])
async def test_microsoft_rejects_opaque_or_malformed_token(
    microsoft_client: httpx.AsyncClient, token: str
) -> None:
    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


async def test_microsoft_does_not_use_upn_without_email_claim(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
) -> None:
    microsoft_claims.pop("email")
    microsoft_claims["preferred_username"] = "victim@example.com"
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    userinfo = await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)

    assert userinfo.email is None


async def test_microsoft_rejects_unknown_signing_key(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
) -> None:
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": "unknown"}
    )

    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


async def test_microsoft_reports_unavailable_discovery(
    microsoft_claims: dict[str, Any], signing_key: rsa.RSAPrivateKey
) -> None:
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503))
    ) as client:
        with pytest.raises(AuthError) as error:
            await OAuthMicrosoftProvider.get_user_info(client, token)

    assert error.value.status_code == 503


async def test_microsoft_organizations_excludes_consumer_accounts(
    microsoft_client: httpx.AsyncClient,
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumer_tenant = "9188040d-6c67-4c5b-b112-36a304b66dad"
    monkeypatch.setattr(config, "MICROSOFT_TENANT", "organizations")
    microsoft_claims.update(
        tid=consumer_tenant,
        iss=f"https://login.microsoftonline.com/{consumer_tenant}/v2.0",
    )
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )

    with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
        await OAuthMicrosoftProvider.get_user_info(microsoft_client, token)


@pytest.mark.parametrize("payload", [None, [], {}, {"issuer": 1}])
async def test_microsoft_rejects_invalid_discovery_payload(
    microsoft_claims: dict[str, Any],
    signing_key: rsa.RSAPrivateKey,
    payload: object,
) -> None:
    token = jwt.encode(
        microsoft_claims, signing_key, algorithm="RS256", headers={"kid": KEY_ID}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(AuthError, match="Invalid Microsoft ID token"):
            await OAuthMicrosoftProvider.get_user_info(client, token)
