from time import time
from unittest.mock import ANY, Mock, patch

import jwt
import pytest
from jwt.exceptions import InvalidTokenError
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError
from luml.schemas.auth import Token
from luml.schemas.user import CreateUser, SignInUser, User

from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.auth.conftest import Passwords


@pytest.fixture(autouse=True)
def stored_user(mocks: CollaboratorMocks[AuthHandler], user: User) -> None:
    mocks.user_repository.get_user.return_value = user


class TestAuthTokens:
    def test_create_tokens_returns_typed_access_and_refresh_tokens(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        actual = mocks.handler._create_tokens("test@example.com")

        assert actual
        assert actual.access_token
        assert actual.refresh_token
        assert actual.token_type == "bearer"

        access_payload = jwt.decode(
            actual.access_token,
            mocks.handler.secret_key,
            algorithms=[mocks.handler.algorithm],
        )
        refresh_payload = jwt.decode(
            actual.refresh_token,
            mocks.handler.secret_key,
            algorithms=[mocks.handler.algorithm],
        )

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"

    async def test_verify_token_returns_email(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        email = "test@example.com"

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {"sub": email, "type": "access"}

            actual = await mocks.handler._verify_token("token")

        assert actual == email
        mock_jwt_decode.assert_called_once()

    async def test_verify_token_raises_when_email_missing(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {"sub": None, "type": "access"}

            with pytest.raises(AuthError, match="Invalid token") as exc_info:
                await mocks.handler._verify_token("invalid_token")

        assert exc_info.value.status_code == 401
        mock_jwt_decode.assert_called_once()

    async def test_verify_token_raises_when_jwt_invalid(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.side_effect = InvalidTokenError()

            with pytest.raises(AuthError, match="Invalid token") as exc_info:
                await mocks.handler._verify_token("invalid_token")

        assert exc_info.value.status_code == 401
        mock_jwt_decode.assert_called_once()

    @pytest.mark.parametrize(
        "purpose",
        ["refresh", "email_confirmation", "password_reset", "legacy_typeless"],
    )
    async def test_verify_token_rejects_tokens_not_minted_for_api_access(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        purpose: str,
        tokens_by_purpose: dict[str, str],
    ) -> None:
        with pytest.raises(AuthError) as error:
            await mocks.handler._verify_token(tokens_by_purpose[purpose])

        assert error.value.status_code == 401

    async def test_verify_token_accepts_access_token(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        email = "signed-in@example.com"

        signed_in_tokens = mocks.handler._create_tokens(email)

        assert await mocks.handler._verify_token(signed_in_tokens.access_token) == email

    async def test_handle_refresh_token_returns_new_tokens(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
        tokens: Token,
    ) -> None:
        mocks.user_repository.get_user.return_value = user
        mocks.token_black_list_repository.add_token.return_value = True
        create_tokens = Mock(return_value=tokens)
        monkeypatch.setattr(mocks.handler, "_create_tokens", create_tokens)

        assert tokens.refresh_token

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": user.email,
                "type": "refresh",
                "exp": int(time()) + 300,
            }

            result = await mocks.handler.handle_refresh_token(tokens.refresh_token)

        assert result == tokens
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)
        mocks.token_black_list_repository.add_token.assert_awaited_once_with(
            tokens.refresh_token, ANY
        )
        create_tokens.assert_called_once_with(user.email, user.token_version)

    async def test_handle_refresh_token_raises_when_token_type_is_not_refresh(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        new_user: CreateUser,
        tokens: Token,
    ) -> None:
        assert tokens.refresh_token

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": new_user.email,
                "type": "bearer",
                "exp": int(time()) + 300,
            }

            with pytest.raises(AuthError, match="Invalid token type") as error:
                await mocks.handler.handle_refresh_token(tokens.refresh_token)

        assert error.value.status_code == 400

    async def test_handle_refresh_token_raises_when_email_missing(
        self, mocks: CollaboratorMocks[AuthHandler], tokens: Token
    ) -> None:
        assert tokens.refresh_token

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": None,
                "type": "refresh",
                "exp": int(time()) + 300,
            }

            with pytest.raises(AuthError, match="Invalid token") as error:
                await mocks.handler.handle_refresh_token(tokens.refresh_token)

        assert error.value.status_code == 400

    async def test_handle_refresh_token_raises_when_token_revoked(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        new_user: CreateUser,
        tokens: Token,
    ) -> None:
        mocks.token_black_list_repository.add_token.return_value = False
        mocks.user_repository.get_user.return_value = Mock(
            email=new_user.email, token_version=0
        )

        assert tokens.refresh_token

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": new_user.email,
                "type": "refresh",
                "exp": int(time()) + 300,
            }

            with pytest.raises(AuthError, match="Token has been revoked") as error:
                await mocks.handler.handle_refresh_token(tokens.refresh_token)

        assert error.value.status_code == 400
        mocks.token_black_list_repository.add_token.assert_awaited_once_with(
            tokens.refresh_token, ANY
        )

    async def test_handle_refresh_token_raises_when_user_not_found(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        tokens: Token,
    ) -> None:
        mocks.user_repository.get_user.return_value = None

        assert tokens.refresh_token

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.return_value = {
                "sub": user.email,
                "type": "refresh",
                "exp": int(time()) + 300,
            }

            with pytest.raises(AuthError, match="User not found") as error:
                await mocks.handler.handle_refresh_token(tokens.refresh_token)

        assert error.value.status_code == 404
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)

    async def test_handle_logout_blacklists_access_and_refresh_tokens(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        access_token = "access.token"
        refresh_token = "refresh.token"

        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.side_effect = [{"exp": 12345}, {"exp": 67890}]

            await mocks.handler.handle_logout(access_token, refresh_token)

        assert mock_jwt_decode.call_count == 2
        add_token = mocks.token_black_list_repository.add_token
        add_token.assert_any_await(access_token, 67890)
        add_token.assert_any_await(refresh_token, 12345)
        assert add_token.await_count == 2

    async def test_handle_logout_raises_when_refresh_token_invalid(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        with patch("luml.handlers.auth.jwt.decode") as mock_jwt_decode:
            mock_jwt_decode.side_effect = InvalidTokenError("Invalid refresh")

            with pytest.raises(AuthError, match="Invalid refresh token") as error:
                await mocks.handler.handle_logout(None, "token")

        assert error.value.status_code == 400

    async def test_signin_refresh_and_logout_flow_survives_token_typing(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        passwords: Passwords,
    ) -> None:
        mocks.user_repository.get_user.return_value = user

        signin = await mocks.handler.handle_signin(
            SignInUser(email=user.email, password=passwords.password)
        )
        assert signin.token.refresh_token
        assert (
            await mocks.handler._verify_token(signin.token.access_token) == user.email
        )

        refreshed = await mocks.handler.handle_refresh_token(signin.token.refresh_token)
        assert refreshed.refresh_token
        assert await mocks.handler._verify_token(refreshed.access_token) == user.email

        await mocks.handler.handle_logout(
            refreshed.access_token, refreshed.refresh_token
        )

        blacklisted = {
            call.args[0]
            for call in mocks.token_black_list_repository.add_token.await_args_list
        }
        assert {refreshed.access_token, refreshed.refresh_token} <= blacklisted

    async def test_is_token_blacklisted_returns_repository_verdict(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        mocks.token_black_list_repository.is_token_blacklisted.return_value = True
        token = "token"

        result = await mocks.handler.is_token_blacklisted(token)

        assert result is True
        mocks.token_black_list_repository.is_token_blacklisted.assert_awaited_once_with(
            token
        )

    @pytest.mark.parametrize("version", [None, 0, 1])
    async def test_access_token_with_previous_version_is_rejected(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        version: int | None,
    ) -> None:
        user.token_version = 2
        payload: dict[str, object] = {"sub": user.email, "type": "access"}
        if version is not None:
            payload["ver"] = version
        token = mocks.handler._create_token(payload, 3600)

        with pytest.raises(AuthError, match="revoked"):
            await mocks.handler._verify_token(token)

    @pytest.mark.parametrize("version", [None, 0, 1])
    async def test_refresh_token_with_previous_version_is_rejected(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        version: int | None,
    ) -> None:
        user.token_version = 2
        payload: dict[str, object] = {"sub": user.email, "type": "refresh"}
        if version is not None:
            payload["ver"] = version
        token = mocks.handler._create_token(payload, 3600)

        with pytest.raises(AuthError, match="revoked"):
            await mocks.handler.handle_refresh_token(token)

        mocks.token_black_list_repository.add_token.assert_not_awaited()

    async def test_legacy_access_token_works_before_first_password_change(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        token = mocks.handler._create_token({"sub": user.email, "type": "access"}, 3600)

        assert await mocks.handler._verify_token(token) == user.email

    async def test_signin_issues_current_token_version(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        passwords: Passwords,
    ) -> None:
        user.token_version = 3
        signin = await mocks.handler.handle_signin(
            SignInUser(email=user.email, password=passwords.password)
        )

        assert (
            await mocks.handler._verify_token(signin.token.access_token) == user.email
        )
        assert signin.token.refresh_token
        refreshed = await mocks.handler.handle_refresh_token(signin.token.refresh_token)
        assert await mocks.handler._verify_token(refreshed.access_token) == user.email
