from uuid import uuid4

import pytest
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError
from luml.schemas.user import ChangeEmailIn, ChangePasswordIn, UpdateUserIn, User

from tests.support.mocks import CollaboratorMocks


@pytest.mark.parametrize("operation", ["profile", "password", "email"])
@pytest.mark.parametrize("changed_field", ["id", "email_version"])
async def test_account_handlers_reject_changed_authenticated_identity(
    mocks: CollaboratorMocks[AuthHandler],
    user: User,
    operation: str,
    changed_field: str,
) -> None:
    identity = (user.id, user.email_version)
    setattr(user, changed_field, uuid4())
    mocks.user_repository.get_user.return_value = user

    if operation == "profile":
        call = mocks.handler.update_user(
            user.email,
            UpdateUserIn(full_name="Changed"),
            expected_identity=identity,
        )
    elif operation == "password":
        call = mocks.handler.handle_change_password(
            user.email,
            ChangePasswordIn(
                current_password="test_password", new_password="new-password"
            ),
            expected_identity=identity,
        )
    else:
        call = mocks.handler.handle_change_email(
            user.email,
            ChangeEmailIn(
                new_email="new@example.com", current_password="test_password"
            ),
            expected_identity=identity,
        )

    with pytest.raises(AuthError) as exc:
        await call

    assert exc.value.status_code == 401
    mocks.user_repository.update_user.assert_not_awaited()
    mocks.user_repository.update_password.assert_not_awaited()
    mocks.emails_handler.send_email_change_confirmation.assert_not_awaited()


async def test_profile_update_preserves_identity_at_final_mutation(
    mocks: CollaboratorMocks[AuthHandler], user: User
) -> None:
    mocks.user_repository.get_user.return_value = user
    identity = (user.id, user.email_version)
    await mocks.handler.update_user(
        user.email, UpdateUserIn(full_name="Changed"), expected_identity=identity
    )
    assert mocks.user_repository.update_user.await_args.kwargs == {
        "expected_identity": identity
    }


async def test_account_deletion_preserves_authenticated_identity(
    mocks: CollaboratorMocks[AuthHandler], user: User
) -> None:
    identity = (user.id, user.email_version)
    await mocks.handler.handle_delete_account(user.email, expected_identity=identity)
    mocks.user_repository.delete_user.assert_awaited_once_with(
        user.email, expected_identity=identity
    )
