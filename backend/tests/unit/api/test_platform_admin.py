from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from luml.handlers.auth import AuthHandler
from luml.handlers.platform_admin_auth import (
    PlatformAdminAuthHandler,
    PlatformAdminConfig,
    code_challenge_for,
)
from luml.schemas.platform_admin import (
    OrganizationLimits,
    OrganizationLimitsUpdate,
    OrganizationUsage,
    PlatformAdminOrganizationDetails,
    PlatformAdminUserUpdate,
    PlatformStats,
)
from luml.schemas.user import AuthProvider, User, UserOut
from luml.service import AppService
from luml.settings import config

ADMIN_EMAIL = "admin@luml.ai"
ADMIN_PASSWORD = "admin-password"
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ALLOWED_ORIGIN = config.CORS_ORIGINS.split(",")[0]
STATS_PATH = "/v1/platform-admin/stats"

HANDLER = "luml.api.platform_admin.platform_admin_handler"

ENABLED_CONFIG = PlatformAdminConfig.from_settings(
    config.model_copy(
        update={
            "PLATFORM_ADMIN_EMAIL": ADMIN_EMAIL,
            "PLATFORM_ADMIN_AUTH_METHODS": "GOOGLE,EMAIL",
            "PLATFORM_ADMIN_GOOGLE_REDIRECT_URI": (
                "https://api.example.com/v1/platform-admin/auth/google/callback"
            ),
        }
    )
)

STATS = PlatformStats(
    users=10,
    disabled_users=1,
    users_created_last_30_days=3,
    organizations=4,
    orbits=5,
    satellites=6,
    artifacts=7,
)


def _organization_details() -> PlatformAdminOrganizationDetails:
    return PlatformAdminOrganizationDetails(
        id=ORGANIZATION_ID,
        name="Acme",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        limits=OrganizationLimits(
            members_limit=10, orbits_limit=1, satellites_limit=2, artifacts_limit=50
        ),
        usage=OrganizationUsage(members=2, orbits=1, satellites=0, artifacts=3),
        members=[],
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    handler = PlatformAdminAuthHandler(
        ENABLED_CONFIG, AuthHandler(secret_key=config.AUTH_SECRET_KEY)
    )
    with (
        patch("luml.service.platform_admin_config", ENABLED_CONFIG),
        patch("luml.service.configure_platform_admin_logging"),
        patch("luml.api.platform_admin.platform_admin_auth_handler", handler),
        patch(
            "luml.handlers.auth.TokenBlackListRepository.is_token_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch.object(
            AuthHandler,
            "_authenticate_user",
            new_callable=AsyncMock,
            return_value=User(
                id=USER_ID,
                email=ADMIN_EMAIL,
                auth_method=AuthProvider.EMAIL,
                email_verified=True,
                disabled=False,
            ),
        ),
    ):
        yield TestClient(AppService())


@pytest.fixture
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/v1/platform-admin/auth/token",
        json={"grant_type": "password", "email": ADMIN_EMAIL, "password": "pw"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_routes_are_not_mounted_without_admin_email() -> None:
    paths = {getattr(route, "path", "") for route in AppService().routes}

    assert not any(path.startswith("/v1/platform-admin") for path in paths)


def test_password_grant_token_identifies_admin(
    client: TestClient, admin_token: str
) -> None:
    response = client.get("/v1/platform-admin/auth/me", headers=_bearer(admin_token))

    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL
    assert response.json()["auth_method"] == "EMAIL"


def test_admin_routes_require_bearer_token(client: TestClient) -> None:
    response = client.get(STATS_PATH)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_admin_token_in_cookie_is_ignored(client: TestClient, admin_token: str) -> None:
    client.cookies.set("access_token", admin_token)

    assert client.get(STATS_PATH).status_code == 401


@patch("luml.handlers.auth.UserRepository.get_public_user", new_callable=AsyncMock)
def test_user_session_token_is_rejected(
    mock_get_public_user: AsyncMock, client: TestClient
) -> None:
    mock_get_public_user.return_value = UserOut(id=USER_ID, email=ADMIN_EMAIL)
    user_token = AuthHandler(secret_key=config.AUTH_SECRET_KEY)._create_tokens(
        ADMIN_EMAIL
    )

    response = client.get(STATS_PATH, headers=_bearer(user_token.access_token))

    assert response.status_code == 401


@patch(f"{HANDLER}.get_stats", new_callable=AsyncMock)
def test_stats_with_admin_token(
    mock_get_stats: AsyncMock, client: TestClient, admin_token: str
) -> None:
    mock_get_stats.return_value = STATS

    response = client.get(STATS_PATH, headers=_bearer(admin_token))

    assert response.status_code == 200
    assert response.json() == STATS.model_dump()


@patch(f"{HANDLER}.update_organization_limits", new_callable=AsyncMock)
def test_update_limits_passes_admin_and_partial_limits(
    mock_update_limits: AsyncMock, client: TestClient, admin_token: str
) -> None:
    mock_update_limits.return_value = _organization_details()

    response = client.patch(
        f"/v1/platform-admin/organizations/{ORGANIZATION_ID}/limits",
        headers=_bearer(admin_token),
        json={"orbits_limit": 5},
    )

    assert response.status_code == 200
    assert mock_update_limits.await_args is not None
    admin, organization_id, limits = mock_update_limits.await_args.args
    assert admin.email == ADMIN_EMAIL
    assert organization_id == ORGANIZATION_ID
    assert limits == OrganizationLimitsUpdate(orbits_limit=5)


@pytest.mark.parametrize(
    "body",
    [{}, {"orbits_limit": -1}, {"orbits_limit": 5, "unknown_limit": 1}],
    ids=["empty", "negative", "unknown-field"],
)
@patch(f"{HANDLER}.update_organization_limits", new_callable=AsyncMock)
def test_update_limits_validates_body(
    mock_update_limits: AsyncMock,
    body: dict[str, int],
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.patch(
        f"/v1/platform-admin/organizations/{ORGANIZATION_ID}/limits",
        headers=_bearer(admin_token),
        json=body,
    )

    assert response.status_code == 422
    mock_update_limits.assert_not_awaited()


@patch(f"{HANDLER}.update_user", new_callable=AsyncMock)
def test_update_user_rejects_fields_other_than_disabled(
    mock_update_user: AsyncMock, client: TestClient, admin_token: str
) -> None:
    response = client.patch(
        f"/v1/platform-admin/users/{USER_ID}",
        headers=_bearer(admin_token),
        json={"disabled": True, "email": "other@example.com"},
    )

    assert response.status_code == 422
    mock_update_user.assert_not_awaited()


@patch(f"{HANDLER}.update_user", new_callable=AsyncMock)
def test_update_user_disables_user(
    mock_update_user: AsyncMock, client: TestClient, admin_token: str
) -> None:
    mock_update_user.side_effect = RuntimeError("stop after validation")

    with pytest.raises(RuntimeError):
        client.patch(
            f"/v1/platform-admin/users/{USER_ID}",
            headers=_bearer(admin_token),
            json={"disabled": True},
        )

    assert mock_update_user.await_args is not None
    _admin, user_id, update = mock_update_user.await_args.args
    assert user_id == USER_ID
    assert update == PlatformAdminUserUpdate(disabled=True)


def test_preflight_to_admin_routes_is_refused(client: TestClient) -> None:
    response = client.options(
        STATS_PATH,
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


@patch(f"{HANDLER}.get_stats", new_callable=AsyncMock)
def test_admin_responses_carry_no_cors_headers(
    mock_get_stats: AsyncMock, client: TestClient, admin_token: str
) -> None:
    mock_get_stats.return_value = STATS

    response = client.get(
        STATS_PATH, headers={**_bearer(admin_token), "Origin": ALLOWED_ORIGIN}
    )

    assert response.status_code == 200
    assert not any(name.startswith("access-control-") for name in response.headers)


def test_cors_still_applies_to_regular_routes(client: TestClient) -> None:
    response = client.options(
        "/v1/auth/signin",
        headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_google_login_redirects_to_google(client: TestClient) -> None:
    response = client.get(
        "/v1/platform-admin/auth/google/login",
        params={"port": 53682, "code_challenge": code_challenge_for("v" * 43)},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"].startswith(config.GOOGLE_AUTH_URL)


@pytest.mark.parametrize(
    "params",
    [
        {"port": 80, "code_challenge": code_challenge_for("v" * 43)},
        {"port": 53682, "code_challenge": "too-short"},
    ],
    ids=["privileged-port", "bad-challenge"],
)
def test_google_login_validates_loopback_parameters(
    client: TestClient, params: dict[str, int | str]
) -> None:
    response = client.get(
        "/v1/platform-admin/auth/google/login", params=params, follow_redirects=False
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [{}, {"organizations_limit": -1}, {"disabled": None}],
    ids=["empty", "negative-limit", "only-null"],
)
@patch(f"{HANDLER}.update_user", new_callable=AsyncMock)
def test_update_user_validates_body(
    mock_update_user: AsyncMock,
    body: dict[str, object],
    client: TestClient,
    admin_token: str,
) -> None:
    response = client.patch(
        f"/v1/platform-admin/users/{USER_ID}", headers=_bearer(admin_token), json=body
    )

    assert response.status_code == 422
    mock_update_user.assert_not_awaited()


@patch(f"{HANDLER}.update_user", new_callable=AsyncMock)
def test_update_user_organizations_limit(
    mock_update_user: AsyncMock, client: TestClient, admin_token: str
) -> None:
    mock_update_user.side_effect = RuntimeError("stop after validation")

    with pytest.raises(RuntimeError):
        client.patch(
            f"/v1/platform-admin/users/{USER_ID}",
            headers=_bearer(admin_token),
            json={"organizations_limit": 8},
        )

    assert mock_update_user.await_args is not None
    _admin, _user_id, update = mock_update_user.await_args.args
    assert update == PlatformAdminUserUpdate(organizations_limit=8)
