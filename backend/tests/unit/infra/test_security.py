from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from luml.handlers.auth import AuthHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.security import JWTAuthenticationBackend
from luml.schemas.user import AuthProvider, CurrentUserOut, UserOut
from luml.settings import config
from starlette.middleware.authentication import AuthenticationMiddleware

from tests.support.ids import USER_ID

EMAIL = "caller@example.com"


@pytest.fixture
def bearer_tokens() -> dict[str, str]:
    token_minter = AuthHandler(secret_key=config.AUTH_SECRET_KEY)
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


def _client(scheme: str) -> TestClient:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(UserAuthentication([scheme]))])
    async def protected() -> dict[str, str]:
        return {"detail": "ok"}

    app.add_middleware(AuthenticationMiddleware, backend=JWTAuthenticationBackend())
    return TestClient(app)


class TestJWTAuthenticationBackend:
    @pytest.mark.parametrize(
        "purpose",
        ["refresh", "email_confirmation", "password_reset", "legacy_typeless"],
    )
    def test_get_protected_returns_401_when_bearer_is_not_access_token(
        self, purpose: str, bearer_tokens: dict[str, str]
    ) -> None:
        with (
            patch(
                "luml.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "luml.handlers.auth.UserRepository.get_current_user",
                new_callable=AsyncMock,
            ) as get_current_user,
        ):
            response = _client("jwt").get(
                "/protected",
                headers={"Authorization": f"Bearer {bearer_tokens[purpose]}"},
            )

        assert response.status_code == 401
        get_current_user.assert_not_awaited()

    def test_get_protected_returns_200_when_bearer_is_access_token(
        self, bearer_tokens: dict[str, str]
    ) -> None:
        current_user = CurrentUserOut(
            id=USER_ID,
            email=EMAIL,
            full_name="Caller",
            disabled=False,
            photo=None,
            has_api_key=False,
            auth_method=AuthProvider.EMAIL,
        )

        with (
            patch(
                "luml.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "luml.handlers.auth.UserRepository.get_current_user",
                new_callable=AsyncMock,
                return_value=current_user,
            ),
        ):
            response = _client("jwt").get(
                "/protected",
                headers={"Authorization": f"Bearer {bearer_tokens['access']}"},
            )

        assert response.status_code == 200

    @pytest.mark.parametrize(
        ("disabled", "expected_status"), [(True, 401), (False, 200)]
    )
    def test_get_protected_with_api_key_returns_401_only_when_user_disabled(
        self, disabled: bool, expected_status: int
    ) -> None:
        with patch(
            "luml.handlers.api_keys.UserRepository.get_user_by_api_key_hash",
            new_callable=AsyncMock,
            return_value=UserOut(
                id=USER_ID, email=EMAIL, disabled=disabled, has_api_key=True
            ),
        ):
            response = _client("api_key").get(
                "/protected", headers={"Authorization": "Bearer dfs_some-api-key"}
            )

        assert response.status_code == expected_status
