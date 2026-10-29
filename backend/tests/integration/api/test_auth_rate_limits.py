from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from luml.api.auth import auth_router
from luml.api.platform_admin import platform_admin_routers
from luml.handlers.auth import AuthHandler
from luml.settings import config


@pytest.mark.parametrize(
    ("path", "body", "handler"),
    [
        (
            "/auth/signin",
            {"email": "user@example.com", "password": "wrong-password"},
            "luml.api.auth.auth_handler.handle_signin",
        ),
        (
            "/auth/signup",
            {"email": "user@example.com", "password": "password"},
            "luml.api.auth.auth_handler.handle_signup",
        ),
        (
            "/auth/forgot-password",
            {"email": "user@example.com"},
            "luml.api.auth.auth_handler.send_password_reset_email",
        ),
        (
            "/auth/reset-password",
            {"new_password": "password"},
            "luml.api.auth.auth_handler.handle_reset_password",
        ),
        (
            "/platform-admin/auth/token",
            {
                "grant_type": "password",
                "email": "user@example.com",
                "password": "wrong-password",
            },
            "luml.api.platform_admin.platform_admin_auth_handler.issue_token",
        ),
    ],
)
async def test_email_limit_survives_changing_ip(
    path: str, body: dict[str, str], handler: str
) -> None:
    app = FastAPI()
    app.include_router(auth_router, prefix="/v1")
    app.include_router(platform_admin_routers, prefix="/v1")
    body = body.copy()
    if path.endswith("reset-password") and "forgot" not in path:
        body["reset_token"] = AuthHandler(
            secret_key=config.AUTH_SECRET_KEY
        )._generate_password_reset_token("user@example.com")

    with (
        patch(
            handler, new_callable=AsyncMock, side_effect=HTTPException(401)
        ) as handle,
    ):
        for index in range(6):
            transport = httpx.ASGITransport(app=app, client=(f"192.0.2.{index}", 1234))
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(f"/v1{path}", json=body)
            assert response.status_code == (401 if index < 5 else 429)
        assert handle.await_count == 5
        assert 0 < int(response.headers["Retry-After"]) <= 60


async def test_ip_limit_survives_changing_email_and_forwarded_headers() -> None:
    app = FastAPI()
    app.include_router(auth_router, prefix="/v1")
    with (
        patch(
            "luml.api.auth.auth_handler.send_password_reset_email",
            new_callable=AsyncMock,
        ) as handle,
    ):
        transport = httpx.ASGITransport(app=app, client=("192.0.2.1", 1234))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            for index in range(21):
                response = await client.post(
                    "/v1/auth/forgot-password",
                    json={"email": f"user{index}@example.com"},
                    headers={"X-Forwarded-For": f"192.0.2.{index}"},
                )
                assert response.status_code == (200 if index < 20 else 429)
        assert handle.await_count == 20
