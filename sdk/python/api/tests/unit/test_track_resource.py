import httpx
import pytest
from respx import MockRouter

from luml_api._client import AsyncLumlClient, LumlClient
from tests.conftest import TEST_BASE_URL


def _sample_track_json(orbit_id: str) -> dict:
    return {
        "id": "0199c455-21ee-74c6-b747-19a82f1a1e75",
        "name": "my-track",
        "orbit_id": orbit_id,
        "artifact_type": "model",
        "description": None,
        "tags": ["production"],
        "stages": [],
        "next_version": 1,
        "total_entries": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_client_tracks_list_with_tags(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    organization_id = client_with_mocks.organization
    orbit_id = client_with_mocks.orbit
    route = respx_mock.get(
        f"/v1/organizations/{organization_id}/orbits/{orbit_id}/tracks"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"items": [_sample_track_json(orbit_id)], "cursor": None},
        )
    )

    result = client_with_mocks.tracks.list(tags=["production", "ml"])

    assert [track.name for track in result.items] == ["my-track"]
    request = route.calls.last.request
    assert request.url.params.get_list("tags") == ["production", "ml"]


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_client_tracks_list_tags(
    client_with_mocks: LumlClient, respx_mock: MockRouter
) -> None:
    organization_id = client_with_mocks.organization
    orbit_id = client_with_mocks.orbit
    respx_mock.get(
        f"/v1/organizations/{organization_id}/orbits/{orbit_id}/tracks/tags"
    ).mock(return_value=httpx.Response(200, json=["ml", "production", "staging"]))

    tags = client_with_mocks.tracks.list_tags()

    assert tags == ["ml", "production", "staging"]


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_client_tracks_list_with_tags(
    async_client_with_mocks: AsyncLumlClient, respx_mock: MockRouter
) -> None:
    organization_id = async_client_with_mocks.organization
    orbit_id = async_client_with_mocks.orbit
    route = respx_mock.get(
        f"/v1/organizations/{organization_id}/orbits/{orbit_id}/tracks"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"items": [_sample_track_json(orbit_id)], "cursor": None},
        )
    )

    result = await async_client_with_mocks.tracks.list(tags=["production", "ml"])

    assert [track.name for track in result.items] == ["my-track"]
    request = route.calls.last.request
    assert request.url.params.get_list("tags") == ["production", "ml"]


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_client_tracks_list_tags(
    async_client_with_mocks: AsyncLumlClient, respx_mock: MockRouter
) -> None:
    organization_id = async_client_with_mocks.organization
    orbit_id = async_client_with_mocks.orbit
    respx_mock.get(
        f"/v1/organizations/{organization_id}/orbits/{orbit_id}/tracks/tags"
    ).mock(return_value=httpx.Response(200, json=["ml", "production", "staging"]))

    tags = await async_client_with_mocks.tracks.list_tags()

    assert tags == ["ml", "production", "staging"]
