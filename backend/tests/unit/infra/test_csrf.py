from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.infra.middleware import CookieCSRFMiddleware


@pytest.fixture
def csrf_client() -> Iterator[TestClient]:
    app = FastAPI()
    app.add_middleware(
        CookieCSRFMiddleware,
        allowed_origins=["https://app.luml.ai", "https://dev.luml.ai", "*", "null"],
    )

    @app.api_route(
        "/{path:path}",
        methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
    )
    def endpoint(path: str) -> dict[str, str]:
        return {"path": path}

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "origin",
    [
        None,
        "https://evil.example",
        "null",
        "https://app.luml.ai.evil.example",
        "https://testserver",
        "http://testserver:81",
    ],
)
def test_cookie_mutations_reject_untrusted_or_missing_origin(
    csrf_client: TestClient, method: str, origin: str | None
) -> None:
    csrf_client.cookies.set("access_token", "cookie-token")
    headers = {"Origin": origin} if origin is not None else {}
    headers["Referer"] = "https://app.luml.ai/"

    response = csrf_client.request(method, "/resource", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF origin check failed"}


@pytest.mark.parametrize("cookie", ["access_token", "refresh_token"])
@pytest.mark.parametrize("origin", ["http://testserver", "https://app.luml.ai"])
def test_cookie_mutations_allow_same_or_configured_origin(
    csrf_client: TestClient, cookie: str, origin: str
) -> None:
    csrf_client.cookies.set(cookie, "cookie-token")

    response = csrf_client.post("/resource", headers={"Origin": origin})

    assert response.status_code == 200


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_cookie_requests_need_no_origin(
    csrf_client: TestClient, method: str
) -> None:
    csrf_client.cookies.set("access_token", "cookie-token")

    assert csrf_client.request(method, "/resource").status_code == 200


@pytest.mark.parametrize("token", ["jwt-token", "dfs_api-key", "dfssat_key"])
def test_header_authentication_does_not_require_csrf_origin(
    csrf_client: TestClient, token: str
) -> None:
    csrf_client.cookies.set("access_token", "unused-cookie")

    response = csrf_client.post(
        "/resource",
        headers={"Authorization": f"Bearer {token}", "Origin": "https://evil.example"},
    )

    assert response.status_code == 200


def test_requests_without_session_cookies_need_no_origin(
    csrf_client: TestClient,
) -> None:
    assert csrf_client.post("/resource").status_code == 200


@pytest.mark.parametrize("path", ["/v1/auth/refresh", "/v1/auth/logout"])
@pytest.mark.parametrize("authorization", [None, "Bearer ignored-token"])
def test_refresh_cookie_endpoints_cannot_bypass_csrf_with_authorization(
    csrf_client: TestClient, path: str, authorization: str | None
) -> None:
    csrf_client.cookies.set("refresh_token", "refresh-cookie")
    headers = {"Authorization": authorization} if authorization else {}

    assert csrf_client.post(path, headers=headers).status_code == 403
    headers["Origin"] = "https://app.luml.ai"
    assert csrf_client.post(path, headers=headers).status_code == 200
