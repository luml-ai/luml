import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import ConflictError, NotFoundError
from luml_api._types import Flow, FlowExposed, LiveSessionStart, LiveSessionStatus
from tests.conftest import TEST_API_KEY

ORG = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
ORBIT = "0199c337-09f3-753e-9def-b27745e69be6"
USER = "0199c9cd-3e36-72c0-b823-040eb8195067"
FLOW_ID = "0199d002-0000-7000-8000-000000000001"
SESSION_ID = "k3f9x2ab"
FLOWS_PATH = f"/v1/organizations/{ORG}/orbits/{ORBIT}/flows"
FLOW_PATH = f"{FLOWS_PATH}/{FLOW_ID}"
FLOW_PAGE_URL = f"https://app.luml.ai/organization/{ORG}/orbit/{ORBIT}/flow"


def _flow_record(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    record: dict[str, Any] = {
        "id": FLOW_ID,
        "orbit_id": ORBIT,
        "user_id": USER,
        "name": "training",
        "session": {
            "id": SESSION_ID,
            "status": "live",
            "started_at": "2026-09-29T12:00:00Z",
            "last_heartbeat_at": "2026-09-29T12:00:30Z",
        },
        "created_at": "2026-09-29T12:00:00Z",
    }
    record.update(overrides)
    return record


EXPOSE_RESPONSE: dict[str, Any] = {
    "flow": _flow_record(),
    "session": {
        "id": SESSION_ID,
        "public_url": f"https://{SESSION_ID}.tunnel.example",
        "agent_url": "wss://tunnel.example/.luml-tunnel/agent",
        "expose_token": "expose-token",
        "token_expires_at": "2026-09-29T12:10:00Z",
        "heartbeat_interval": 30,
    },
    "app_url": FLOW_PAGE_URL,
}

# (operation, args, HTTP method, path, request body, response body, result type)
OPERATIONS: list[
    tuple[str, tuple[Any, ...], str, str, Any, Any, type[BaseModel] | None]
] = [
    (
        "expose",
        ("training",),
        "POST",
        FLOWS_PATH,
        {"name": "training"},
        EXPOSE_RESPONSE,
        FlowExposed,
    ),
    ("get", (FLOW_ID,), "GET", FLOW_PATH, None, _flow_record(), Flow),
    ("remove", (FLOW_ID,), "DELETE", FLOW_PATH, None, None, None),
]
OPERATION_IDS = [operation[0] for operation in OPERATIONS]


def _mock(
    respx_mock: MockRouter,
    method: str,
    path: str,
    response: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    answer = (
        httpx.Response(204) if response is None else httpx.Response(200, json=response)
    )
    return respx_mock.request(method, path).mock(return_value=answer)


def _assert_request(
    route: Any,  # noqa: ANN401
    expected_body: Any,  # noqa: ANN401
) -> None:
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {TEST_API_KEY}"
    sent_body = json.loads(request.content) if request.content else None
    assert sent_body == expected_body


def _assert_result(
    result: Any,  # noqa: ANN401
    response: Any,  # noqa: ANN401
    result_type: type[BaseModel] | None,
) -> None:
    if result_type is None:
        assert result is None
        return
    assert isinstance(result, result_type)
    assert result.model_dump(mode="json") == result_type.model_validate(
        response
    ).model_dump(mode="json")


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
    result_type: type[BaseModel] | None,
) -> None:
    route = _mock(respx_mock, method, path, response)

    result = getattr(client_with_mocks.flows, operation)(*args)

    _assert_request(route, body)
    _assert_result(result, response, result_type)


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
    result_type: type[BaseModel] | None,
) -> None:
    route = _mock(respx_mock, method, path, response)

    result = await getattr(async_client_with_mocks.flows, operation)(*args)

    _assert_request(route, body)
    _assert_result(result, response, result_type)


def test_list_returns_typed_flows(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    route = respx_mock.get(FLOWS_PATH).mock(
        return_value=httpx.Response(
            200, json=[_flow_record(), _flow_record(id=USER, name="eval")]
        )
    )

    flows = client_with_mocks.flows.list()

    assert route.call_count == 1
    assert [flow.name for flow in flows] == ["training", "eval"]
    assert all(isinstance(flow, Flow) for flow in flows)
    assert flows[0].session.status == LiveSessionStatus.LIVE


@pytest.mark.asyncio
async def test_async_list_returns_typed_flows(
    async_client_with_mocks: AsyncLumlClient, respx_mock: MockRouter
) -> None:
    route = respx_mock.get(FLOWS_PATH).mock(
        return_value=httpx.Response(200, json=[_flow_record()])
    )

    flows = await async_client_with_mocks.flows.list()

    assert route.call_count == 1
    assert flows == [Flow.model_validate(_flow_record())]


def test_expose_answer_carries_session_start_and_flow_page(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    respx_mock.post(FLOWS_PATH).mock(
        return_value=httpx.Response(200, json=EXPOSE_RESPONSE)
    )

    exposed = client_with_mocks.flows.expose("training")

    assert exposed.app_url == FLOW_PAGE_URL
    assert isinstance(exposed.session, LiveSessionStart)
    assert exposed.session.id == exposed.flow.session.id == SESSION_ID
    assert exposed.session.heartbeat_interval == 30


@pytest.mark.parametrize(
    "detail",
    [
        "Relay office is draining",
        "Organization reached its limit of sessions through own relays",
    ],
)
def test_refused_expose_raises_conflict(
    client_with_mocks: LumlClient, respx_mock: MockRouter, detail: str
) -> None:
    respx_mock.post(FLOWS_PATH).mock(
        return_value=httpx.Response(409, json={"detail": detail})
    )

    with pytest.raises(ConflictError) as error:
        client_with_mocks.flows.expose("training")

    assert detail in str(error.value)


@pytest.mark.parametrize(
    ("operation", "method"), [("get", "GET"), ("remove", "DELETE")]
)
def test_flow_of_another_user_raises_not_found(
    client_with_mocks: LumlClient,
    respx_mock: MockRouter,
    operation: str,
    method: str,
) -> None:
    respx_mock.request(method, FLOW_PATH).mock(
        return_value=httpx.Response(404, json={"detail": "Flow not found"})
    )

    with pytest.raises(NotFoundError):
        getattr(client_with_mocks.flows, operation)(FLOW_ID)
