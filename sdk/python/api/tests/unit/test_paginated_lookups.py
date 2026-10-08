from collections.abc import Awaitable
from typing import Any
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import InternalServerError, MultipleResourcesFoundError
from luml_api._types import Artifact
from tests.conftest import TEST_BASE_URL

pytestmark = [pytest.mark.asyncio, pytest.mark.respx(base_url=TEST_BASE_URL)]


@pytest_asyncio.fixture(params=["sync", "async"])
async def lookup_client(
    request: pytest.FixtureRequest,
    client_with_mocks: LumlClient,
    async_client_with_mocks: AsyncLumlClient,
) -> LumlClient | AsyncLumlClient:
    return client_with_mocks if request.param == "sync" else async_client_with_mocks


async def _resolve(value: Any) -> Any:  # noqa: ANN401
    return await value if isinstance(value, Awaitable) else value


def _items(
    client: LumlClient | AsyncLumlClient, resource: str, artifact: Artifact
) -> list[dict]:
    items = []
    for index in range(150):
        item = (
            artifact.model_dump()
            if resource == "artifacts"
            else {
                "orbit_id": client.orbit,
                "artifact_type": "model",
                "stages": [],
                "next_version": 1,
                "total_entries": 0,
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        item.update(id=str(UUID(int=index + 1)), name=f"target-extra-{index}")
        if resource == "artifacts":
            item["file_name"] = f"model_{index}.fnnx"
        items.append(item)
    items[120]["name"] = "target"
    return items


def _path(
    client: LumlClient | AsyncLumlClient, resource: str, *, detail: bool = False
) -> str:
    path = f"/v1/organizations/{client.organization}/orbits/{client.orbit}"
    if resource == "artifacts" and detail:
        path += f"/collections/{client.collection}"
    return f"{path}/{resource}"


def _mock_pages(router: MockRouter, path: str, items: list[dict]) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        search = request.url.params.get("search")
        matches = [
            item
            for item in items
            if not search or search.lower() in item["name"].lower()
        ]
        start = 100 if request.url.params.get("cursor") == "page-2" else 0
        return httpx.Response(
            200,
            json={
                "items": matches[start : start + 100],
                "cursor": "page-2" if len(matches) > start + 100 else None,
            },
        )

    router.get(path).mock(side_effect=respond)


@pytest.mark.parametrize("resource", ["artifacts", "tracks"])
@pytest.mark.parametrize(
    "scenario",
    [
        "second_page",
        "first_page",
        "missing",
        "duplicate",
        "partial_only",
        "case_mismatch",
    ],
)
async def test_name_lookup_pages_and_exact_matches(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    resource: str,
    scenario: str,
) -> None:
    items = _items(lookup_client, resource, sample_artifact)
    if scenario == "first_page":
        items[5]["name"], items[120]["name"] = "target", "target-extra-120"
    elif scenario in {"missing", "partial_only"}:
        items[120]["name"] = "target-extra-120"
    elif scenario == "case_mismatch":
        items[120]["name"] = "TARGET"
    elif scenario == "duplicate":
        items[5]["name"] = "target"
    _mock_pages(respx_mock, _path(lookup_client, resource), items)
    value = "absent" if scenario == "missing" else "target"

    if scenario == "duplicate":
        with pytest.raises(MultipleResourcesFoundError):
            await _resolve(getattr(lookup_client, resource).get(value))
    else:
        result = await _resolve(getattr(lookup_client, resource).get(value))
        if scenario in {"missing", "partial_only", "case_mismatch"}:
            assert result is None
        else:
            assert str(result.id) == items[5 if scenario == "first_page" else 120]["id"]

    requests = [
        call.request
        for call in respx_mock.calls
        if call.request.url.path == _path(lookup_client, resource)
    ]
    assert requests[0].url.params.get("cursor") is None
    if scenario != "missing" or resource == "artifacts":
        assert len(requests) == 2
        assert requests[1].url.params["cursor"] == "page-2"
    if resource == "tracks":
        assert all(request.url.params["search"] == value for request in requests)


@pytest.mark.parametrize("duplicate", [False, True])
async def test_artifact_filename_lookup_and_name_collision(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    duplicate: bool,
) -> None:
    items = _items(lookup_client, "artifacts", sample_artifact)
    items[120].update(name="different-name", file_name="target")
    if duplicate:
        items[5]["name"] = "target"
    _mock_pages(respx_mock, _path(lookup_client, "artifacts"), items)

    if duplicate:
        with pytest.raises(MultipleResourcesFoundError):
            await _resolve(lookup_client.artifacts.get("target"))
    else:
        result = await _resolve(lookup_client.artifacts.get("target"))
        assert str(result.id) == items[120]["id"]


@pytest.mark.parametrize("resource", ["artifacts", "tracks"])
async def test_uuid_lookup_uses_single_resource_endpoint(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    resource: str,
) -> None:
    item = _items(lookup_client, resource, sample_artifact)[120]
    route = respx_mock.get(
        f"{_path(lookup_client, resource, detail=True)}/{item['id']}"
    ).respond(200, json=item)

    result = await _resolve(getattr(lookup_client, resource).get(item["id"]))

    assert str(result.id) == item["id"]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params


@pytest.mark.parametrize("status", [404, 500])
async def test_artifact_uuid_lookup_errors(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    status: int,
) -> None:
    respx_mock.get(
        f"{_path(lookup_client, 'artifacts', detail=True)}/{sample_artifact.id}"
    ).respond(status, json={"detail": "lookup failed"})
    if status == 404:
        assert await _resolve(lookup_client.artifacts.get(sample_artifact.id)) is None
    else:
        with pytest.raises(InternalServerError):
            await _resolve(lookup_client.artifacts.get(sample_artifact.id))


@pytest.mark.parametrize("by", ["id", "name"])
async def test_artifact_lookup_honors_collection_override(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    by: str,
) -> None:
    collection_id = str(UUID(int=999))
    items = _items(lookup_client, "artifacts", sample_artifact)
    items[120]["collection_id"] = collection_id
    item = items[120]
    if by == "id":
        path = (
            f"/v1/organizations/{lookup_client.organization}/orbits/"
            f"{lookup_client.orbit}/collections/{collection_id}/artifacts/{item['id']}"
        )
        respx_mock.get(path).respond(200, json=item)
    else:
        path = _path(lookup_client, "artifacts")
        _mock_pages(respx_mock, path, items)

    result = await _resolve(
        lookup_client.artifacts.get(item[by], collection_id=collection_id)
    )

    assert result.id == item["id"]
    if by == "name":
        requests = [
            call.request for call in respx_mock.calls if call.request.url.path == path
        ]
        assert len(requests) == 2
        assert all(
            request.url.params.get_list("collection_ids") == [collection_id]
            for request in requests
        )


@pytest.mark.parametrize("by", ["id", "name", "file_name"])
@pytest.mark.parametrize("file_path", [None, "output.fnnx"])
async def test_download_resolves_id_and_name(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    by: str,
    file_path: str | None,
) -> None:
    items = _items(lookup_client, "artifacts", sample_artifact)
    item = items[120]
    path = _path(lookup_client, "artifacts", detail=True)
    if by == "id" and file_path is None:
        respx_mock.get(f"{path}/{item['id']}").respond(200, json=item)
    elif by != "id":
        _mock_pages(respx_mock, _path(lookup_client, "artifacts"), items)
    url_route = respx_mock.get(f"{path}/{item['id']}/download-url").respond(
        200, json={"url": "https://example.com/file"}
    )

    with patch("luml_api.resources.artifacts.S3FileHandler") as handler:
        await _resolve(lookup_client.artifacts.download(item[by], file_path=file_path))

    assert url_route.call_count == 1
    handler.return_value.download_file_with_progress.assert_called_once()
    kwargs = handler.return_value.download_file_with_progress.call_args.kwargs
    assert kwargs["file_path"] == (file_path or item["file_name"])
    assert kwargs["url"] == "https://example.com/file"


@pytest.mark.parametrize("file_path", [None, "output.fnnx"])
@pytest.mark.parametrize("ambiguous", [False, True])
async def test_download_missing_name_does_not_start_download(
    lookup_client: LumlClient | AsyncLumlClient,
    respx_mock: MockRouter,
    sample_artifact: Artifact,
    file_path: str | None,
    ambiguous: bool,
) -> None:
    items = _items(lookup_client, "artifacts", sample_artifact)
    if ambiguous:
        items[5]["name"] = "target"
    _mock_pages(
        respx_mock,
        _path(lookup_client, "artifacts"),
        items,
    )
    with (
        patch("luml_api.resources.artifacts.S3FileHandler") as handler,
        pytest.raises(MultipleResourcesFoundError if ambiguous else ValueError),
    ):
        await _resolve(
            lookup_client.artifacts.download(
                "target" if ambiguous else "absent", file_path=file_path
            )
        )
    handler.assert_not_called()
