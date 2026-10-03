from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from luml.handlers.relays import RelayHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.security import JWTAuthenticationBackend
from luml.schemas.relay import Relay, RelayStatus
from luml.schemas.user import UserOut
from starlette.middleware.authentication import AuthenticationMiddleware

RELAY_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
RELAY_TOKEN = "dfsrelay_secret"
USER_API_KEY = "dfs_secret"

FIND_RELAY = "luml.handlers.relays.RelayRepository.get_relay_by_token_hash"
FIND_USER = "luml.handlers.api_keys.APIKeyHandler.authenticate_api_key"


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/relay-facing", dependencies=[Depends(UserAuthentication(["relay"]))])
    async def relay_facing(request: Request) -> dict[str, str]:
        return {
            "relay_id": str(request.user.id),
            "scopes": " ".join(request.auth.scopes),
        }

    @app.get(
        "/organization", dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))]
    )
    async def organization() -> dict[str, str]:
        return {"detail": "ok"}

    app.add_middleware(AuthenticationMiddleware, backend=JWTAuthenticationBackend())
    return TestClient(app)


def _relay() -> Relay:
    return Relay(
        id=RELAY_ID,
        organization_id=None,
        label="eu",
        base_domain="eu.luml.example",
        agent_url="wss://eu.luml.example/connect",
        status=RelayStatus.DRAINING,
        created_at=datetime.now(UTC),
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@patch(FIND_RELAY, new_callable=AsyncMock)
def test_relay_token_authenticates_with_the_relay_scope(
    mock_find_relay: AsyncMock,
) -> None:
    mock_find_relay.return_value = _relay()

    response = _client().get("/relay-facing", headers=_bearer(RELAY_TOKEN))

    assert response.status_code == 200
    assert response.json() == {
        "relay_id": str(RELAY_ID),
        "scopes": "authenticated relay",
    }
    mock_find_relay.assert_awaited_once_with(RelayHandler().hash_token(RELAY_TOKEN))


@patch(FIND_RELAY, new_callable=AsyncMock)
def test_relay_token_is_refused_on_organization_routes(
    mock_find_relay: AsyncMock,
) -> None:
    mock_find_relay.return_value = _relay()

    response = _client().get("/organization", headers=_bearer(RELAY_TOKEN))

    assert response.status_code == 403


@patch(FIND_USER, new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock)
def test_unknown_relay_token_is_not_authenticated(
    mock_find_relay: AsyncMock, mock_find_user: AsyncMock
) -> None:
    mock_find_relay.return_value = None

    response = _client().get("/relay-facing", headers=_bearer(RELAY_TOKEN))

    assert response.status_code == 401
    mock_find_user.assert_not_awaited()


@patch(FIND_USER, new_callable=AsyncMock)
@patch(FIND_RELAY, new_callable=AsyncMock)
def test_user_api_key_is_refused_on_relay_facing_routes(
    mock_find_relay: AsyncMock, mock_find_user: AsyncMock
) -> None:
    mock_find_user.return_value = UserOut(
        id=USER_ID, email="caller@example.com", full_name="Caller", disabled=False
    )

    response = _client().get("/relay-facing", headers=_bearer(USER_API_KEY))

    assert response.status_code == 403
    mock_find_relay.assert_not_awaited()
