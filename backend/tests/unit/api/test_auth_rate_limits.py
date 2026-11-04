from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.auth import auth_router
from luml.api.platform_admin import platform_admin_routers
from luml.handlers.auth import AuthHandler
from luml.settings import config


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(auth_router, prefix="/v1")
    app.include_router(platform_admin_routers, prefix="/v1")
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "body", "handler"),
    [
        (
            "/auth/signin",
            {"email": "u@example.com", "password": "password"},
            "luml.api.auth.auth_handler.handle_signin",
        ),
        (
            "/auth/signup",
            {"email": "u@example.com", "password": "password"},
            "luml.api.auth.auth_handler.handle_signup",
        ),
        (
            "/auth/forgot-password",
            {"email": "u@example.com"},
            "luml.api.auth.auth_handler.send_password_reset_email",
        ),
        (
            "/auth/reset-password",
            {"reset_token": "invalid", "new_password": "password"},
            "luml.api.auth.auth_handler.handle_reset_password",
        ),
        (
            "/platform-admin/auth/token",
            {
                "grant_type": "password",
                "email": "u@example.com",
                "password": "password",
            },
            "luml.api.platform_admin.platform_admin_auth_handler.issue_token",
        ),
    ],
)
def test_limited_requests_do_not_reach_handlers(
    client: TestClient, path: str, body: dict[str, str], handler: str
) -> None:
    with (
        patch(
            "luml.infra.auth_rate_limits.limiter.consume",
            new_callable=AsyncMock,
            return_value=42,
        ) as consume,
        patch(handler, new_callable=AsyncMock) as handle,
    ):
        response = client.post(f"/v1{path}", json=body)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.json() == {"detail": "Too many authentication attempts"}
    handle.assert_not_awaited()
    consume.assert_awaited_once()


def test_email_limits_ignore_case_and_forwarded_headers(client: TestClient) -> None:
    with (
        patch(
            "luml.infra.auth_rate_limits.limiter.consume",
            new_callable=AsyncMock,
            return_value=0,
        ) as consume,
        patch(
            "luml.api.auth.auth_handler.send_password_reset_email",
            new_callable=AsyncMock,
        ),
    ):
        for email, forwarded in [
            ("User@example.com", "1.2.3.4"),
            ("user@example.com", "5.6.7.8"),
        ]:
            assert (
                client.post(
                    "/v1/auth/forgot-password",
                    json={"email": email},
                    headers={"X-Forwarded-For": forwarded},
                ).status_code
                == 200
            )

    assert consume.await_args_list[0] == consume.await_args_list[1]
    limits = consume.await_args_list[0].args[0]
    assert sorted(limits.values()) == [5, 20]
    assert all("example.com" not in key for key in limits)


def test_reset_limits_use_only_verified_password_reset_identity(
    client: TestClient,
) -> None:
    handler = AuthHandler(secret_key=config.AUTH_SECRET_KEY)
    valid_token = handler._generate_password_reset_token("user@example.com")
    wrong_type = handler._create_tokens("user@example.com").access_token
    forged_token = AuthHandler(secret_key="wrong-key")._generate_password_reset_token(
        "user@example.com"
    )
    with (
        patch(
            "luml.infra.auth_rate_limits.limiter.consume",
            new_callable=AsyncMock,
            return_value=42,
        ) as consume,
    ):
        for token in [valid_token, wrong_type, forged_token, "invalid"]:
            assert (
                client.post(
                    "/v1/auth/reset-password",
                    json={"reset_token": token, "new_password": "password"},
                ).status_code
                == 429
            )
    assert [len(call.args[0]) for call in consume.await_args_list] == [2, 1, 1, 1]


def test_google_code_grant_is_unchanged(client: TestClient) -> None:
    from luml.schemas.platform_admin import PlatformAdminToken

    with (
        patch(
            "luml.infra.auth_rate_limits.limiter.consume", new_callable=AsyncMock
        ) as consume,
        patch(
            "luml.api.platform_admin.platform_admin_auth_handler.issue_token",
            new_callable=AsyncMock,
            return_value=PlatformAdminToken(access_token="token", expires_in=60),
        ),
    ):
        response = client.post(
            "/v1/platform-admin/auth/token",
            json={
                "grant_type": "google_code",
                "code": "code",
                "code_verifier": "v" * 43,
            },
        )
    assert response.status_code == 200
    consume.assert_not_awaited()


def test_limits_are_disabled_without_redis_url(client: TestClient) -> None:
    with (
        patch("luml.infra.auth_rate_limits.limiter", None),
        patch(
            "luml.api.auth.auth_handler.send_password_reset_email",
            new_callable=AsyncMock,
        ) as handle,
    ):
        response = client.post(
            "/v1/auth/forgot-password", json={"email": "u@example.com"}
        )

    assert response.status_code == 200
    handle.assert_awaited_once()
