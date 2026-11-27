import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from httpx2 import ASGITransport, AsyncClient
from luml.handlers.api_keys import APIKeyHandler
from luml.handlers.auth import AuthHandler
from luml.handlers.emails import EmailHandler
from luml.infra.exceptions import AuthError
from luml.models import UserOrm
from luml.repositories.token_blacklist import TokenBlackListRepository
from luml.repositories.users import UserRepository
from luml.schemas.user import AuthProvider, CreateUser
from luml.service import AppService
from luml.settings import config
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

PASSWORD = "original-password"
NEW_EMAIL = "new@example.com"


@pytest.fixture
async def client(
    engine: AsyncEngine, new_user: CreateUser, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    new_user.hashed_password = AuthHandler._get_password_hash(PASSWORD)
    new_user.email_verified = True
    await UserRepository(engine).create_user(new_user)
    monkeypatch.setattr(
        AuthHandler, "_AuthHandler__user_repository", UserRepository(engine)
    )
    monkeypatch.setattr(
        AuthHandler,
        "_AuthHandler__token_black_list_repository",
        TokenBlackListRepository(engine),
    )
    monkeypatch.setattr(
        APIKeyHandler, "_APIKeyHandler__user_repository", UserRepository(engine)
    )
    async with AsyncClient(
        transport=ASGITransport(app=AppService()),
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as client:
        response = await client.post(
            "/v1/auth/signin", json={"email": new_user.email, "password": PASSWORD}
        )
        assert response.status_code == 200
        yield client


@pytest.fixture
def mail(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    confirmation, notice = AsyncMock(), AsyncMock()
    monkeypatch.setattr(EmailHandler, "send_email_change_confirmation", confirmation)
    monkeypatch.setattr(EmailHandler, "send_email_changed_notice", notice)
    return confirmation, notice


async def request_change(
    client: AsyncClient, mail: tuple[AsyncMock, AsyncMock], email: str = NEW_EMAIL
) -> str:
    response = await client.post(
        "/v1/auth/change-email", json={"new_email": email, "current_password": PASSWORD}
    )
    assert response.status_code == 200
    assert mail[0].await_args is not None
    return parse_qs(urlparse(mail[0].await_args.args[1]).query)["token"][0]


async def confirm(client: AsyncClient, token: str) -> str:
    response = await client.get(
        "/v1/auth/confirm-email-change", params={"token": token}
    )
    assert response.status_code == 307
    location = urlparse(response.headers["location"])
    assert location._replace(query="").geturl() == config.CHANGE_EMAIL_REDIRECT_URL
    return parse_qs(location.query)["status"][0]


async def test_email_changes_on_link_visit_and_revokes_two_sessions(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
) -> None:
    sessions = [(client.cookies["access_token"], client.cookies["refresh_token"])]
    response = await client.post(
        "/v1/auth/signin", json={"email": new_user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    sessions.append((client.cookies["access_token"], client.cookies["refresh_token"]))
    token = await request_change(client, mail, "  New@Example.com  ")
    assert (await UserRepository(engine).get_user(new_user.email)) is not None
    assert (
        await client.post(
            "/v1/auth/signin", json={"email": new_user.email, "password": PASSWORD}
        )
    ).status_code == 200
    assert await confirm(client, token) == "changed"
    assert "access_token" not in client.cookies
    assert "refresh_token" not in client.cookies
    changed = await UserRepository(engine).get_user(NEW_EMAIL)
    assert changed is not None
    assert changed.email_verified
    mail[1].assert_awaited_once_with(
        new_user.email, "n***@example.com", new_user.full_name
    )
    for access, refresh in sessions:
        response = await client.get(
            "/v1/auth/users/me", headers={"Authorization": f"Bearer {access}"}
        )
        assert response.status_code == 401
        response = await client.post(
            "/v1/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"}
        )
        assert response.status_code == 401
    assert (
        await client.post(
            "/v1/auth/signin", json={"email": NEW_EMAIL, "password": PASSWORD}
        )
    ).status_code == 200
    assert (
        await client.post(
            "/v1/auth/signin", json={"email": new_user.email, "password": PASSWORD}
        )
    ).status_code != 200
    assert await confirm(client, token) == "changed"
    mail[1].assert_awaited_once()


@pytest.mark.parametrize("reason", ["password", "another-change", "expired"])
async def test_stale_confirmation_leaves_identity_unchanged(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
    reason: str,
) -> None:
    token = await request_change(client, mail)
    if reason == "password":
        response = await client.post(
            "/v1/auth/change-password",
            json={"current_password": PASSWORD, "new_password": "replacement-password"},
        )
        assert response.status_code == 200
    elif reason == "another-change":
        other = await request_change(client, mail, "other@example.com")
        assert await confirm(client, other) == "changed"
    else:
        handler = AuthHandler(config.AUTH_SECRET_KEY)
        import jwt

        payload = jwt.decode(token, config.AUTH_SECRET_KEY, algorithms=["HS256"])
        token = handler._create_token(payload, -1)
    assert await confirm(client, token) == "invalid"
    assert await UserRepository(engine).get_user(NEW_EMAIL) is None


@pytest.mark.parametrize("stored_email", [NEW_EMAIL, "New@example.com"])
async def test_taken_address_responses_match_and_unverified_accounts_block_confirmation(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
    stored_email: str,
) -> None:
    response = await client.post(
        "/v1/auth/change-email",
        json={"new_email": NEW_EMAIL, "current_password": PASSWORD},
    )
    assert mail[0].await_args is not None
    token = parse_qs(urlparse(mail[0].await_args.args[1]).query)["token"][0]
    await UserRepository(engine).create_user(
        new_user.model_copy(update={"email": stored_email, "email_verified": False})
    )
    taken = await client.post(
        "/v1/auth/change-email",
        json={"new_email": NEW_EMAIL, "current_password": PASSWORD},
    )
    assert taken.status_code == response.status_code == 200
    assert taken.json() == response.json()
    mail[0].assert_awaited_once()
    assert await confirm(client, token) == "in-use"
    assert (await UserRepository(engine).get_user(new_user.email)) is not None
    mail[1].assert_not_awaited()


async def test_replacement_account_cannot_use_old_identity_tokens(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
) -> None:
    access, refresh = client.cookies["access_token"], client.cookies["refresh_token"]
    handler = AuthHandler(config.AUTH_SECRET_KEY)
    user = await UserRepository(engine).get_user(new_user.email)
    assert user is not None
    reset = handler._generate_password_reset_token(
        user.email, user.id, user.email_version
    )
    activation = handler._generate_email_confirmation_token(
        user.email, user.id, user.email_version
    )
    token = await request_change(client, mail)
    assert await confirm(client, token) == "changed"
    replacement = await UserRepository(engine).create_user(
        new_user.model_copy(update={"email_verified": False})
    )
    assert replacement.id != user.id
    assert (
        await client.get(
            "/v1/auth/users/me", headers={"Authorization": f"Bearer {access}"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/v1/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"}
        )
    ).status_code == 401
    with pytest.raises(AuthError):
        await handler.handle_email_confirmation(activation)
    assert (
        await client.post(
            "/v1/auth/reset-password",
            json={"reset_token": reset, "new_password": "different-password"},
        )
    ).status_code == 400
    after = await UserRepository(engine).get_user(new_user.email)
    assert after is not None
    assert not after.email_verified
    assert after.hashed_password == replacement.hashed_password


async def test_simultaneous_confirmations_have_one_winner(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
) -> None:
    first = await request_change(client, mail)
    second = await request_change(client, mail, "other@example.com")
    outcomes = await asyncio.gather(*(confirm(client, t) for t in [first, second]))
    assert sorted(outcomes) == ["changed", "invalid"]
    assert await UserRepository(engine).get_user(new_user.email) is None
    mail[1].assert_awaited_once()


async def test_a_scanner_and_the_person_opening_one_link_both_see_success(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
) -> None:
    token = await request_change(client, mail)
    outcomes = await asyncio.gather(*(confirm(client, token) for _ in range(2)))
    assert outcomes == ["changed", "changed"]
    assert await UserRepository(engine).get_user(NEW_EMAIL) is not None
    mail[1].assert_awaited_once()


async def test_sso_request_is_rejected_and_auth_request_is_limited(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
) -> None:
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            update(UserOrm)
            .where(UserOrm.email == new_user.email)
            .values(auth_method=AuthProvider.GOOGLE)
        )
    for _ in range(5):
        response = await client.post(
            "/v1/auth/change-email",
            json={"new_email": NEW_EMAIL, "current_password": PASSWORD},
        )
        assert response.status_code == 400
    response = await client.post(
        "/v1/auth/change-email",
        json={"new_email": NEW_EMAIL, "current_password": PASSWORD},
    )
    assert response.status_code == 429
    mail[0].assert_not_awaited()


async def test_api_key_members_and_invitations_keep_the_same_user(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from luml.handlers.organizations import OrganizationHandler
    from luml.infra.exceptions import InsufficientPermissionsError
    from luml.repositories.invites import InviteRepository
    from luml.schemas.organization import CreateOrganizationInvite, OrgRole

    repository = UserRepository(engine)
    invite_repository = InviteRepository(engine)
    monkeypatch.setattr(
        OrganizationHandler, "_OrganizationHandler__user_repository", repository
    )
    monkeypatch.setattr(
        OrganizationHandler,
        "_OrganizationHandler__invites_repository",
        invite_repository,
    )
    user = await repository.get_user(new_user.email)
    assert user is not None
    owner = await repository.create_user(
        new_user.model_copy(update={"email": "owner@example.com"})
    )
    organizations = await repository.get_user_organizations(owner.id)
    organization_id = organizations[0].id
    invites = [
        await invite_repository.create_organization_invite(
            CreateOrganizationInvite(
                email=email,
                organization_id=organization_id,
                invited_by=owner.id,
                role=OrgRole.MEMBER,
            )
        )
        for email in [new_user.email, NEW_EMAIL]
    ]
    key = await APIKeyHandler().create_user_api_key(user.id)
    assert key.key is not None
    token = await request_change(client, mail)
    assert await confirm(client, token) == "changed"
    response = await client.get(
        "/v1/auth/api-keys/validate", headers={"Authorization": f"Bearer {key.key}"}
    )
    assert response.status_code == 204
    authenticated = await APIKeyHandler().authenticate_api_key(key.key)
    assert authenticated is not None
    assert authenticated.id == user.id
    assert authenticated.email == NEW_EMAIL
    handler = OrganizationHandler()
    with pytest.raises(
        InsufficientPermissionsError, match="This invite is not for you"
    ):
        await handler.accept_invite(invites[0].id, user.id, NEW_EMAIL)
    assert await invite_repository.get_invite(invites[0].id) is not None
    await handler.accept_invite(invites[1].id, user.id, NEW_EMAIL)
    members = await repository.get_organization_members(organization_id)
    member = next(member for member in members if member.user.id == user.id)
    assert member.user.email == NEW_EMAIL
    assert await invite_repository.get_invite(invites[0].id) is not None


async def test_returning_to_old_email_does_not_revive_any_old_tokens(
    client: AsyncClient,
    engine: AsyncEngine,
    new_user: CreateUser,
    mail: tuple[AsyncMock, AsyncMock],
) -> None:
    repository = UserRepository(engine)
    user = await repository.get_user(new_user.email)
    assert user is not None
    handler = AuthHandler(config.AUTH_SECRET_KEY)
    access, refresh = client.cookies["access_token"], client.cookies["refresh_token"]
    reset = handler._generate_password_reset_token(
        user.email, user.id, user.email_version
    )
    activation = handler._generate_email_confirmation_token(
        user.email, user.id, user.email_version
    )
    first = await request_change(client, mail)
    sibling = await request_change(client, mail, "third@example.com")
    assert await confirm(client, first) == "changed"
    assert (
        await client.post(
            "/v1/auth/signin", json={"email": NEW_EMAIL, "password": PASSWORD}
        )
    ).status_code == 200
    back = await request_change(client, mail, user.email)
    assert await confirm(client, back) == "changed"
    assert (
        await client.get(
            "/v1/auth/users/me", headers={"Authorization": f"Bearer {access}"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/v1/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"}
        )
    ).status_code == 401
    assert await confirm(client, sibling) == "invalid"
    with pytest.raises(AuthError):
        await handler.handle_email_confirmation(activation)
    assert (
        await client.post(
            "/v1/auth/reset-password",
            json={"reset_token": reset, "new_password": "different-password"},
        )
    ).status_code == 400
    unchanged = await repository.get_user(user.email)
    assert unchanged is not None
    assert unchanged.id == user.id
    assert unchanged.email_version != user.email_version
    assert unchanged.hashed_password == user.hashed_password
    assert (
        await client.post(
            "/v1/auth/signin", json={"email": user.email, "password": PASSWORD}
        )
    ).status_code == 200
