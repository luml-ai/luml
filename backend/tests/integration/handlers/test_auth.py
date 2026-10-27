import asyncio
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.auth import AuthHandler
from luml.repositories.token_blacklist import TokenBlackListRepository
from luml.repositories.users import UserRepository
from luml.schemas.user import CreateUser
from luml.service import AppService
from luml.settings import config
from sqlalchemy.ext.asyncio import AsyncEngine

PASSWORD = "original-password"
NEW_PASSWORD = "replacement-password"


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
    async with AsyncClient(
        transport=ASGITransport(app=AppService()),
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as client:
        yield client


async def signin(client: AsyncClient, email: str, password: str) -> tuple[str, str]:
    response = await client.post(
        "/v1/auth/signin", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    return client.cookies["access_token"], client.cookies["refresh_token"]


class TestPasswordSecurity:
    @pytest.mark.parametrize("reset", [False, True], ids=["change", "reset"])
    async def test_password_update_revokes_all_old_sessions(
        self, client: AsyncClient, new_user: CreateUser, reset: bool
    ) -> None:
        access, refresh = await signin(client, new_user.email, PASSWORD)
        handler = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY,
            access_token_expire=3600,
            refresh_token_expire=7200,
        )
        other_sessions = handler._create_tokens(new_user.email)
        if reset:
            response = await client.post(
                "/v1/auth/reset-password",
                json={
                    "reset_token": handler._generate_password_reset_token(
                        new_user.email
                    ),
                    "new_password": NEW_PASSWORD,
                },
            )
        else:
            response = await client.post(
                "/v1/auth/change-password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
        assert response.status_code == 200

        if reset:
            assert (await client.get("/v1/auth/users/me")).status_code == 401
        else:
            assert client.cookies["access_token"] != access
            assert client.cookies["refresh_token"] != refresh
            assert (await client.get("/v1/auth/users/me")).status_code == 200
            assert (await client.post("/v1/auth/refresh")).status_code == 200
        for token in [access, other_sessions.access_token]:
            response = await client.get(
                "/v1/auth/users/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401
        for refresh_token in [refresh, other_sessions.refresh_token]:
            assert refresh_token
            client.cookies.clear()
            client.cookies.set("refresh_token", refresh_token)
            response = await client.post("/v1/auth/refresh")
            assert response.status_code == 400

        client.cookies.clear()
        await signin(client, new_user.email, NEW_PASSWORD)
        assert (await client.get("/v1/auth/users/me")).status_code == 200
        assert (await client.post("/v1/auth/refresh")).status_code == 200

    async def test_reset_token_cannot_be_reused(
        self, client: AsyncClient, new_user: CreateUser
    ) -> None:
        token = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY
        )._generate_password_reset_token(new_user.email)
        response = await client.post(
            "/v1/auth/reset-password",
            json={"reset_token": token, "new_password": NEW_PASSWORD},
        )
        assert response.status_code == 200
        response = await client.post(
            "/v1/auth/reset-password",
            json={"reset_token": token, "new_password": "another-password"},
        )
        assert response.status_code == 400
        await signin(client, new_user.email, NEW_PASSWORD)

    async def test_concurrent_reset_token_use_only_succeeds_once(
        self, client: AsyncClient, new_user: CreateUser
    ) -> None:
        token = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY
        )._generate_password_reset_token(new_user.email)
        responses = await asyncio.gather(
            *(
                client.post(
                    "/v1/auth/reset-password",
                    json={"reset_token": token, "new_password": password},
                )
                for password in [NEW_PASSWORD, "another-password"]
            )
        )
        assert sorted(response.status_code for response in responses) == [200, 400]
        winner = [NEW_PASSWORD, "another-password"][
            next(
                i for i, response in enumerate(responses) if response.status_code == 200
            )
        ]
        await signin(client, new_user.email, winner)

    async def test_profile_cannot_change_password(
        self, client: AsyncClient, new_user: CreateUser
    ) -> None:
        await signin(client, new_user.email, PASSWORD)
        response = await client.patch(
            "/v1/auth/users/me", json={"password": NEW_PASSWORD}
        )
        assert response.status_code == 422
        await signin(client, new_user.email, PASSWORD)

    @pytest.mark.parametrize("current", [None, "incorrect-password"])
    async def test_change_requires_correct_current_password(
        self, client: AsyncClient, new_user: CreateUser, current: str | None
    ) -> None:
        await signin(client, new_user.email, PASSWORD)
        payload = {"new_password": NEW_PASSWORD}
        if current is not None:
            payload["current_password"] = current
        response = await client.post("/v1/auth/change-password", json=payload)
        assert response.status_code == (422 if current is None else 400)
        assert (await client.get("/v1/auth/users/me")).status_code == 200
        await signin(client, new_user.email, PASSWORD)

    async def test_failed_password_write_does_not_consume_reset_token(
        self, client: AsyncClient, new_user: CreateUser
    ) -> None:
        token = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY
        )._generate_password_reset_token(new_user.email)
        payload = {"reset_token": token, "new_password": NEW_PASSWORD}
        with (
            patch(
                "luml.repositories.users.update",
                side_effect=RuntimeError("write failed"),
            ),
            pytest.raises(RuntimeError, match="write failed"),
        ):
            await client.post("/v1/auth/reset-password", json=payload)

        response = await client.post("/v1/auth/reset-password", json=payload)
        assert response.status_code == 200
        await signin(client, new_user.email, NEW_PASSWORD)
