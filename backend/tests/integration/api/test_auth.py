import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx2 import ASGITransport, AsyncClient
from luml.handlers.auth import AuthHandler
from luml.handlers.emails import EmailHandler
from luml.models import OrganizationMemberOrm, OrganizationOrm, UserOrm
from luml.repositories.users import UserRepository
from luml.schemas.user import CreateUser, CreateUserIn, User
from luml.service import AppService
from luml.settings import config
from pydantic import EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


async def test_concurrent_signup_with_same_email_returns_uniform_response(
    engine: AsyncEngine,
    new_user_in: CreateUserIn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = UserRepository(engine)
    get_user = repository.get_user
    checked_email = asyncio.Barrier(2)

    async def check_email(email: EmailStr) -> User | None:
        user = await get_user(email)
        await checked_email.wait()
        return user

    monkeypatch.setattr(repository, "get_user", check_email)
    monkeypatch.setattr(AuthHandler, "_AuthHandler__user_repository", repository)
    send_email = AsyncMock()
    monkeypatch.setattr(EmailHandler, "send_activation_email", send_email)

    async with AsyncClient(
        transport=ASGITransport(app=AppService(), raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        async with asyncio.timeout(10):
            responses = await asyncio.gather(
                *(
                    client.post(
                        "/v1/auth/signup", json=new_user_in.model_dump(mode="json")
                    )
                    for _ in range(2)
                )
            )

    assert [response.status_code for response in responses] == [200, 200]
    assert all(
        response.json() == {"detail": "Please confirm your email address"}
        for response in responses
    )
    send_email.assert_awaited_once()
    assert await get_user(new_user_in.email) is not None
    async with AsyncSession(engine) as session:
        for model in (UserOrm, OrganizationOrm, OrganizationMemberOrm):
            assert await session.scalar(select(func.count()).select_from(model)) == 1


@pytest.mark.parametrize("reset_password", [False, True], ids=["signup", "recovery"])
async def test_pending_signup_can_replace_predeployment_confirmation_link(
    engine: AsyncEngine,
    new_user: CreateUser,
    new_user_in: CreateUserIn,
    monkeypatch: pytest.MonkeyPatch,
    reset_password: bool,
) -> None:
    repository = UserRepository(engine)
    user = await repository.create_user(new_user)
    monkeypatch.setattr(AuthHandler, "_AuthHandler__user_repository", repository)
    send_activation = AsyncMock()
    send_reset = AsyncMock()
    monkeypatch.setattr(EmailHandler, "send_activation_email", send_activation)
    monkeypatch.setattr(EmailHandler, "send_password_reset_email", send_reset)
    handler = AuthHandler(secret_key=config.AUTH_SECRET_KEY)
    old_token = handler._create_token(
        {"sub": user.email, "type": "email_confirmation"}, expires_delta=86400
    )
    original_password_hash = user.hashed_password
    original_full_name = user.full_name

    async with AsyncClient(
        transport=ASGITransport(app=AppService()),
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as client:
        response = await client.get(
            "/v1/auth/confirm-email", params={"confirmation_token": old_token}
        )
        assert response.status_code == 400
        if reset_password:
            response = await client.post(
                "/v1/auth/forgot-password", json={"email": user.email}
            )
            assert response.status_code == 200
            args = send_reset.await_args
            assert args is not None
            reset_token = args.args[1].removeprefix(config.CHANGE_PASSWORD_URL)
            new_user_in.password = "recovered-password"
            response = await client.post(
                "/v1/auth/reset-password",
                json={
                    "reset_token": reset_token,
                    "new_password": new_user_in.password,
                },
            )
            assert response.status_code == 200
            updated_user = await repository.get_user(user.email)
            assert updated_user is not None
            assert updated_user.email_verified is False
            original_password_hash = updated_user.hashed_password

        new_user_in.full_name = "Different Name"
        response = await client.post(
            "/v1/auth/signup", json=new_user_in.model_dump(mode="json")
        )
        assert response.status_code == 200
        assert response.json() == {"detail": "Please confirm your email address"}
        send_activation.assert_awaited_once()
        args = send_activation.await_args
        assert args is not None
        confirmation_token = args.args[1].removeprefix(config.CONFIRM_EMAIL_URL)
        pending_user = await repository.get_user(user.email)
        assert pending_user is not None
        assert pending_user.id == user.id
        assert pending_user.email_version == user.email_version
        assert pending_user.hashed_password == original_password_hash
        assert pending_user.full_name == original_full_name
        assert pending_user.email_verified is False
        response = await client.get(
            "/v1/auth/confirm-email", params={"confirmation_token": confirmation_token}
        )
        assert response.status_code == 307
        confirmed_user = await repository.get_user(user.email)
        assert confirmed_user is not None
        assert confirmed_user.email_verified is True
        response = await client.post(
            "/v1/auth/signin",
            json={"email": user.email, "password": new_user_in.password},
        )
        assert response.status_code == 200
