from collections.abc import Awaitable
from contextlib import nullcontext
from typing import Any

import pytest
import pytest_asyncio
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import CollectionResourceNotFoundError
from luml_api._types import Collection
from tests.conftest import TEST_BASE_URL

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


@pytest.mark.respx(base_url=TEST_BASE_URL)
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
    respx_mock: MockRouter,
    sample_collection: Collection,
    names: list[str],
    expected: str | None,
) -> None:
    items = [sample_collection.model_copy(update={"name": name}) for name in names]
    respx_mock.get(
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


@pytest.mark.respx(base_url=TEST_BASE_URL)
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


@pytest.mark.respx(base_url=TEST_BASE_URL)
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
