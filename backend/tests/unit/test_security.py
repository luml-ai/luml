from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from luml.handlers.auth import AuthHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.security import JWTAuthenticationBackend
from luml.schemas.user import UserOut
from luml.settings import config
from starlette.middleware.authentication import AuthenticationMiddleware

EMAIL = "caller@example.com"
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

token_minter = AuthHandler(secret_key=config.AUTH_SECRET_KEY)


@pytest.fixture
def bearer_tokens() -> dict[str, str]:
    tokens = token_minter._create_tokens(EMAIL)
    assert tokens.refresh_token

    return {
        "access": tokens.access_token,
        "refresh": tokens.refresh_token,
        "email_confirmation": token_minter._generate_email_confirmation_token(EMAIL),
        "password_reset": token_minter._generate_password_reset_token(EMAIL),
        "legacy_typeless": token_minter._create_token(
            data={"sub": EMAIL}, expires_delta=3600
        ),
    }


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(UserAuthentication(["jwt"]))])
    async def protected() -> dict[str, str]:
        return {"detail": "ok"}

    app.add_middleware(AuthenticationMiddleware, backend=JWTAuthenticationBackend())
    return TestClient(app)


@patch(
    "luml.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@patch("luml.handlers.auth.UserRepository.get_public_user", new_callable=AsyncMock)
@pytest.mark.parametrize(
    "purpose",
    ["refresh", "email_confirmation", "password_reset", "legacy_typeless"],
)
def test_only_access_tokens_authenticate_api_requests(
    mock_get_public_user: AsyncMock,
    mock_is_token_blacklisted: AsyncMock,
    purpose: str,
    bearer_tokens: dict[str, str],
) -> None:
    mock_is_token_blacklisted.return_value = False

    response = _client().get(
        "/protected", headers={"Authorization": f"Bearer {bearer_tokens[purpose]}"}
    )

    assert response.status_code == 401
    mock_get_public_user.assert_not_awaited()


@patch(
    "luml.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@patch("luml.handlers.auth.UserRepository.get_public_user", new_callable=AsyncMock)
def test_access_token_authenticates_api_requests(
    mock_get_public_user: AsyncMock,
    mock_is_token_blacklisted: AsyncMock,
    bearer_tokens: dict[str, str],
) -> None:
    mock_is_token_blacklisted.return_value = False
    mock_get_public_user.return_value = UserOut(
        id=USER_ID,
        email=EMAIL,
        full_name="Caller",
        disabled=False,
        photo=None,
        has_api_key=False,
    )

    response = _client().get(
        "/protected", headers={"Authorization": f"Bearer {bearer_tokens['access']}"}
    )

    assert response.status_code == 200


def _api_key_client() -> TestClient:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(UserAuthentication(["api_key"]))])
    async def protected() -> dict[str, str]:
        return {"detail": "ok"}

    app.add_middleware(AuthenticationMiddleware, backend=JWTAuthenticationBackend())
    return TestClient(app)


@patch(
    "luml.handlers.api_keys.UserRepository.get_user_by_api_key_hash",
    new_callable=AsyncMock,
)
@pytest.mark.parametrize(("disabled", "expected_status"), [(True, 401), (False, 200)])
def test_api_key_of_disabled_user_does_not_authenticate(
    mock_get_user_by_api_key_hash: AsyncMock, disabled: bool, expected_status: int
) -> None:
    mock_get_user_by_api_key_hash.return_value = UserOut(
        id=USER_ID, email=EMAIL, disabled=disabled, has_api_key=True
    )

    response = _api_key_client().get(
        "/protected", headers={"Authorization": "Bearer dfs_some-api-key"}
    )

    assert response.status_code == expected_status
