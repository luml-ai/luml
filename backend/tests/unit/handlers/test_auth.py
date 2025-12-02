import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from time import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid7

import jwt
import pytest
import pytest_asyncio
from jwt.exceptions import InvalidTokenError

from dataforce_studio.handlers.auth import AuthHandler
from dataforce_studio.infra.exceptions import AuthError
from dataforce_studio.schemas.auth import OAuthLogin, Token, UserInfo
from dataforce_studio.schemas.user import (
    AuthProvider,
    CreateUser,
    CreateUserIn,
    SignInResponse,
    SignInUser,
    UpdateUser,
    UpdateUserIn,
    User,
    UserOut,
)
from dataforce_studio.services.oauth_providers import OAuthGoogleProvider

secret_key = "test"
algorithm = "HS256"

handler = AuthHandler(
    secret_key=secret_key, algorithm=algorithm, oauth_provider=OAuthGoogleProvider
)


@dataclass
class Passwords:
    password: str
    hashed_password: str


@pytest_asyncio.fixture(scope="function")
async def passwords() -> AsyncGenerator[Passwords]:
    yield Passwords(
        password="test_password",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$GZPWq5NMO1CsJrHq+EpiTA$E2QWHVvlRyMcPb4231Bh9pBhnjjENgeqYdb1M7lsIXs",
    )


@pytest.fixture
def get_tokens() -> Token:
    email = str(uuid.uuid4())
    now = int(time())
    access_payload = {"sub": email, "exp": now + 3600}
    refresh_payload = {
        "sub": email,
        "type": "refresh",
        "exp": now + 7200,
    }

    return Token(
        access_token=jwt.encode(access_payload, secret_key, algorithm=algorithm),
        refresh_token=jwt.encode(refresh_payload, secret_key, algorithm=algorithm),
        token_type="bearer",
    )


@patch.object(AuthHandler, "_password_hasher")
def test_get_password_hash(mock_password_hasher: Mock, passwords: Passwords) -> None:
    passwords_data = passwords
    mock_password_hasher.hash.return_value = "argon_hash"

    hashed_password_from_auth_handler = handler._get_password_hash(
        passwords_data.password
    )
    assert hashed_password_from_auth_handler == "argon_hash"
    mock_password_hasher.hash.assert_called_once_with(passwords_data.password)


def test_verify_password(passwords: Passwords) -> None:
    passwords_data = passwords

    actual = handler._verify_password(
        passwords_data.password, passwords_data.hashed_password
    )

    assert actual


@patch.object(AuthHandler, "_verify_password")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user(
    mock_get_user: AsyncMock,
    mock_verify_password: Mock,
    test_user: User,
    passwords: Passwords,
) -> None:
    passwords_data = passwords
    expected = test_user

    mock_verify_password.return_value = True
    mock_get_user.return_value = expected

    actual = await handler._authenticate_user(expected.email, passwords_data.password)

    assert actual == expected
    mock_get_user.assert_awaited_once_with(expected.email)
    mock_verify_password.assert_called_once_with(
        passwords_data.password, expected.hashed_password
    )


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_user_not_found(
    mock_get_user: AsyncMock, test_user: User, passwords: Passwords
) -> None:
    expected = test_user

    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="Invalid email or password") as error:
        await handler._authenticate_user(expected.email, passwords.password)

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_invalid_auth_method(
    mock_get_user: AsyncMock, test_user: User, passwords: Passwords
) -> None:
    user_with_google = test_user.model_copy()
    user_with_google.auth_method = AuthProvider.GOOGLE
    mock_get_user.return_value = user_with_google

    with pytest.raises(AuthError, match="Invalid auth method") as error:
        await handler._authenticate_user(user_with_google.email, passwords.password)

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(user_with_google.email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_password_is_invalid(
    mock_get_user: AsyncMock, test_user: User
) -> None:
    expected = test_user.model_copy()
    expected.hashed_password = None
    mock_get_user.return_value = expected

    assert expected, f"{expected}..."

    with pytest.raises(AuthError, match="Password is invalid") as error:
        await handler._authenticate_user(expected.email, "invalid_pass")

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)


@patch.object(AuthHandler, "_verify_password")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_password_not_verified(
    mock_get_user: AsyncMock,
    mock_verify_password: Mock,
    test_user: User,
    passwords: Passwords,
) -> None:
    expected = test_user

    mock_verify_password.return_value = False
    mock_get_user.return_value = expected

    with pytest.raises(AuthError, match="Invalid email or password") as error:
        await handler._authenticate_user(expected.email, passwords.password)

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)
    mock_verify_password.assert_called_once_with(
        passwords.password, expected.hashed_password
    )


@patch.object(AuthHandler, "_verify_password")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_email_not_verified(
    mock_get_user: AsyncMock,
    mock_verify_password: Mock,
    test_user: User,
    passwords: Passwords,
) -> None:
    expected = test_user.model_copy()
    expected.email_verified = False
    mock_get_user.return_value = expected
    mock_verify_password.return_value = True

    with pytest.raises(AuthError, match="Email not verified") as error:
        await handler._authenticate_user(expected.email, passwords.password)

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(expected.email)
    mock_verify_password.assert_called_once_with(
        passwords.password, expected.hashed_password
    )


@pytest.mark.asyncio
async def test_create_tokens() -> None:
    actual = handler._create_tokens("some_user_email@gmail.com")

    assert actual
    assert actual.access_token
    assert actual.refresh_token
    assert actual.token_type == "bearer"


@patch("dataforce_studio.handlers.auth.jwt.decode")
def test_verify_token_valid(mock_jwt_decode: MagicMock) -> None:
    email = "some_user_email@gmail.com"
    mock_jwt_decode.return_value = {"sub": email}

    actual = handler._verify_token("token")

    assert actual == email
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
def test_verify_token_cant_get_email(mock_jwt_decode: MagicMock) -> None:
    mock_jwt_decode.return_value = {"sub": None}

    with pytest.raises(AuthError, match="Invalid token") as exc_info:
        handler._verify_token("invalid_token")

    assert exc_info.value.status_code == 401
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
def test_verify_token_invalid_jwt(mock_jwt_decode: MagicMock) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError()

    with pytest.raises(AuthError, match="Invalid token") as exc_info:
        handler._verify_token("invalid_token")

    assert exc_info.value.status_code == 401
    mock_jwt_decode.assert_called_once()


@patch.object(AuthHandler, "_get_password_hash")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.create_user", new_callable=AsyncMock
)
@patch(
    "dataforce_studio.handlers.auth.EmailHandler.send_activation_email",
    new_callable=MagicMock,
)
@pytest.mark.asyncio
async def test_handle_signup(
    mock_send_activation_email: MagicMock,
    mock_create_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_get_password_hash: Mock,
    test_user_create_in: CreateUserIn,
    test_user_create: CreateUser,
    test_user: User,
) -> None:
    create_user_in = test_user_create_in
    create_user = test_user_create

    mock_get_user.return_value = None
    mock_get_password_hash.return_value = create_user.hashed_password
    mock_create_user.return_value = test_user

    actual = await handler.handle_signup(create_user_in)

    assert actual
    assert actual["detail"] == "Please confirm your email address"
    mock_send_activation_email.assert_called_once()
    mock_get_password_hash.assert_called_once_with(create_user_in.password)
    mock_get_user.assert_awaited_once_with(create_user.email)
    mock_create_user.assert_awaited_once_with(create_user=create_user)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_signup_already_exist(
    mock_get_user: AsyncMock,
    test_user_create_in: CreateUserIn,
    test_user_create: CreateUser,
    passwords: Passwords,
) -> None:
    create_user_in, user = test_user_create_in, test_user_create
    create_user = CreateUser(
        **create_user_in.model_dump(exclude={"password"}),
        hashed_password=passwords.hashed_password,
        auth_method=AuthProvider.EMAIL,
    )
    mock_get_user.return_value = user

    with pytest.raises(AuthError, match="Email already registered") as error:
        await handler.handle_signup(create_user_in)

    assert error.value.status_code == 400
    mock_get_user.assert_awaited_once_with(create_user.email)


@patch.object(AuthHandler, "_authenticate_user", new_callable=AsyncMock)
@patch.object(AuthHandler, "_create_tokens", new_callable=MagicMock)
@pytest.mark.asyncio
async def test_handle_signin(
    mock_create_tokens: MagicMock,
    mock_authenticate_user: AsyncMock,
    test_user_create_in: CreateUserIn,
    test_user: User,
    get_tokens: Token,
) -> None:
    create_user, user = test_user_create_in, test_user
    sign_in_user = SignInUser(email=create_user.email, password=create_user.password)
    expected = SignInResponse(token=get_tokens, user_id=user.id)

    mock_authenticate_user.return_value = user
    mock_create_tokens.return_value = get_tokens

    actual = await handler.handle_signin(sign_in_user)

    assert actual == expected
    mock_authenticate_user.assert_awaited_once_with(
        sign_in_user.email, sign_in_user.password
    )
    mock_create_tokens.assert_called_once_with(create_user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch.object(AuthHandler, "_create_tokens", new_callable=MagicMock)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.add_token",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_refresh_token(
    mock_add_token: AsyncMock,
    mock_is_token_blacklisted: AsyncMock,
    mock_get_user: AsyncMock,
    mock_create_tokens: MagicMock,
    mock_jwt_decode: MagicMock,
    test_user: User,
    get_tokens: Token,
) -> None:
    user = test_user
    tokens = get_tokens

    mock_jwt_decode.return_value = {
        "sub": user.email,
        "type": "refresh",
        "exp": int(time()) + 300,
    }
    mock_is_token_blacklisted.return_value = False
    mock_get_user.return_value = user
    mock_create_tokens.return_value = tokens

    assert tokens.refresh_token

    result = await handler.handle_refresh_token(tokens.refresh_token)

    assert result == tokens
    mock_is_token_blacklisted.assert_awaited_once_with(tokens.refresh_token)
    mock_get_user.assert_awaited_once_with(user.email)
    mock_add_token.assert_awaited_once()
    mock_create_tokens.assert_called_once_with(user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_refresh_token_type_isnt_refresh(
    mock_jwt_decode: MagicMock, test_user_create: CreateUser, get_tokens: Token
) -> None:
    user = test_user_create
    tokens = get_tokens

    mock_jwt_decode.return_value = {
        "sub": user.email,
        "type": "bearer",
        "exp": int(time()) + 300,
    }

    assert tokens.refresh_token

    with pytest.raises(AuthError, match="Invalid token type") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_refresh_token_email_is_none(
    mock_jwt_decode: MagicMock, get_tokens: Token
) -> None:
    tokens = get_tokens

    mock_jwt_decode.return_value = {
        "sub": None,
        "type": "refresh",
        "exp": int(time()) + 300,
    }

    assert tokens.refresh_token

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_refresh_token_has_been_revoked(
    mock_is_token_blacklisted: AsyncMock,
    mock_jwt_decode: MagicMock,
    test_user_create: CreateUser,
    get_tokens: Token,
) -> None:
    user = test_user_create
    tokens = get_tokens

    mock_jwt_decode.return_value = {
        "sub": user.email,
        "type": "refresh",
        "exp": int(time()) + 300,
    }
    mock_is_token_blacklisted.return_value = True

    assert tokens.refresh_token

    with pytest.raises(AuthError, match="Token has been revoked") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 400
    mock_is_token_blacklisted.assert_awaited_once_with(tokens.refresh_token)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_refresh_token_user_not_found(
    mock_is_token_blacklisted: AsyncMock,
    mock_get_user: AsyncMock,
    mock_jwt_decode: MagicMock,
    test_user: User,
    get_tokens: Token,
) -> None:
    user = test_user
    tokens = get_tokens

    mock_jwt_decode.return_value = {
        "sub": user.email,
        "type": "refresh",
        "exp": int(time()) + 300,
    }
    mock_is_token_blacklisted.return_value = False
    mock_get_user.return_value = None

    assert tokens.refresh_token

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_refresh_token(tokens.refresh_token)

    assert error.value.status_code == 404
    mock_is_token_blacklisted.assert_awaited_once_with(tokens.refresh_token)
    mock_get_user.assert_awaited_once_with(user.email)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_update_user(
    mock_update_user: AsyncMock, mock_get_user: AsyncMock, test_user: User
) -> None:
    email = "test@example.com"
    update_payload = UpdateUserIn(full_name="Updated Name")

    mock_get_user.return_value = test_user
    mock_update_user.return_value = True

    result = await handler.update_user(email, update_payload)

    assert result is True
    mock_get_user.assert_awaited_once_with(email)
    expected_update = UpdateUser(full_name="Updated Name", email=email)
    mock_update_user.assert_awaited_once_with(expected_update)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_update_user_not_found(mock_get_user: AsyncMock) -> None:
    email = "test@example.com"
    update_payload = UpdateUserIn(full_name="Updated Name")

    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as exc:
        await handler.update_user(email, update_payload)

    assert exc.value.status_code == 404
    mock_get_user.assert_awaited_once_with(email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.delete_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_handle_delete_account(mock_delete_user: AsyncMock) -> None:
    email = "test@example.com"

    await handler.handle_delete_account(email)

    mock_delete_user.assert_awaited_once_with(email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.get_public_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_get_current_user(
    mock_get_public_user: AsyncMock, test_user_out: UserOut
) -> None:
    user = test_user_out
    mock_get_public_user.return_value = user

    result = await handler.handle_get_current_user(user.email)

    assert result == user
    mock_get_public_user.assert_awaited_once_with(user.email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.get_public_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_get_current_user_not_found(
    mock_get_public_user: AsyncMock, test_user_out: UserOut
) -> None:
    user = test_user_out
    mock_get_public_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_get_current_user(user.email)

    assert error.value.status_code == 404
    mock_get_public_user.assert_awaited_once_with(user.email)


@patch(
    "dataforce_studio.handlers.auth.UserRepository.get_public_user",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_get_current_account_is_disabled(
    mock_get_public_user: AsyncMock, test_user_out: UserOut
) -> None:
    user = test_user_out.model_copy()
    user.disabled = True

    mock_get_public_user.return_value = user

    with pytest.raises(AuthError, match="Account is disabled") as error:
        await handler.handle_get_current_user(user.email)

    assert error.value.status_code == 400
    mock_get_public_user.assert_awaited_once_with(user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.add_token",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_handle_logout(mock_add_token: AsyncMock, mock_jwt_decode: Mock) -> None:
    access_token = "access.token"
    refresh_token = "refresh.token"

    mock_jwt_decode.side_effect = [{"exp": 12345}, {"exp": 67890}]

    await handler.handle_logout(access_token, refresh_token)

    assert mock_jwt_decode.call_count == 2
    mock_add_token.assert_any_await(access_token, 67890)
    mock_add_token.assert_any_await(refresh_token, 67890)
    assert mock_add_token.await_count == 2


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_logout_invalid_refresh_token(mock_jwt_decode: Mock) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError("Invalid refresh")

    with pytest.raises(AuthError, match="Invalid refresh token") as error:
        await handler.handle_logout(None, "token")

    assert error.value.status_code == 400


@patch(
    "dataforce_studio.services.oauth_providers.OAuthGoogleProvider.exchange_code_for_token",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.services.oauth_providers.OAuthGoogleProvider.get_user_info",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.auth.AuthHandler._create_tokens", new_callable=MagicMock
)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.create_user", new_callable=AsyncMock
)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_handle_oauth_google(
    mock_update_user: AsyncMock,
    mock_create_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_create_tokens: MagicMock,
    mock_get_user_info: AsyncMock,
    mock_exchange_code: AsyncMock,
    get_tokens: Token,
    test_user_create: CreateUser,
) -> None:
    created_user = User(
        id=uuid7(),
        email=test_user_create.email,
        full_name=test_user_create.full_name,
        email_verified=True,
        auth_method=AuthProvider.GOOGLE,
        photo="http://example.com/photo.jpg",
        hashed_password=None,
        disabled=False,
    )

    expected = OAuthLogin(token=get_tokens, user_id=created_user.id)

    mock_exchange_code.return_value = "access_token"
    mock_get_user_info.return_value = UserInfo(
        email=test_user_create.email,
        full_name=test_user_create.full_name,
        photo_url="http://example.com/photo.jpg",
    )

    mock_get_user.return_value = None
    mock_create_user.return_value = created_user
    mock_create_tokens.return_value = get_tokens

    result = await handler.handle_oauth("code")

    assert result == expected
    mock_exchange_code.assert_awaited_once()
    mock_get_user_info.assert_awaited_once()
    mock_create_user.assert_awaited_once()
    mock_create_tokens.assert_called_once_with(created_user.email)


@patch(
    "dataforce_studio.services.oauth_providers.OAuthGoogleProvider.exchange_code_for_token",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.services.oauth_providers.OAuthGoogleProvider.get_user_info",
    new_callable=AsyncMock,
)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.AuthHandler._create_tokens", new_callable=MagicMock
)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_oauth_updates_auth_method_for_existing_user(
    mock_update_user: AsyncMock,
    mock_create_tokens: MagicMock,
    mock_get_user: AsyncMock,
    mock_get_user_info: AsyncMock,
    mock_exchange_code: AsyncMock,
    get_tokens: Token,
) -> None:
    email = "user@example.com"
    photo = "http://example.com/photo.jpg"

    mock_exchange_code.return_value = "access_token"
    mock_get_user_info.return_value = UserInfo(
        email=email, full_name="Test User", photo_url=photo
    )

    mock_get_user.return_value = MagicMock(
        id=uuid.uuid4(), email=email, auth_method=AuthProvider.EMAIL, photo=photo
    )
    mock_create_tokens.return_value = get_tokens

    await handler.handle_oauth("code")

    mock_update_user.assert_awaited_once_with(
        UpdateUser(email=email, auth_method=AuthProvider.GOOGLE)
    )


@patch.object(AuthHandler, "_create_token")
def test_generate_password_reset_token(
    mock_create_token: MagicMock, test_user: User
) -> None:
    email = test_user.email

    mock_create_token.return_value = "test_token"
    actual = handler._generate_password_reset_token(email)

    assert actual == "test_token"
    mock_create_token.assert_called_once_with(
        data={"sub": email, "type": "password_reset"},
        expires_delta=3600,
    )


@patch(
    "dataforce_studio.handlers.auth.EmailHandler.send_password_reset_email",
    new_callable=MagicMock,
)
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch.object(AuthHandler, "_generate_password_reset_token")
@patch.object(AuthHandler, "_get_password_reset_link")
@pytest.mark.asyncio
async def test_send_password_reset_email(
    mock_get_password_reset_link: MagicMock,
    mock_generate_password_reset_token: MagicMock,
    mock_get_user: AsyncMock,
    mock_send_email: MagicMock,
    test_user: User,
) -> None:
    user = test_user
    token = "token"
    link = f"https://example.com/reset?token=${token}"

    mock_generate_password_reset_token.return_value = token
    mock_get_password_reset_link.return_value = link
    mock_get_user.return_value = user

    await handler.send_password_reset_email(user.email)

    mock_get_user.assert_awaited_once_with(user.email)
    mock_generate_password_reset_token.assert_called_once_with(user.email)
    mock_get_password_reset_link.assert_called_once_with(token)
    mock_send_email.assert_called_once_with(user.email, link, user.full_name)


@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_send_password_reset_email_user_not_found(
    mock_get_user: AsyncMock, test_user: User
) -> None:
    user = test_user
    mock_get_user.return_value = None

    await handler.send_password_reset_email(user.email)

    mock_get_user.assert_awaited_once_with(user.email)


@patch("dataforce_studio.handlers.auth.config.CHANGE_PASSWORD_URL", "https://test.com/")
def test_get_password_reset_link() -> None:
    token = "token"
    expected = "https://test.com/" + token

    actual = handler._get_password_reset_link(token)

    assert actual == expected


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@pytest.mark.asyncio
async def test_handle_email_confirmation(
    mock_update_user: AsyncMock,
    mock_get_user: AsyncMock,
    mock_jwt_decode: MagicMock,
    test_user: User,
) -> None:
    user = test_user.model_copy()
    user.email_verified = False

    mock_jwt_decode.return_value = {"sub": user.email}
    mock_get_user.return_value = user

    await handler.handle_email_confirmation("token")

    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once_with(user.email)
    mock_update_user.assert_awaited_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_email_confirmation_invalid_token(
    mock_jwt_decode: MagicMock,
) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError()

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_email_confirmation_cant_get_email(
    mock_jwt_decode: MagicMock,
) -> None:
    mock_jwt_decode.return_value = {"sub": None}

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 400


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_email_confirmation_user_not_found(
    mock_get_user: AsyncMock, mock_jwt_decode: MagicMock, test_user: User
) -> None:
    user = test_user
    mock_jwt_decode.return_value = {"sub": user.email}
    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 404
    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_email_confirmation_already_verified(
    mock_get_user: AsyncMock, mock_jwt_decode: MagicMock, test_user: User
) -> None:
    user = test_user
    user.email_verified = True

    mock_jwt_decode.return_value = {"sub": user.email}
    mock_get_user.return_value = user

    with pytest.raises(AuthError, match="Email already verified") as error:
        await handler.handle_email_confirmation("token")

    assert error.value.status_code == 400
    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@patch(
    "dataforce_studio.handlers.auth.UserRepository.update_user", new_callable=AsyncMock
)
@patch("dataforce_studio.handlers.auth.AuthHandler._get_password_hash")
@pytest.mark.asyncio
async def test_handle_reset_password(
    mock_hash: MagicMock,
    mock_update: AsyncMock,
    mock_get_user: AsyncMock,
    mock_jwt_decode: MagicMock,
    test_user: User,
) -> None:
    user = test_user
    new_password = "new_pass"
    update_user = UpdateUser(email=user.email, hashed_password=user.hashed_password)
    mock_jwt_decode.return_value = {"sub": user.email, "exp": int(time()) + 3600}
    mock_get_user.return_value = user
    mock_hash.return_value = user.hashed_password

    await handler.handle_reset_password("token", new_password)

    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once_with(user.email)
    mock_hash.assert_called_once_with(new_password)
    mock_update.assert_awaited_once_with(update_user)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_reset_expired(
    mock_jwt_decode: MagicMock, test_user_create: CreateUser
) -> None:
    user = test_user_create
    new_password = "new_pass"
    mock_jwt_decode.return_value = {"sub": user.email, "exp": None}

    with pytest.raises(AuthError, match="Token expired") as error:
        await handler.handle_reset_password("token", new_password)

    assert error.value.status_code == 400
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_reset_password_cant_get_email(mock_jwt_decode: MagicMock) -> None:
    new_password = "new_pass"
    mock_jwt_decode.return_value = {"sub": None, "exp": int(time()) + 3600}

    with pytest.raises(AuthError, match="Invalid token") as error:
        await handler.handle_reset_password("token", new_password)

    assert error.value.status_code == 400
    mock_jwt_decode.assert_called_once()


@patch("dataforce_studio.handlers.auth.jwt.decode")
@patch("dataforce_studio.handlers.auth.UserRepository.get_user", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_handle_reset_password_user_not_found(
    mock_get_user: AsyncMock, mock_jwt_decode: MagicMock, test_user: User
) -> None:
    user = test_user
    new_password = "new_pass"
    mock_jwt_decode.return_value = {"sub": user.email, "exp": int(time()) + 3600}
    mock_get_user.return_value = None

    with pytest.raises(AuthError, match="User not found") as error:
        await handler.handle_reset_password("token", new_password)

    assert error.value.status_code == 404
    mock_jwt_decode.assert_called_once()
    mock_get_user.assert_awaited_once_with(user.email)


@patch("dataforce_studio.handlers.auth.jwt.decode")
@pytest.mark.asyncio
async def test_handle_reset_password_invalid_token(mock_jwt_decode: MagicMock) -> None:
    mock_jwt_decode.side_effect = InvalidTokenError()

    with pytest.raises(AuthError, match="Invalid token") as exc:
        await handler.handle_reset_password("token", "new_pass")

    assert exc.value.status_code == 400
    mock_jwt_decode.assert_called_once()


@patch(
    "dataforce_studio.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_is_token_blacklisted(mock_is_token_blacklisted: AsyncMock) -> None:
    mock_is_token_blacklisted.return_value = True

    token = "token"

    result = await handler.is_token_blacklisted(token)

    assert result is True
    mock_is_token_blacklisted.assert_awaited_once_with(token)
