from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from luml.schemas.user import AuthProvider, ChangePasswordIn, CurrentUserOut

from tests.support.auth import CALLER_EMAIL
from tests.support.ids import USER_ID

UPDATE_PROFILE_PATH = "/v1/auth/users/me"


class TestAuth:
    @pytest.mark.parametrize("field", ["disabled", "auth_method"])
    @patch("luml.api.auth.auth_handler.update_user", new_callable=AsyncMock)
    def test_update_profile_rejects_protected_fields(
        self, mock_update_user: AsyncMock, field: str, client: TestClient
    ) -> None:
        value: bool | str = True if field == "disabled" else "GOOGLE"

        response = client.patch(UPDATE_PROFILE_PATH, json={field: value})

        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", field]
        mock_update_user.assert_not_awaited()

    @patch("luml.api.auth.auth_handler.update_user", new_callable=AsyncMock)
    def test_update_profile_accepts_profile_fields(
        self, mock_update_user: AsyncMock, client: TestClient
    ) -> None:
        mock_update_user.return_value = True

        response = client.patch(
            UPDATE_PROFILE_PATH,
            json={
                "full_name": "Updated Name",
                "photo": "https://example.com/photo.jpg",
            },
        )

        assert response.status_code == 200
        mock_update_user.assert_awaited_once()

    @patch("luml.api.auth.auth_handler.handle_change_password", new_callable=AsyncMock)
    def test_change_password(
        self, mock_change_password: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "current-password",
                "new_password": "new-password",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"detail": "Password changed successfully"}
        mock_change_password.assert_awaited_once_with(
            CALLER_EMAIL,
            ChangePasswordIn(
                current_password="current-password", new_password="new-password"
            ),
        )

    @patch("luml.api.auth.auth_handler.handle_change_password", new_callable=AsyncMock)
    def test_change_password_rejects_short_passwords(
        self, mock_change_password: AsyncMock, client: TestClient
    ) -> None:
        response = client.post(
            "/v1/auth/change-password",
            json={"current_password": "short", "new_password": "new-password"},
        )

        assert response.status_code == 422
        mock_change_password.assert_not_awaited()

    @patch("luml.api.auth.auth_handler.handle_get_current_user", new_callable=AsyncMock)
    def test_get_current_user_returns_auth_method(
        self, mock_get_current_user: AsyncMock, client: TestClient
    ) -> None:
        mock_get_current_user.return_value = CurrentUserOut(
            id=USER_ID,
            email=CALLER_EMAIL,
            full_name="Caller",
            disabled=False,
            photo=None,
            has_api_key=False,
            auth_method=AuthProvider.EMAIL,
        )

        response = client.get(UPDATE_PROFILE_PATH)

        assert response.status_code == 200
        assert response.json()["auth_method"] == "EMAIL"
        mock_get_current_user.assert_awaited_once_with(CALLER_EMAIL)
