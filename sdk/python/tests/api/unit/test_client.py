import httpx
import pytest
from respx import MockRouter

from dataforce import AsyncDataForceClient, DataForceClient
from dataforce.api._exceptions import NotFoundError
from tests.conftest import TEST_API_KEY, TEST_BASE_URL


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_client_initialization_with_params(mock_initialization_requests: dict) -> None:
    data = mock_initialization_requests
    organization_id = data["organization"].id
    orbit_id = data["orbit"].id
    collection_oid = data["collection"].id

    client = DataForceClient(
        base_url=TEST_BASE_URL,
        api_key=TEST_API_KEY,
        organization=organization_id,
        orbit=orbit_id,
        collection=collection_oid,
    )
    assert client._api_key == TEST_API_KEY
    assert client._base_url == TEST_BASE_URL
    assert client.organization == organization_id
    assert client.orbit == orbit_id
    assert client.collection == collection_oid


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_organization_validation_single_org(mock_initialization_requests: dict) -> None:
    data = mock_initialization_requests
    client = DataForceClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    assert client.organization == data["organization"].id


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_organization_validation_multiple_orgs_no_default(
    respx_mock: MockRouter,
) -> None:
    respx_mock.get("/users/me/organizations").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Org 1", "created_at": "2024-01-01T00:00:00Z"},
                {"id": 2, "name": "Org 2", "created_at": "2024-01-01T00:00:00Z"},
            ],
        )
    )

    client = DataForceClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    assert client.organization is None


def test_async_client_initialization() -> None:
    client = AsyncDataForceClient(base_url=TEST_BASE_URL, api_key=TEST_API_KEY)
    assert client._api_key == TEST_API_KEY
    assert client._base_url == TEST_BASE_URL


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
async def test_async_organization_list(
    async_client_with_mocks: AsyncDataForceClient,
) -> None:
    organizations = await async_client_with_mocks.organizations.list()

    assert len(organizations) == 1
    assert organizations[0].id == 1
    assert organizations[0].name == "Test Organization"


@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_error_handling(
    client_with_mocks: DataForceClient, respx_mock: MockRouter
) -> None:
    organization_id = 1
    bucket_id = 999999

    respx_mock.get(f"/organizations/{organization_id}/bucket-secrets/{bucket_id}").mock(
        return_value=httpx.Response(404, json={"error": "Not found"})
    )

    with pytest.raises(NotFoundError):
        client_with_mocks.bucket_secrets.get(bucket_id)


@pytest.mark.parametrize(
    "resource_name",
    ["organizations", "orbits", "collections", "bucket_secrets", "model_artifacts"],
)
@pytest.mark.respx(base_url=TEST_BASE_URL)
def test_all_resources_accessible(
    resource_name: str, mock_initialization_requests: dict
) -> None:
    sync_client = DataForceClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    assert hasattr(sync_client, resource_name)

    async_client = AsyncDataForceClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    assert hasattr(async_client, resource_name)
