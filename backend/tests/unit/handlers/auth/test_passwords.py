from unittest.mock import Mock, patch

import pytest
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError
from luml.schemas.user import ChangePasswordIn, UpdateUser, User

from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.auth.conftest import Passwords


class TestAuthPasswords:
    def test_get_password_hash_returns_hasher_output(
        self, mocks: CollaboratorMocks[AuthHandler], passwords: Passwords
    ) -> None:
        with patch.object(AuthHandler, "_password_hasher") as mock_password_hasher:
            mock_password_hasher.hash.return_value = "argon_hash"

            hashed_password = mocks.handler._get_password_hash(passwords.password)

        assert hashed_password == "argon_hash"
        mock_password_hasher.hash.assert_called_once_with(passwords.password)

    def test_verify_password_returns_true_for_matching_hash(
        self, mocks: CollaboratorMocks[AuthHandler], passwords: Passwords
    ) -> None:
        actual = mocks.handler._verify_password(
            passwords.password, passwords.hashed_password
        )

        assert actual

    async def test_handle_change_password_stores_new_password_hash(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        mocks.user_repository.get_user.return_value = user
        passwords = ChangePasswordIn(
            current_password="current-password", new_password="new-password"
        )
        verify_password = Mock(return_value=True)
        get_password_hash = Mock(return_value="new-password-hash")
        monkeypatch.setattr(mocks.handler, "_verify_password", verify_password)
        monkeypatch.setattr(mocks.handler, "_get_password_hash", get_password_hash)

        await mocks.handler.handle_change_password(user.email, passwords)

        verify_password.assert_called_once_with(
            passwords.current_password, user.hashed_password
        )
        get_password_hash.assert_called_once_with(passwords.new_password)
        mocks.user_repository.update_user.assert_awaited_once_with(
            UpdateUser(email=user.email, hashed_password="new-password-hash")
        )

    async def test_handle_change_password_raises_when_current_password_invalid(
        self,
        mocks: CollaboratorMocks[AuthHandler],
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        mocks.user_repository.get_user.return_value = user
        passwords = ChangePasswordIn(
            current_password="invalid-password", new_password="new-password"
        )
        monkeypatch.setattr(mocks.handler, "_verify_password", Mock(return_value=False))

        with pytest.raises(AuthError, match="Invalid current password") as exc:
            await mocks.handler.handle_change_password(user.email, passwords)

        assert exc.value.status_code == 400
        mocks.user_repository.update_user.assert_not_awaited()
