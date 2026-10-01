from time import time
from unittest.mock import Mock, patch

import pytest
from jwt.exceptions import InvalidTokenError
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError
from luml.schemas.user import CreateUser, UpdateUser, User

from tests.support.mocks import CollaboratorMocks


class TestAuthEmailFlows:
    def test_generate_password_reset_token_creates_one_hour_reset_token(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        create_token = Mock(return_value="test_token")
        monkeypatch.setattr(mocks.handler, "_create_token", create_token)

        actual = mocks.handler._generate_password_reset_token(user.email)

        assert actual == "test_token"
        create_token.assert_called_once_with(
            data={"sub": user.email, "type": "password_reset"},
            expires_delta=3600,
        )

    async def test_send_password_reset_email_sends_reset_link(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        token = "token"
        link = f"https://example.com/reset?token=${token}"
        generate_password_reset_token = Mock(return_value=token)
        get_password_reset_link = Mock(return_value=link)
        monkeypatch.setattr(
            mocks.handler,
            "_generate_password_reset_token",
            generate_password_reset_token,
        )
        monkeypatch.setattr(
            mocks.handler, "_get_password_reset_link", get_password_reset_link
        )
        mocks.user_repository.get_user.return_value = user

        await mocks.handler.send_password_reset_email(user.email)

        mocks.user_repository.get_user.assert_awaited_once_with(user.email)
        generate_password_reset_token.assert_called_once_with(user.email)
        get_password_reset_link.assert_called_once_with(token)
        mocks.emails_handler.send_password_reset_email.assert_called_once_with(
            user.email, link, user.full_name
        )

    async def test_send_password_reset_email_does_nothing_when_user_not_found(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        mocks.user_repository.get_user.return_value = None

        await mocks.handler.send_password_reset_email(user.email)

        mocks.user_repository.get_user.assert_awaited_once_with(user.email)

    def test_get_password_reset_link_appends_token_to_configured_url(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        token = "token"
        expected = "https://test.com/" + token

        with patch(
            "luml.handlers.auth.config.CHANGE_PASSWORD_URL", "https://test.com/"
        ):
            actual = mocks.handler._get_password_reset_link(token)

        assert actual == expected

    async def test_handle_email_confirmation_marks_email_verified(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        unverified_user = user.model_copy()
        unverified_user.email_verified = False
        mocks.user_repository.get_user.return_value = unverified_user

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": unverified_user.email,
                "type": "email_confirmation",
            }

            await mocks.handler.handle_email_confirmation("token")

        mock_jwt_decode.assert_called_once()
        mocks.user_repository.get_user.assert_awaited_once_with(unverified_user.email)
        mocks.user_repository.update_user.assert_awaited_once()

    async def test_handle_email_confirmation_raises_when_token_invalid(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.side_effect = InvalidTokenError()

            with pytest.raises(AuthError, match="Invalid token") as error:
                await mocks.handler.handle_email_confirmation("token")

        assert error.value.status_code == 400

    async def test_handle_email_confirmation_raises_when_email_missing(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {"sub": None, "type": "email_confirmation"}

            with pytest.raises(AuthError, match="Invalid token") as error:
                await mocks.handler.handle_email_confirmation("token")

        assert error.value.status_code == 400

    async def test_handle_email_confirmation_raises_when_user_not_found(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        mocks.user_repository.get_user.return_value = None

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": user.email,
                "type": "email_confirmation",
            }

            with pytest.raises(AuthError, match="User not found") as error:
                await mocks.handler.handle_email_confirmation("token")

        assert error.value.status_code == 404
        mock_jwt_decode.assert_called_once()
        mocks.user_repository.get_user.assert_awaited_once()

    async def test_handle_email_confirmation_does_not_update_when_already_verified(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        verified_user = user.model_copy()
        verified_user.email_verified = True
        mocks.user_repository.get_user.return_value = verified_user

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": verified_user.email,
                "type": "email_confirmation",
            }

            await mocks.handler.handle_email_confirmation("token")

        mock_jwt_decode.assert_called_once()
        mocks.user_repository.get_user.assert_awaited_once_with(verified_user.email)
        mocks.user_repository.update_user.assert_not_awaited()

    @pytest.mark.parametrize(
        "purpose", ["access", "refresh", "password_reset", "legacy_typeless"]
    )
    async def test_handle_email_confirmation_rejects_other_token_purposes(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        purpose: str,
        tokens_by_purpose: dict[str, str],
    ) -> None:
        with pytest.raises(AuthError, match="Invalid token") as error:
            await mocks.handler.handle_email_confirmation(tokens_by_purpose[purpose])

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_not_awaited()
        mocks.user_repository.update_user.assert_not_awaited()

    async def test_handle_email_confirmation_accepts_a_minted_confirmation_token(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        unverified_user = user.model_copy()
        unverified_user.email_verified = False
        mocks.user_repository.get_user.return_value = unverified_user

        await mocks.handler.handle_email_confirmation(
            mocks.handler._generate_email_confirmation_token(unverified_user.email)
        )

        mocks.user_repository.update_user.assert_awaited_once_with(
            UpdateUser(email=unverified_user.email, email_verified=True)
        )

    async def test_handle_reset_password_stores_new_password_hash(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        new_password = "new_pass"
        update_user = UpdateUser(email=user.email, hashed_password=user.hashed_password)
        get_password_hash = Mock(return_value=user.hashed_password)
        monkeypatch.setattr(mocks.handler, "_get_password_hash", get_password_hash)
        mocks.user_repository.get_user.return_value = user

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": user.email,
                "type": "password_reset",
                "exp": int(time()) + 3600,
            }

            await mocks.handler.handle_reset_password("token", new_password)

        mock_jwt_decode.assert_called_once()
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)
        get_password_hash.assert_called_once_with(new_password)
        mocks.user_repository.update_user.assert_awaited_once_with(update_user)

    async def test_handle_reset_password_raises_when_token_expired(
        self, mocks: CollaboratorMocks[AuthHandler], new_user: CreateUser
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": new_user.email,
                "type": "password_reset",
                "exp": None,
            }

            with pytest.raises(AuthError, match="Token expired") as error:
                await mocks.handler.handle_reset_password("token", "new_pass")

        assert error.value.status_code == 400
        mock_jwt_decode.assert_called_once()

    async def test_handle_reset_password_raises_when_email_missing(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": None,
                "type": "password_reset",
                "exp": int(time()) + 3600,
            }

            with pytest.raises(AuthError, match="Invalid token") as error:
                await mocks.handler.handle_reset_password("token", "new_pass")

        assert error.value.status_code == 400
        mock_jwt_decode.assert_called_once()

    async def test_handle_reset_password_raises_when_user_not_found(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        mocks.user_repository.get_user.return_value = None

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": user.email,
                "type": "password_reset",
                "exp": int(time()) + 3600,
            }

            with pytest.raises(AuthError, match="User not found") as error:
                await mocks.handler.handle_reset_password("token", "new_pass")

        assert error.value.status_code == 404
        mock_jwt_decode.assert_called_once()
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)

    async def test_handle_reset_password_raises_when_token_invalid(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.side_effect = InvalidTokenError()

            with pytest.raises(AuthError, match="Invalid token") as exc:
                await mocks.handler.handle_reset_password("token", "new_pass")

        assert exc.value.status_code == 400
        mock_jwt_decode.assert_called_once()

    @pytest.mark.parametrize(
        "purpose", ["access", "refresh", "email_confirmation", "legacy_typeless"]
    )
    async def test_handle_reset_password_rejects_other_token_purposes(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        purpose: str,
        tokens_by_purpose: dict[str, str],
    ) -> None:
        with pytest.raises(AuthError, match="Invalid token") as error:
            await mocks.handler.handle_reset_password(
                tokens_by_purpose[purpose], "new_pass"
            )

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_not_awaited()
        mocks.user_repository.update_user.assert_not_awaited()

    async def test_handle_reset_password_accepts_a_minted_reset_token(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        mocks.user_repository.get_user.return_value = user
        monkeypatch.setattr(
            mocks.handler, "_get_password_hash", Mock(return_value="argon_hash")
        )

        await mocks.handler.handle_reset_password(
            mocks.handler._generate_password_reset_token(user.email), "new_pass"
        )

        mocks.user_repository.update_user.assert_awaited_once_with(
            UpdateUser(email=user.email, hashed_password="argon_hash")
        )
