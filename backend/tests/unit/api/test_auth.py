from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.auth import auth_router
from luml.models import AuthUser
from luml.schemas.user import ChangePasswordIn
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
UPDATE_PROFILE_PATH = "/v1/auth/users/me"


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router, prefix="/v1")
    app.add_middleware(AuthenticationMiddleware, backend=_SignedInBackend())
    return TestClient(app)


@pytest.mark.parametrize("field", ["disabled", "auth_method"])
@patch("luml.api.auth.auth_handler.update_user", new_callable=AsyncMock)
def test_update_profile_rejects_protected_fields(
    mock_update_user: AsyncMock, field: str
) -> None:
    value: bool | str = True if field == "disabled" else "GOOGLE"

    response = _client().patch(UPDATE_PROFILE_PATH, json={field: value})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    mock_update_user.assert_not_awaited()


@patch("luml.api.auth.auth_handler.update_user", new_callable=AsyncMock)
def test_update_profile_accepts_profile_fields(
    mock_update_user: AsyncMock,
) -> None:
    mock_update_user.return_value = True

    response = _client().patch(
        UPDATE_PROFILE_PATH,
        json={"full_name": "Updated Name", "photo": "https://example.com/photo.jpg"},
    )

    assert response.status_code == 200
    mock_update_user.assert_awaited_once()


@patch("luml.api.auth.auth_handler.handle_change_password", new_callable=AsyncMock)
def test_change_password(mock_change_password: AsyncMock) -> None:
    response = _client().post(
        "/v1/auth/change-password",
        json={
            "current_password": "current-password",
            "new_password": "new-password",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"detail": "Password changed successfully"}
    mock_change_password.assert_awaited_once_with(
        "caller@example.com",
        ChangePasswordIn(
            current_password="current-password", new_password="new-password"
        ),
    )


@patch("luml.api.auth.auth_handler.handle_change_password", new_callable=AsyncMock)
def test_change_password_rejects_short_passwords(
    mock_change_password: AsyncMock,
) -> None:
    response = _client().post(
        "/v1/auth/change-password",
        json={"current_password": "short", "new_password": "new-password"},
    )

    assert response.status_code == 422
    mock_change_password.assert_not_awaited()
