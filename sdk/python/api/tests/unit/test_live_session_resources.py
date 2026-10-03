import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from luml_api._types import (
    LiveSession,
    LiveSessionHeartbeat,
    LiveSessionStart,
    LiveSessionStatus,
    LiveSessionViewToken,
    LiveSessionVisibility,
)
from tests.conftest import TEST_API_KEY

ORG = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
ORBIT = "0199c337-09f3-753e-9def-b27745e69be6"
USER = "0199c9cd-3e36-72c0-b823-040eb8195067"
SESSION_ID = "k3f9x2ab"
SESSIONS_PATH = f"/v1/organizations/{ORG}/orbits/{ORBIT}/live-sessions"
SESSION_PATH = f"{SESSIONS_PATH}/{SESSION_ID}"
RELAY = "0199d001-0000-7000-8000-000000000001"
TOKEN_EXPIRES_AT = datetime(2026, 9, 29, 12, 10, tzinfo=UTC)


def _session_record(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    record: dict[str, Any] = {
        "id": SESSION_ID,
        "orbit_id": ORBIT,
        "user_id": USER,
        "label": "training dashboard",
        "visibility": "owner",
        "relay_id": RELAY,
        "started_at": "2026-09-29T12:00:00Z",
        "last_heartbeat_at": "2026-09-29T12:00:30Z",
        "connected": True,
        "ended_at": None,
        "last_viewer_activity_at": None,
        "status": "live",
    }
    record.update(overrides)
    return record


START_RESPONSE: dict[str, Any] = {
    "id": SESSION_ID,
    "public_url": f"https://{SESSION_ID}.tunnel.example",
    "agent_url": "wss://tunnel.example/.luml-tunnel/agent",
    "expose_token": "expose-token",
    "token_expires_at": "2026-09-29T12:10:00Z",
    "heartbeat_interval": 30,
}
HEARTBEAT_RESPONSE: dict[str, Any] = {
    "status": "live",
    "expose_token": "renewed-token",
    "token_expires_at": "2026-09-29T12:20:00Z",
}
VIEW_TOKEN_RESPONSE: dict[str, Any] = {
    "token": "view-token",
    "launch_url": f"https://{SESSION_ID}.tunnel.example/.luml-tunnel/launch?token=view-token",
    "expires_at": "2026-09-29T12:05:00Z",
}

# (operation, args, HTTP method, path, request body, response body, result type)
OPERATIONS: list[tuple[str, tuple[Any, ...], str, str, Any, Any, type[BaseModel]]] = [
    (
        "start",
        ("training dashboard",),
        "POST",
        SESSIONS_PATH,
        {"label": "training dashboard"},
        START_RESPONSE,
        LiveSessionStart,
    ),
    ("start", (), "POST", SESSIONS_PATH, {}, START_RESPONSE, LiveSessionStart),
    ("get", (SESSION_ID,), "GET", SESSION_PATH, None, _session_record(), LiveSession),
    (
        "heartbeat",
        (SESSION_ID, False, TOKEN_EXPIRES_AT),
        "POST",
        f"{SESSION_PATH}/heartbeat",
        {"connected": False, "token_expires_at": "2026-09-29T12:10:00+00:00"},
        HEARTBEAT_RESPONSE,
        LiveSessionHeartbeat,
    ),
    (
        "view_token",
        (SESSION_ID,),
        "POST",
        f"{SESSION_PATH}/view-token",
        {},
        VIEW_TOKEN_RESPONSE,
        LiveSessionViewToken,
    ),
    (
        "view_token",
        (SESSION_ID, "/runs/42?tab=metrics"),
        "POST",
        f"{SESSION_PATH}/view-token",
        {"destination": "/runs/42?tab=metrics"},
        VIEW_TOKEN_RESPONSE,
        LiveSessionViewToken,
    ),
    (
        "end",
        (SESSION_ID,),
        "POST",
        f"{SESSION_PATH}/end",
        None,
        _session_record(ended_at="2026-09-29T12:30:00Z", status="ended"),
        LiveSession,
    ),
]
OPERATION_IDS = [f"{operation[0]}-{len(operation[1])}-args" for operation in OPERATIONS]


def _assert_request(
    route: Any,  # noqa: ANN401
    expected_body: Any,  # noqa: ANN401
) -> None:
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {TEST_API_KEY}"
    sent_body = json.loads(request.content) if request.content else None
    assert sent_body == expected_body


@pytest.mark.parametrize(
    ("operation", "args", "method", "path", "body", "response", "result_type"),
    OPERATIONS,
    ids=OPERATION_IDS,
)
def test_operation_sends_matching_request_and_returns_typed_answer(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
    operation: str,
    args: tuple[Any, ...],
    method: str,
    path: str,
    body: Any,  # noqa: ANN401
    response: Any,  # noqa: ANN401
    result_type: type[BaseModel],
) -> None:
    route = respx_mock.request(method, path).mock(
        return_value=httpx.Response(200, json=response)
    )

    result = getattr(client_with_mocks.live_sessions, operation)(*args)

    _assert_request(route, body)
    assert isinstance(result, result_type)
    assert result.model_dump(mode="json") == result_type.model_validate(
        response
    ).model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "args", "method", "path", "body", "response", "result_type"),
    OPERATIONS,
    ids=OPERATION_IDS,
)
async def test_async_operation_sends_matching_request_and_returns_typed_answer(
    async_client_with_mocks: AsyncLumlClient,
    respx_mock: MockRouter,
    operation: str,
    args: tuple[Any, ...],
    method: str,
    path: str,
    body: Any,  # noqa: ANN401
    response: Any,  # noqa: ANN401
    result_type: type[BaseModel],
) -> None:
    route = respx_mock.request(method, path).mock(
        return_value=httpx.Response(200, json=response)
    )

    result = await getattr(async_client_with_mocks.live_sessions, operation)(*args)

    _assert_request(route, body)
    assert isinstance(result, result_type)


def test_list_returns_typed_sessions(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.get(SESSIONS_PATH).mock(
        return_value=httpx.Response(
            200,
            json=[_session_record(), _session_record(id="p7q2m9zz", status="ended")],
        )
    )

    sessions = client_with_mocks.live_sessions.list()

    assert [session.id for session in sessions] == [SESSION_ID, "p7q2m9zz"]
    assert all(isinstance(session, LiveSession) for session in sessions)
    assert [session.status for session in sessions] == [
        LiveSessionStatus.LIVE,
        LiveSessionStatus.ENDED,
    ]


@pytest.mark.asyncio
async def test_async_list_returns_typed_sessions(
    async_client_with_mocks: AsyncLumlClient, respx_mock: MockRouter
) -> None:
    route = respx_mock.get(SESSIONS_PATH).mock(
        return_value=httpx.Response(200, json=[_session_record()])
    )

    sessions = await async_client_with_mocks.live_sessions.list()

    assert route.call_count == 1
    assert sessions == [LiveSession.model_validate(_session_record())]


def test_start_parses_token_expiry_as_datetime(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.post(SESSIONS_PATH).mock(
        return_value=httpx.Response(200, json=START_RESPONSE)
    )

    started = client_with_mocks.live_sessions.start("training dashboard")

    assert started.token_expires_at == TOKEN_EXPIRES_AT
    assert started.heartbeat_interval == 30


def test_heartbeat_without_renewal_has_no_token(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.post(f"{SESSION_PATH}/heartbeat").mock(
        return_value=httpx.Response(200, json={"status": "ended"})
    )

    answer = client_with_mocks.live_sessions.heartbeat(
        SESSION_ID, True, TOKEN_EXPIRES_AT
    )

    assert answer.status == LiveSessionStatus.ENDED
    assert answer.expose_token is None
    assert answer.token_expires_at is None


def test_start_answer_carries_no_app_address(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.post(SESSIONS_PATH).mock(
        return_value=httpx.Response(200, json=START_RESPONSE)
    )

    started = client_with_mocks.live_sessions.start()

    assert "app_url" not in started.model_dump()
    assert started.public_url == f"https://{SESSION_ID}.tunnel.example"


def test_session_without_label_or_relay_is_typed(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.get(SESSION_PATH).mock(
        return_value=httpx.Response(
            200, json=_session_record(label=None, relay_id=None, status="ended")
        )
    )

    session = client_with_mocks.live_sessions.get(SESSION_ID)

    assert session.label is None
    assert session.relay_id is None
    assert session.visibility == LiveSessionVisibility.OWNER


@pytest.mark.parametrize(
    "detail",
    [
        "Assign a relay to this orbit in orbit settings",
        "Relay office is draining",
    ],
)
def test_start_refusal_raises_conflict(
    client_with_mocks: LumlClient, respx_mock: MockRouter, detail: str
) -> None:
    respx_mock.post(SESSIONS_PATH).mock(
        return_value=httpx.Response(409, json={"detail": detail})
    )

    with pytest.raises(ConflictError):
        client_with_mocks.live_sessions.start("training dashboard")


def test_view_token_with_invalid_destination_raises_unprocessable(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.post(f"{SESSION_PATH}/view-token").mock(
        return_value=httpx.Response(422, json={"detail": "Invalid destination"})
    )

    with pytest.raises(UnprocessableEntityError):
        client_with_mocks.live_sessions.view_token(SESSION_ID, "https://evil.example")


def test_get_of_another_users_session_raises_not_found(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.get(SESSION_PATH).mock(
        return_value=httpx.Response(404, json={"detail": "Live session not found"})
    )

    with pytest.raises(NotFoundError):
        client_with_mocks.live_sessions.get(SESSION_ID)


def test_view_token_for_ended_session_raises_conflict(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.post(f"{SESSION_PATH}/view-token").mock(
        return_value=httpx.Response(409, json={"detail": "Live session has ended"})
    )

    with pytest.raises(ConflictError):
        client_with_mocks.live_sessions.view_token(SESSION_ID)
