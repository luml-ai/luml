from collections.abc import Awaitable
from contextlib import nullcontext
from typing import Any

import httpx2
import pytest
import pytest_asyncio
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import (
    AuthenticationError,
    CollectionResourceNotFoundError,
    OrbitResourceNotFoundError,
    OrganizationResourceNotFoundError,
)
from luml_api._types import Collection
from tests.conftest import TEST_API_KEY, TEST_BASE_URL

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(params=["sync", "async"])
async def client(
    request: pytest.FixtureRequest,
    client_with_mocks: LumlClient,
    async_client_with_mocks: AsyncLumlClient,
) -> LumlClient | AsyncLumlClient:
    return client_with_mocks if request.param == "sync" else async_client_with_mocks


async def _resolve(value: Any) -> Any:  # noqa: ANN401
    return await value if isinstance(value, Awaitable) else value


@pytest.mark.httpx2(base_url=TEST_BASE_URL)
@pytest.mark.parametrize(
    ("names", "expected"),
    [
        (["model"], "match"),
        (["models-v2"], None),
        (["MODEL"], None),
        ([], None),
        (["models-v2", "model"], "match"),
        (["models-v2", "model-v3"], None),
        (["model", "model"], "duplicate"),
    ],
)
async def test_default_collection_requires_exact_name(
    client: LumlClient | AsyncLumlClient,
    httpx2_mock: MockRouter,
    sample_collection: Collection,
    names: list[str],
    expected: str | None,
) -> None:
    items = [sample_collection.model_copy(update={"name": name}) for name in names]
    httpx2_mock.get(
        f"/v1/organizations/{client.organization}/orbits/{client.orbit}/collections",
    ).respond(
        200, json={"items": [item.model_dump() for item in items], "cursor": None}
    )

    if expected == "duplicate":
        with pytest.raises(CollectionResourceNotFoundError):
            await _resolve(client._validate_collection_by_name("model"))
    else:
        result = await _resolve(client._validate_collection_by_name("model"))
        assert result == (sample_collection.id if expected == "match" else None)


@pytest.mark.httpx2(base_url=TEST_BASE_URL)
async def test_explicit_close_releases_http_client(
    client: LumlClient | AsyncLumlClient,
) -> None:
    assert not client._client.is_closed
    if isinstance(client, AsyncLumlClient):
        await client.aclose()
        await client.aclose()
    else:
        client.close()
        client.close()
    assert client._client.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        await _resolve(client.get("/v1/users/me/organizations"))


@pytest.mark.httpx2(base_url=TEST_BASE_URL, assert_all_called=False)
@pytest.mark.parametrize(
    ("options", "error"),
    [
        ({"organization": "Missing"}, OrganizationResourceNotFoundError),
        ({"orbit": "Missing"}, OrbitResourceNotFoundError),
        (
            {"collection": "0199c337-0000-7000-8000-000000000000"},
            CollectionResourceNotFoundError,
        ),
        ({}, AuthenticationError),
    ],
)
async def test_failed_construction_closes_http_client(
    mock_initialization_requests: dict,
    httpx2_mock: MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    options: dict[str, str],
    error: type[Exception],
) -> None:
    if error is AuthenticationError:
        httpx2_mock.get("/v1/users/me/organizations").respond(401, json={})
    closed: list[httpx2.Client] = []
    close = LumlClient.close

    def recording_close(self: LumlClient) -> None:
        closed.append(self._client)
        close(self)

    monkeypatch.setattr(LumlClient, "close", recording_close)

    with pytest.raises(error):
        LumlClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, **options)

    [http_client] = closed
    assert http_client.is_closed


@pytest.mark.httpx2(base_url=TEST_BASE_URL)
@pytest.mark.parametrize("raise_error", [False, True])
async def test_context_manager_closes_http_client(
    client: LumlClient | AsyncLumlClient,
    raise_error: bool,
) -> None:
    expected_error = (
        pytest.raises(ValueError, match="context failed")
        if raise_error
        else nullcontext()
    )
    with expected_error:
        if isinstance(client, AsyncLumlClient):
            async with client as entered:
                assert entered is client
                assert len(await entered.organizations.list()) == 1
                if raise_error:
                    raise ValueError("context failed")
        else:
            with client as entered:
                assert entered is client
                assert len(entered.organizations.list()) == 1
                if raise_error:
                    raise ValueError("context failed")
    assert client._client.is_closed
