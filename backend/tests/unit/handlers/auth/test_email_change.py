from time import time
from unittest.mock import ANY
from uuid import uuid4

import jwt
import pytest
from luml.handlers.auth import AuthHandler
from luml.infra.exceptions import AuthError, EmailDeliveryError
from luml.schemas.user import AuthProvider, ChangeEmailIn, EmailChange, User
from pydantic import ValidationError

from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.auth.conftest import Passwords


async def test_request_sends_bound_link_without_changing_email(
    mocks: CollaboratorMocks[AuthHandler], user: User, passwords: Passwords
) -> None:
    mocks.user_repository.get_user.return_value = user
    mocks.user_repository.email_exists.return_value = False
    result = await mocks.handler.handle_change_email(
        user.email,
        ChangeEmailIn(
            new_email="  NEW@Example.com  ", current_password=passwords.password
        ),
        expected_identity=(user.id, user.email_version),
    )
    assert result == {
        "detail": "If this address can be used, we have sent a confirmation link to it"
    }
    mocks.user_repository.update_user.assert_not_awaited()
    sent = mocks.emails_handler.send_email_change_confirmation.await_args.args
    assert sent[0] == "new@example.com"
    token = sent[1].split("token=")[1]
    payload = jwt.decode(token, mocks.handler.secret_key, algorithms=["HS256"])
    assert payload["uid"] == str(user.id)
    assert payload["sub"] == user.email
    assert payload["new_email"] == "new@example.com"
    assert payload["pwh"] == mocks.handler._password_fingerprint(user.hashed_password)
    assert 86390 < payload["exp"] - time() <= 86400


async def test_taken_and_free_addresses_have_identical_responses(
    mocks: CollaboratorMocks[AuthHandler], user: User, passwords: Passwords
) -> None:
    request = ChangeEmailIn(
        new_email="new@example.com", current_password=passwords.password
    )
    mocks.user_repository.get_user.return_value = user
    mocks.user_repository.email_exists.side_effect = [False, True]
    free = await mocks.handler.handle_change_email(
        user.email, request, expected_identity=(user.id, user.email_version)
    )
    taken = await mocks.handler.handle_change_email(
        user.email, request, expected_identity=(user.id, user.email_version)
    )
    assert free == taken
    mocks.emails_handler.send_email_change_confirmation.assert_awaited_once()


@pytest.mark.parametrize("scenario", ["password", "same", "same-case", "sso"])
async def test_invalid_request_sends_no_mail(
    mocks: CollaboratorMocks[AuthHandler],
    user: User,
    passwords: Passwords,
    scenario: str,
) -> None:
    if scenario == "same-case":
        user.email = user.email.upper()
    if scenario == "sso":
        user.auth_method = AuthProvider.GOOGLE
    mocks.user_repository.get_user.return_value = user
    request = ChangeEmailIn(
        new_email=user.email
        if scenario in {"same", "same-case"}
        else "new@example.com",
        current_password="wrong-password"
        if scenario == "password"
        else passwords.password,
    )
    with pytest.raises(AuthError):
        await mocks.handler.handle_change_email(
            user.email, request, expected_identity=(user.id, user.email_version)
        )
    mocks.emails_handler.send_email_change_confirmation.assert_not_awaited()


@pytest.mark.parametrize("email", ["bad", "", "a" * 255 + "@example.com"])
def test_invalid_new_email_is_rejected(email: str) -> None:
    with pytest.raises(ValidationError):
        ChangeEmailIn(new_email=email, current_password="password")


async def test_confirmation_delivery_failure_does_not_update_user(
    mocks: CollaboratorMocks[AuthHandler], user: User, passwords: Passwords
) -> None:
    mocks.user_repository.get_user.return_value = user
    mocks.user_repository.email_exists.return_value = False
    mocks.emails_handler.send_email_change_confirmation.side_effect = RuntimeError
    with pytest.raises(EmailDeliveryError):
        await mocks.handler.handle_change_email(
            user.email,
            ChangeEmailIn(
                new_email="new@example.com", current_password=passwords.password
            ),
            expected_identity=(user.id, user.email_version),
        )
    mocks.user_repository.update_user.assert_not_awaited()


async def test_confirmation_passes_expected_state_and_sends_masked_notice(
    mocks: CollaboratorMocks[AuthHandler], user: User
) -> None:
    token = mocks.handler._generate_email_change_token(user, "new@example.com")
    mocks.user_repository.get_user.return_value = user
    mocks.user_repository.change_email.return_value = True
    change = await mocks.handler.handle_confirm_email_change(token)
    mocks.user_repository.change_email.assert_awaited_once_with(
        user.id,
        user.email,
        "new@example.com",
        user.hashed_password,
        token,
        ANY,
        user.email_version,
    )
    assert change == EmailChange(
        old_email=user.email, new_email="new@example.com", full_name=user.full_name
    )
    mocks.emails_handler.send_email_changed_notice.assert_not_awaited()
    await mocks.handler.send_email_changed_notice(change)
    mocks.emails_handler.send_email_changed_notice.assert_awaited_once_with(
        user.email, "n***@example.com", user.full_name
    )


@pytest.mark.parametrize("change", ["password", "email", "id", "sso", "used"])
async def test_confirmation_rejects_changed_state(
    mocks: CollaboratorMocks[AuthHandler], user: User, change: str
) -> None:
    original = user.email
    token = mocks.handler._generate_email_change_token(user, "new@example.com")
    if change == "password":
        user.hashed_password = "changed"
    elif change == "email":
        user.email = "another@example.com"
    elif change == "id":
        user.id = uuid4()
    elif change == "sso":
        user.auth_method = AuthProvider.MICROSOFT
    mocks.user_repository.get_user.side_effect = lambda email: (
        user if email == original else None
    )
    mocks.user_repository.change_email.return_value = change != "used"
    with pytest.raises(AuthError):
        await mocks.handler.handle_confirm_email_change(token)
    mocks.emails_handler.send_email_changed_notice.assert_not_awaited()


@pytest.mark.parametrize("visit", ["again", "concurrently"])
async def test_confirmation_of_an_applied_link_succeeds_without_a_change(
    mocks: CollaboratorMocks[AuthHandler], user: User, visit: str
) -> None:
    token = mocks.handler._generate_email_change_token(user, "new@example.com")
    changed = user.model_copy(
        update={"email": "new@example.com", "email_version": uuid4()}
    )
    accounts = {"new@example.com": changed}
    if visit == "concurrently":
        accounts[user.email] = user
    mocks.user_repository.get_user.side_effect = accounts.get
    mocks.user_repository.change_email.return_value = False
    assert await mocks.handler.handle_confirm_email_change(token) is None
    if visit == "again":
        mocks.user_repository.change_email.assert_not_awaited()
    else:
        mocks.user_repository.change_email.assert_awaited_once()


@pytest.mark.parametrize("token", ["invalid", "expired", "wrong-purpose"])
async def test_confirmation_rejects_invalid_tokens(
    mocks: CollaboratorMocks[AuthHandler], user: User, token: str
) -> None:
    if token == "expired":
        token = mocks.handler._create_token(
            {"type": "email_change", "sub": user.email}, -1
        )
    elif token == "wrong-purpose":
        token = mocks.handler._generate_password_reset_token(user.email)
    with pytest.raises(AuthError):
        await mocks.handler.handle_confirm_email_change(token)
    mocks.user_repository.change_email.assert_not_awaited()


async def test_notice_failure_is_not_raised(
    mocks: CollaboratorMocks[AuthHandler], user: User
) -> None:
    mocks.emails_handler.send_email_changed_notice.side_effect = RuntimeError(
        "delivery failed"
    )
    await mocks.handler.send_email_changed_notice(
        EmailChange(old_email=user.email, new_email="new@example.com", full_name=None)
    )
    mocks.emails_handler.send_email_changed_notice.assert_awaited_once()
