import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.auth import AuthHandler
from luml.handlers.emails import EmailHandler
from luml.models import OrganizationMemberOrm, OrganizationOrm, UserOrm
from luml.repositories.users import UserRepository
from luml.schemas.user import CreateUserIn, User
from luml.service import AppService
from pydantic import EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


async def test_concurrent_signup_with_same_email_returns_400(
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

    assert sorted(response.status_code for response in responses) == [200, 400]
    winner = next(response for response in responses if response.status_code == 200)
    loser = next(response for response in responses if response.status_code == 400)
    assert winner.json() == {"detail": "Please confirm your email address"}
    assert loser.json() == {"detail": "Email already registered"}
    send_email.assert_awaited_once()
    assert await get_user(new_user_in.email) is not None
    async with AsyncSession(engine) as session:
        for model in (UserOrm, OrganizationOrm, OrganizationMemberOrm):
            assert await session.scalar(select(func.count()).select_from(model)) == 1
