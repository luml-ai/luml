from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from luml.clients.oauth_providers import (
    OAuthGoogleProvider,
    OAuthMicrosoftProvider,
    OAuthProvider,
)
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError
from luml.schemas.auth import OAuthLogin, Token, UserInfo
from luml.schemas.user import AuthProvider, UpdateUser, User

from tests.support.ids import USER_ID
from tests.support.mocks import CollaboratorMocks


class TestAuthOAuth:
    async def test_handle_oauth_creates_google_user_when_not_registered(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        tokens: Token,
        user: User,
    ) -> None:
        created_user = User(
            id=USER_ID,
            email=user.email,
            full_name=user.full_name,
            email_verified=True,
            auth_method=AuthProvider.GOOGLE,
            photo="http://example.com/photo.jpg",
            hashed_password=None,
            disabled=False,
        )
        expected = OAuthLogin(token=tokens, user_id=created_user.id)
        assert user.full_name is not None
        mocks.user_repository.get_user.return_value = None
        mocks.user_repository.create_user.return_value = created_user
        create_tokens = Mock(return_value=tokens)
        monkeypatch.setattr(mocks.handler, "_create_tokens", create_tokens)

        with (
            patch.object(
                OAuthGoogleProvider, "exchange_code_for_token", new_callable=AsyncMock
            ) as mock_exchange_code,
            patch.object(
                OAuthGoogleProvider, "get_user_info", new_callable=AsyncMock
            ) as mock_get_user_info,
        ):
            mock_exchange_code.return_value = "access_token"
            mock_get_user_info.return_value = UserInfo(
                email=user.email,
                full_name=user.full_name,
                photo_url="http://example.com/photo.jpg",
                email_verified=True,
            )

            result = await mocks.handler.handle_oauth("code")

        assert result == expected
        mock_exchange_code.assert_awaited_once()
        mock_get_user_info.assert_awaited_once()
        mocks.user_repository.create_user.assert_awaited_once()
        create_tokens.assert_called_once_with(created_user.email)

    async def test_handle_oauth_updates_auth_method_for_existing_user(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        tokens: Token,
    ) -> None:
        email = "test@example.com"
        photo = "http://example.com/photo.jpg"
        mocks.user_repository.get_user.return_value = MagicMock(
            id=USER_ID, email=email, auth_method=AuthProvider.EMAIL, photo=photo
        )
        monkeypatch.setattr(mocks.handler, "_create_tokens", Mock(return_value=tokens))

        with (
            patch.object(
                OAuthGoogleProvider, "exchange_code_for_token", new_callable=AsyncMock
            ) as mock_exchange_code,
            patch.object(
                OAuthGoogleProvider, "get_user_info", new_callable=AsyncMock
            ) as mock_get_user_info,
        ):
            mock_exchange_code.return_value = "access_token"
            mock_get_user_info.return_value = UserInfo(
                email=email, full_name="Test User", photo_url=photo, email_verified=True
            )

            await mocks.handler.handle_oauth("code")

        mocks.user_repository.update_user.assert_awaited_once_with(
            UpdateUser(email=email, auth_method=AuthProvider.GOOGLE)
        )

    @pytest.mark.parametrize("provider", [OAuthGoogleProvider, OAuthMicrosoftProvider])
    @pytest.mark.parametrize("email_verified", [False, None])
    @pytest.mark.parametrize("registered", [True, False])
    async def test_handle_oauth_rejects_unverified_email_before_account_access(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
        provider: type[OAuthProvider],
        email_verified: bool | None,
        registered: bool,
    ) -> None:
        assert user.full_name is not None
        mocks.handler.oauth_provider = provider
        mocks.user_repository.get_user.return_value = user if registered else None
        mocks.user_repository.create_user.return_value = user
        create_tokens = Mock(wraps=mocks.handler._create_tokens)
        monkeypatch.setattr(mocks.handler, "_create_tokens", create_tokens)

        with (
            patch.object(provider, "exchange_code_for_token", new_callable=AsyncMock),
            patch.object(
                provider,
                "get_user_info",
                new_callable=AsyncMock,
                return_value=UserInfo(
                    email=user.email,
                    full_name=user.full_name,
                    email_verified=email_verified,
                ),
            ),
            pytest.raises(AuthError, match="email is not verified") as error,
        ):
            await mocks.handler.handle_oauth("code")

        assert error.value.status_code == 403
        mocks.user_repository.get_user.assert_not_awaited()
        mocks.user_repository.create_user.assert_not_awaited()
        mocks.user_repository.update_user.assert_not_awaited()
        create_tokens.assert_not_called()
        assert user.auth_method == AuthProvider.EMAIL
