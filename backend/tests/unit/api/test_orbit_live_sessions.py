from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from luml.api.orbits.orbit_live_sessions import live_session_handler
from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.live_session_tokens import TunnelTokenKind
from luml.models import AuthUser
from luml.schemas.live_session import LiveSession, LiveSessionStartOut
from luml.service import AppService
from luml.settings import config
from starlette.authentication import AuthCredentials

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
BASE_PATH = f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/live-sessions"
AUTHENTICATE = "luml.infra.security.JWTAuthenticationBackend.authenticate"
REPO = "luml.handlers.live_sessions.LiveSessionRepository"


def _signed_in() -> tuple[AuthCredentials, AuthUser]:
    return AuthCredentials(["authenticated", "api_key"]), AuthUser(
        user_id=USER_ID, email="caller@example.com"
    )


def _enabled_handler() -> LiveSessionHandler:
    pem = (
        ec.generate_private_key(ec.SECP256R1())
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    return LiveSessionHandler(
        config.model_copy(
            update={
                "LIVE_SESSION_SIGNING_KEY": pem,
                "LIVE_SESSION_RELAY_ID": "relay-1",
                "LIVE_SESSION_RELAY_BASE_DOMAIN": "tunnel.example",
                "LIVE_SESSION_RELAY_AGENT_URL": "wss://tunnel.example/connect",
            }
        )
    )


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=None)
def test_public_keys_are_published_without_sign_in(
    mock_authenticate: AsyncMock,
) -> None:
    enabled = _enabled_handler()
    with patch.object(live_session_handler, "_signer", enabled._signer):
        response = TestClient(AppService()).get("/.well-known/jwks.json")

    assert response.status_code == 200
    keys = response.json()["keys"]
    assert [key["kid"] for key in keys] == [enabled.public_keys()["keys"][0]["kid"]]
    assert enabled._signer is not None
    token, _ = enabled._signer.sign(
        TunnelTokenKind.VIEW,
        "relay-1",
        "k3f9x2ab",
        str(USER_ID),
        timedelta(minutes=5),
    )
    claims = jwt.decode(
        token,
        jwt.PyJWK(keys[0], algorithm="ES256").key,
        algorithms=["ES256"],
        audience="relay-1",
        issuer="luml",
    )
    assert claims["sid"] == "k3f9x2ab"


@patch(f"{REPO}.create_live_session", new_callable=AsyncMock)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_start_fails_with_its_own_status_when_the_feature_is_off(
    mock_authenticate: AsyncMock, mock_create: AsyncMock
) -> None:
    response = TestClient(AppService()).post(BASE_PATH, json={"name": "run"})

    assert response.status_code == 501
    assert response.json() == {
        "detail": "Live sessions are not set up in this deployment"
    }
    mock_create.assert_not_awaited()


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_start_requires_a_name(mock_authenticate: AsyncMock) -> None:
    response = TestClient(AppService()).post(BASE_PATH, json={"name": ""})

    assert response.status_code == 422


@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=None)
def test_operations_require_sign_in(mock_authenticate: AsyncMock) -> None:
    response = TestClient(AppService()).get(BASE_PATH)

    assert response.status_code == 401


@patch(
    "luml.api.orbits.orbit_live_sessions.LiveSessionHandler.start_session",
    new_callable=AsyncMock,
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_start_route(mock_authenticate: AsyncMock, mock_start: AsyncMock) -> None:
    mock_start.return_value = LiveSessionStartOut(
        id="k3f9x2ab",
        public_url="https://k3f9x2ab.tunnel.example",
        app_url="https://app.luml.ai/flow/k3f9x2ab",
        agent_url="wss://tunnel.example/connect",
        expose_token="token",
        token_expires_at=datetime(2026, 9, 29, tzinfo=UTC),
    )

    response = TestClient(AppService()).post(BASE_PATH, json={"name": "training run"})

    assert response.status_code == 200
    assert response.json()["heartbeat_interval"] == 30
    assert mock_start.await_args is not None
    args = mock_start.await_args.args
    assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
    assert args[3].name == "training run"


@pytest.mark.parametrize(
    ("method", "path", "handler_method", "body"),
    [
        ("get", "", "list_sessions", None),
        ("get", "/k3f9x2ab", "get_session", None),
        (
            "post",
            "/k3f9x2ab/heartbeat",
            "record_heartbeat",
            {"connected": True, "token_expires_at": "2026-09-29T12:00:00Z"},
        ),
        ("post", "/k3f9x2ab/view-token", "issue_view_token", None),
        ("post", "/k3f9x2ab/end", "end_session", None),
    ],
)
@patch(AUTHENTICATE, new_callable=AsyncMock, return_value=_signed_in())
def test_session_routes_pass_the_caller_and_the_session(
    mock_authenticate: AsyncMock,
    method: str,
    path: str,
    handler_method: str,
    body: dict[str, object] | None,
) -> None:
    session = LiveSession(
        id="k3f9x2ab",
        orbit_id=ORBIT_ID,
        user_id=USER_ID,
        name="run",
        relay_id="relay-1",
        started_at=datetime.now(UTC),
        connected=False,
    )
    results = {
        "list_sessions": [session],
        "get_session": session,
        "record_heartbeat": {"status": "live"},
        "issue_view_token": {
            "token": "t",
            "launch_url": "https://k3f9x2ab.tunnel.example/.luml-tunnel/launch?token=t",
            "expires_at": "2026-09-29T12:00:00Z",
        },
        "end_session": session,
    }
    with patch(
        f"luml.api.orbits.orbit_live_sessions.LiveSessionHandler.{handler_method}",
        new_callable=AsyncMock,
        return_value=results[handler_method],
    ) as mock_handler:
        client = TestClient(AppService())
        response = client.request(method, BASE_PATH + path, json=body)

    assert response.status_code == 200
    assert mock_handler.await_args is not None
    args = mock_handler.await_args.args
    assert args[:3] == (USER_ID, ORGANIZATION_ID, ORBIT_ID)
    if path:
        assert args[3] == "k3f9x2ab"
