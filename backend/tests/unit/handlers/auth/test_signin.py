from unittest.mock import AsyncMock, Mock

import pytest
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError, EmailDeliveryError
from luml.schemas.auth import Token
from luml.schemas.user import (
    AuthProvider,
    CreateUser,
    CreateUserIn,
    CurrentUserOut,
    SignInResponse,
    SignInUser,
    UpdateUser,
    UpdateUserIn,
    User,
)
from pydantic import ValidationError

from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.auth.conftest import Passwords


class TestAuthSignIn:
    async def test_authenticate_user_returns_user(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
        passwords: Passwords,
    ) -> None:
        verify_password = Mock(return_value=True)
        monkeypatch.setattr(mocks.handler, "_verify_password", verify_password)
        mocks.user_repository.get_user.return_value = user

        actual = await mocks.handler._authenticate_user(user.email, passwords.password)

        assert actual == user
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)
        verify_password.assert_called_once_with(
            passwords.password, user.hashed_password
        )

    async def test_authenticate_user_raises_when_user_not_found(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        passwords: Passwords,
    ) -> None:
        mocks.user_repository.get_user.return_value = None

        with pytest.raises(AuthError, match="Invalid email or password") as error:
            await mocks.handler._authenticate_user(user.email, passwords.password)

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)

    async def test_authenticate_user_raises_when_auth_method_is_not_email(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        user: User,
        passwords: Passwords,
    ) -> None:
        user_with_google = user.model_copy()
        user_with_google.auth_method = AuthProvider.GOOGLE
        mocks.user_repository.get_user.return_value = user_with_google

        with pytest.raises(AuthError, match="Invalid auth method") as error:
            await mocks.handler._authenticate_user(
                user_with_google.email, passwords.password
            )

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_awaited_once_with(user_with_google.email)

    async def test_authenticate_user_raises_when_password_hash_missing(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        user_without_password = user.model_copy()
        user_without_password.hashed_password = None
        mocks.user_repository.get_user.return_value = user_without_password

        assert user_without_password, f"{user_without_password}..."

        with pytest.raises(AuthError, match="Password is invalid") as error:
            await mocks.handler._authenticate_user(
                user_without_password.email, "invalid_pass"
            )

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_awaited_once_with(
            user_without_password.email
        )

    async def test_authenticate_user_raises_when_password_not_verified(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
        passwords: Passwords,
    ) -> None:
        verify_password = Mock(return_value=False)
        monkeypatch.setattr(mocks.handler, "_verify_password", verify_password)
        mocks.user_repository.get_user.return_value = user

        with pytest.raises(AuthError, match="Invalid email or password") as error:
            await mocks.handler._authenticate_user(user.email, passwords.password)

        assert error.value.status_code == 401
        mocks.user_repository.get_user.assert_awaited_once_with(user.email)
        verify_password.assert_called_once_with(
            passwords.password, user.hashed_password
        )

    async def test_authenticate_user_raises_when_email_not_verified(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
        passwords: Passwords,
    ) -> None:
        unverified_user = user.model_copy()
        unverified_user.email_verified = False
        mocks.user_repository.get_user.return_value = unverified_user
        verify_password = Mock(return_value=True)
        monkeypatch.setattr(mocks.handler, "_verify_password", verify_password)

        with pytest.raises(AuthError, match="Email not verified") as error:
            await mocks.handler._authenticate_user(
                unverified_user.email, passwords.password
            )

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_awaited_once_with(unverified_user.email)
        verify_password.assert_called_once_with(
            passwords.password, unverified_user.hashed_password
        )

    async def test_handle_signup_creates_user_then_sends_activation_email(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        new_user_in: CreateUserIn,
        new_user: CreateUser,
        user: User,
    ) -> None:
        calls = Mock()
        calls.attach_mock(mocks.user_repository.create_user, "create_user")
        calls.attach_mock(
            mocks.emails_handler.send_activation_email, "send_activation_email"
        )
        get_password_hash = Mock(return_value=new_user.hashed_password)
        monkeypatch.setattr(mocks.handler, "_get_password_hash", get_password_hash)
        mocks.user_repository.get_user.return_value = None
        mocks.user_repository.create_user.return_value = user

        actual = await mocks.handler.handle_signup(new_user_in)

        assert actual == {"detail": "Please confirm your email address"}
        get_password_hash.assert_called_once_with(new_user_in.password)
        mocks.user_repository.get_user.assert_awaited_once_with(new_user.email)
        mocks.user_repository.create_user.assert_awaited_once_with(create_user=new_user)
        assert [name for name, _, _ in calls.mock_calls] == [
            "create_user",
            "send_activation_email",
        ]
        mocks.user_repository.delete_signup.assert_not_awaited()

    async def test_handle_signup_deletes_signup_when_activation_email_fails(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        new_user_in: CreateUserIn,
        new_user: CreateUser,
        user: User,
    ) -> None:
        monkeypatch.setattr(
            mocks.handler,
            "_get_password_hash",
            Mock(return_value=new_user.hashed_password),
        )
        mocks.user_repository.get_user.return_value = None
        mocks.user_repository.create_user.return_value = user
        mocks.emails_handler.send_activation_email.side_effect = RuntimeError(
            "email delivery failed"
        )

        with pytest.raises(EmailDeliveryError):
            await mocks.handler.handle_signup(new_user_in)

        mocks.user_repository.create_user.assert_awaited_once_with(create_user=new_user)
        mocks.user_repository.delete_signup.assert_awaited_once_with(user.id)

    async def test_handle_signup_does_not_send_email_when_commit_fails(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        new_user_in: CreateUserIn,
        new_user: CreateUser,
    ) -> None:
        monkeypatch.setattr(
            mocks.handler,
            "_get_password_hash",
            Mock(return_value=new_user.hashed_password),
        )
        mocks.user_repository.get_user.return_value = None
        mocks.user_repository.create_user.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await mocks.handler.handle_signup(new_user_in)

        mocks.emails_handler.send_activation_email.assert_not_called()
        mocks.user_repository.delete_signup.assert_not_awaited()

    async def test_handle_signup_raises_when_email_already_registered(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        new_user_in: CreateUserIn,
        new_user: CreateUser,
        passwords: Passwords,
    ) -> None:
        create_user = CreateUser(
            **new_user_in.model_dump(exclude={"password"}),
            hashed_password=passwords.hashed_password,
            auth_method=AuthProvider.EMAIL,
        )
        mocks.user_repository.get_user.return_value = new_user

        with pytest.raises(AuthError, match="Email already registered") as error:
            await mocks.handler.handle_signup(new_user_in)

        assert error.value.status_code == 400
        mocks.user_repository.get_user.assert_awaited_once_with(create_user.email)

    async def test_handle_signin_returns_tokens_and_user_id(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        new_user_in: CreateUserIn,
        user: User,
        tokens: Token,
    ) -> None:
        sign_in_user = SignInUser(
            email=new_user_in.email, password=new_user_in.password
        )
        expected = SignInResponse(token=tokens, user_id=user.id)
        authenticate_user = AsyncMock(return_value=user)
        create_tokens = Mock(return_value=tokens)
        monkeypatch.setattr(mocks.handler, "_authenticate_user", authenticate_user)
        monkeypatch.setattr(mocks.handler, "_create_tokens", create_tokens)

        actual = await mocks.handler.handle_signin(sign_in_user)

        assert actual == expected
        authenticate_user.assert_awaited_once_with(
            sign_in_user.email, sign_in_user.password
        )
        create_tokens.assert_called_once_with(new_user_in.email)

    async def test_update_user_updates_profile(
        self, mocks: CollaboratorMocks[AuthHandler], user: User
    ) -> None:
        email = "test@example.com"
        update_payload = UpdateUserIn(full_name="Updated Name")
        mocks.user_repository.get_user.return_value = user
        mocks.user_repository.update_user.return_value = True

        result = await mocks.handler.update_user(email, update_payload)

        assert result is True
        mocks.user_repository.get_user.assert_awaited_once_with(email)
        expected_update = UpdateUser(full_name="Updated Name", email=email)
        mocks.user_repository.update_user.assert_awaited_once_with(expected_update)

    async def test_update_user_raises_when_user_not_found(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        email = "test@example.com"
        update_payload = UpdateUserIn(full_name="Updated Name")
        mocks.user_repository.get_user.return_value = None

        with pytest.raises(AuthError, match="User not found") as exc:
            await mocks.handler.update_user(email, update_payload)

        assert exc.value.status_code == 404
        mocks.user_repository.get_user.assert_awaited_once_with(email)

    async def test_handle_delete_account_deletes_user(
        self, mocks: CollaboratorMocks[AuthHandler]
    ) -> None:
        email = "test@example.com"

        await mocks.handler.handle_delete_account(email)

        mocks.user_repository.delete_user.assert_awaited_once_with(email)

    async def test_handle_get_current_user_returns_user(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        current_user_out: CurrentUserOut,
    ) -> None:
        mocks.user_repository.get_current_user.return_value = current_user_out

        result = await mocks.handler.handle_get_current_user(current_user_out.email)

        assert result == current_user_out
        mocks.user_repository.get_current_user.assert_awaited_once_with(
            current_user_out.email
        )

    async def test_handle_get_current_user_raises_when_user_not_found(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        current_user_out: CurrentUserOut,
    ) -> None:
        mocks.user_repository.get_current_user.return_value = None

        with pytest.raises(AuthError, match="User not found") as error:
            await mocks.handler.handle_get_current_user(current_user_out.email)

        assert error.value.status_code == 404
        mocks.user_repository.get_current_user.assert_awaited_once_with(
            current_user_out.email
        )

    async def test_handle_get_current_user_raises_when_account_disabled(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        current_user_out: CurrentUserOut,
    ) -> None:
        disabled_user = current_user_out.model_copy()
        disabled_user.disabled = True
        mocks.user_repository.get_current_user.return_value = disabled_user

        with pytest.raises(AuthError, match="Account is disabled") as error:
            await mocks.handler.handle_get_current_user(disabled_user.email)

        assert error.value.status_code == 400
        mocks.user_repository.get_current_user.assert_awaited_once_with(
            disabled_user.email
        )

    def test_create_user_in_rejects_full_name_over_100_characters(self) -> None:
        long_name = "a" * 101
        with pytest.raises(ValidationError) as excinfo:
            CreateUserIn(
                email="test@example.com", password="password123", full_name=long_name
            )

        assert "String should have at most" in str(excinfo.value)
