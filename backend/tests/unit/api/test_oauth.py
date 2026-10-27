from time import time
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import URL
from luml.api import auth
from luml.handlers.auth import AuthHandler
from luml.schemas.auth import OAuthLogin, Token
from luml.settings import config

from tests.support.ids import USER_ID


@pytest.fixture(params=["google", "microsoft"])
def provider(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def oauth_client(client: TestClient) -> TestClient:
    client.base_url = URL("https://testserver")
    return client


def _start_login(client: TestClient, provider: str) -> str:
    response = client.get(f"/v1/auth/{provider}/login", follow_redirects=False)
    assert response.status_code == 307
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def test_login_sets_fresh_browser_bound_state(
    oauth_client: TestClient, provider: str
) -> None:
    first = _start_login(oauth_client, provider)
    second = _start_login(oauth_client, provider)

    assert first != second
    assert second.startswith(f"{provider}.")
    cookie = next(
        cookie
        for cookie in oauth_client.cookies.jar
        if cookie.name == f"__Host-oauth_{provider}_state"
    )
    assert cookie.value == second
    assert cookie.secure
    assert cookie.path == "/"
    assert not cookie.domain_specified
    assert cookie.has_nonstandard_attr("HttpOnly")
    assert cookie.get_nonstandard_attr("SameSite") == config.AUTH_COOKIE_SAMESITE
    assert cookie.expires is not None
    assert 0 < cookie.expires - time() <= 300


@pytest.mark.parametrize(
    "failure",
    ["missing", "empty", "bogus", "static", "no_cookie", "other_browser", "old_login"],
)
def test_callback_rejects_unbound_state_before_processing_code(
    oauth_client: TestClient, provider: str, failure: str
) -> None:
    first = _start_login(oauth_client, provider)
    state: str | None = first
    if failure == "missing":
        state = None
    elif failure == "empty":
        state = ""
    elif failure == "bogus":
        state = "garbage-not-google"
    elif failure == "static":
        state = provider
        oauth_client.cookies.set(f"__Host-oauth_{provider}_state", state)
    elif failure == "no_cookie":
        oauth_client.cookies.clear()
    elif failure in {"other_browser", "old_login"}:
        _start_login(oauth_client, provider)

    handler: AuthHandler = getattr(auth, f"{provider}_auth_handler")
    with patch.object(handler, "handle_oauth", new_callable=AsyncMock) as handle_oauth:
        params = {"code": "attacker-code"}
        if state is not None:
            params["state"] = state
        response = oauth_client.get(f"/v1/auth/{provider}/callback", params=params)

    assert response.status_code == 400
    assert "access_token" not in response.cookies
    assert "refresh_token" not in response.cookies
    handle_oauth.assert_not_awaited()


@pytest.mark.parametrize(
    "failure",
    [
        "expired",
        "tampered",
        "wrong_type",
        "wrong_provider",
        "wrong_audience",
        "no_exp",
        "no_iat",
        "no_nonce",
    ],
)
def test_callback_rejects_invalid_signed_state_even_with_matching_cookie(
    oauth_client: TestClient, provider: str, failure: str
) -> None:
    state = _start_login(oauth_client, provider)
    prefix, token = state.split(".", 1)
    payload = jwt.decode(token, options={"verify_signature": False})
    if failure == "expired":
        payload["exp"] = int(time()) - 1
    elif failure == "wrong_type":
        payload["type"] = "access"
    elif failure == "wrong_provider":
        payload["provider"] = "microsoft" if provider == "google" else "google"
    elif failure == "wrong_audience":
        payload["aud"] = "luml-platform-admin"
    elif failure.startswith("no_"):
        del payload[failure.removeprefix("no_")]
    token = jwt.encode(payload, config.AUTH_SECRET_KEY, algorithm="HS256")
    if failure == "tampered":
        header_payload, signature = token.rsplit(".", 1)
        signature = ("a" if signature[0] != "a" else "b") + signature[1:]
        token = f"{header_payload}.{signature}"
    state = f"{prefix}.{token}"
    oauth_client.cookies.clear()
    oauth_client.cookies.set(f"__Host-oauth_{provider}_state", state)

    handler: AuthHandler = getattr(auth, f"{provider}_auth_handler")
    with patch.object(handler, "handle_oauth", new_callable=AsyncMock) as handle_oauth:
        response = oauth_client.get(
            f"/v1/auth/{provider}/callback", params={"code": "code", "state": state}
        )

    assert response.status_code == 400
    assert "access_token" not in response.cookies
    handle_oauth.assert_not_awaited()


def test_callback_rejects_state_from_other_provider(
    oauth_client: TestClient, provider: str
) -> None:
    other = "microsoft" if provider == "google" else "google"
    state = _start_login(oauth_client, other)
    oauth_client.cookies.set(f"__Host-oauth_{provider}_state", state)
    handler: AuthHandler = getattr(auth, f"{provider}_auth_handler")
    with patch.object(handler, "handle_oauth", new_callable=AsyncMock) as handle_oauth:
        response = oauth_client.get(
            f"/v1/auth/{provider}/callback", params={"code": "code", "state": state}
        )

    assert response.status_code == 400
    handle_oauth.assert_not_awaited()


def test_callback_accepts_matching_state_and_clears_cookie(
    oauth_client: TestClient, provider: str
) -> None:
    state = _start_login(oauth_client, provider)
    handler: AuthHandler = getattr(auth, f"{provider}_auth_handler")
    with patch.object(handler, "handle_oauth", new_callable=AsyncMock) as handle_oauth:
        handle_oauth.return_value = OAuthLogin(
            user_id=USER_ID,
            token=Token(
                access_token="access", refresh_token="refresh", token_type="bearer"
            ),
        )
        response = oauth_client.get(
            f"/v1/auth/{provider}/callback", params={"code": "code", "state": state}
        )
        replay = oauth_client.get(
            f"/v1/auth/{provider}/callback", params={"code": "code", "state": state}
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(USER_ID)
    assert response.cookies["access_token"] == "access"
    assert response.cookies["refresh_token"] == "refresh"
    assert f"__Host-oauth_{provider}_state" not in oauth_client.cookies
    assert replay.status_code == 400
    handle_oauth.assert_awaited_once_with("code")


def test_callback_with_valid_state_still_requires_code(
    oauth_client: TestClient, provider: str
) -> None:
    state = _start_login(oauth_client, provider)
    response = oauth_client.get(
        f"/v1/auth/{provider}/callback", params={"state": state}
    )

    assert response.status_code == 400
    assert "access_token" not in response.cookies
