from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from luml.api.organization.organization_relays import relays_router
from luml.infra.exceptions import ApplicationError
from luml.models import AuthRelay, AuthUser
from luml.schemas.relay import Relay, RelayStatus, RelayTokenOut
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
RELAY_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")

RELAYS_PATH = f"/{ORGANIZATION_ID}/relays"
RELAY_PATH = f"{RELAYS_PATH}/{RELAY_ID}"
HANDLER = "luml.handlers.relays.RelayHandler"


class _NoCredentialsBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection) -> None:
        return None


class _SignedInBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthUser]:
        return AuthCredentials(["authenticated", "jwt"]), AuthUser(
            user_id=USER_ID, email="caller@example.com"
        )


class _RelayBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthRelay]:
        return AuthCredentials(["authenticated", "relay"]), AuthRelay(RELAY_ID)


def _client(backend: AuthenticationBackend) -> TestClient:
    app = FastAPI()
    app.include_router(relays_router)

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, error: ApplicationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.message}
        )

    app.add_middleware(AuthenticationMiddleware, backend=backend)
    return TestClient(app)


def _relay() -> Relay:
    return Relay(
        id=RELAY_ID,
        organization_id=ORGANIZATION_ID,
        label="lab",
        base_domain="tunnel.example",
        agent_url="wss://relay.tunnel.example/connect",
        status=RelayStatus.ENABLED,
        created_at=datetime.now(UTC),
    )


@patch(f"{HANDLER}.list_relays", new_callable=AsyncMock)
def test_relays_require_authentication(mock_list_relays: AsyncMock) -> None:
    response = _client(_NoCredentialsBackend()).get(RELAYS_PATH)

    assert response.status_code == 401
    mock_list_relays.assert_not_awaited()


@patch(f"{HANDLER}.list_relays", new_callable=AsyncMock)
def test_relay_token_is_refused_on_organization_routes(
    mock_list_relays: AsyncMock,
) -> None:
    response = _client(_RelayBackend()).get(RELAYS_PATH)

    assert response.status_code == 403
    mock_list_relays.assert_not_awaited()


@patch(f"{HANDLER}.list_relays", new_callable=AsyncMock)
def test_list_relays_answers_kind_and_online_without_hashes(
    mock_list_relays: AsyncMock,
) -> None:
    mock_list_relays.return_value = [_relay()]

    response = _client(_SignedInBackend()).get(RELAYS_PATH)

    assert response.status_code == 200
    mock_list_relays.assert_awaited_once_with(USER_ID, ORGANIZATION_ID)
    [listed] = response.json()
    assert listed["kind"] == "own"
    assert listed["online"] is False
    assert listed["status"] == "enabled"
    assert not any("hash" in field for field in listed)


@patch(f"{HANDLER}.create_relay", new_callable=AsyncMock)
def test_create_relay_answers_the_plaintext_token(
    mock_create_relay: AsyncMock,
) -> None:
    mock_create_relay.return_value = RelayTokenOut(
        relay=_relay(), token="dfsrelay_secret"
    )

    response = _client(_SignedInBackend()).post(
        RELAYS_PATH,
        json={
            "label": "lab",
            "base_domain": "Tunnel.Example",
            "agent_url": "wss://relay.tunnel.example/connect",
        },
    )

    assert response.status_code == 200
    assert response.json()["token"] == "dfsrelay_secret"
    assert response.json()["relay"]["kind"] == "own"
    created = mock_create_relay.await_args_list[0].args[2]
    assert created.base_domain == "tunnel.example"


@patch(f"{HANDLER}.create_relay", new_callable=AsyncMock)
def test_create_relay_with_an_invalid_address_is_refused(
    mock_create_relay: AsyncMock,
) -> None:
    response = _client(_SignedInBackend()).post(
        RELAYS_PATH,
        json={
            "label": "lab",
            "base_domain": "tunnel.example",
            "agent_url": "https://relay.tunnel.example/connect",
        },
    )

    assert response.status_code == 422
    assert "ws or wss" in response.text
    mock_create_relay.assert_not_awaited()


@patch(f"{HANDLER}.update_relay", new_callable=AsyncMock)
def test_update_relay_forwards_the_change(mock_update_relay: AsyncMock) -> None:
    mock_update_relay.return_value = _relay()

    response = _client(_SignedInBackend()).patch(
        RELAY_PATH, json={"status": "draining"}
    )

    assert response.status_code == 200
    user_id, organization_id, relay_id, change = mock_update_relay.await_args_list[
        0
    ].args
    assert (user_id, organization_id, relay_id) == (USER_ID, ORGANIZATION_ID, RELAY_ID)
    assert change.model_dump(exclude_unset=True) == {"status": "draining"}


@patch(f"{HANDLER}.update_relay", new_callable=AsyncMock)
def test_managed_relay_refusal_reaches_the_caller(
    mock_update_relay: AsyncMock,
) -> None:
    mock_update_relay.side_effect = ApplicationError(
        "Managed relays are read-only", 403
    )

    response = _client(_SignedInBackend()).patch(RELAY_PATH, json={"label": "x"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Managed relays are read-only"


@patch(f"{HANDLER}.rotate_token", new_callable=AsyncMock)
def test_rotate_token_answers_the_new_token(mock_rotate_token: AsyncMock) -> None:
    mock_rotate_token.return_value = RelayTokenOut(
        relay=_relay(), token="dfsrelay_rotated"
    )

    response = _client(_SignedInBackend()).post(f"{RELAY_PATH}/rotate-token")

    assert response.status_code == 200
    assert response.json()["token"] == "dfsrelay_rotated"
    mock_rotate_token.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, RELAY_ID)


@patch(f"{HANDLER}.get_relay", new_callable=AsyncMock)
def test_get_relay_forwards_path_parameters(mock_get_relay: AsyncMock) -> None:
    mock_get_relay.return_value = _relay()

    response = _client(_SignedInBackend()).get(RELAY_PATH)

    assert response.status_code == 200
    assert response.json()["id"] == str(RELAY_ID)
    mock_get_relay.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, RELAY_ID)


@patch(f"{HANDLER}.delete_relay", new_callable=AsyncMock)
def test_delete_relay_answers_no_content(mock_delete_relay: AsyncMock) -> None:
    response = _client(_SignedInBackend()).delete(RELAY_PATH)

    assert response.status_code == 204
    mock_delete_relay.assert_awaited_once_with(USER_ID, ORGANIZATION_ID, RELAY_ID)
