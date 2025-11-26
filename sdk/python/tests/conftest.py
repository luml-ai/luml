import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import pytest_asyncio

from luml.api._client import AsyncLumlClient, LumlClient
from luml.api._types import (
    BucketSecret,
    Collection,
    ModelArtifact,
    Orbit,
    Organization,
)

TEST_BASE_URL = "http://127.0.0.1:8000"
TEST_API_KEY = "test-api-key"


@pytest.fixture
def mock_sync_client() -> Mock:
    client = Mock(spec=LumlClient)
    client.organization = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
    client.orbit = "0199c337-09f3-753e-9def-b27745e69be6"
    client.collection = "0199c337-09f4-7a01-9f5f-5f68db62cf70"

    client.get = Mock()
    client.post = Mock()
    client.patch = Mock()
    client.delete = Mock()
    client.filter_none = Mock(
        side_effect=lambda x: {k: v for k, v in x.items() if v is not None}
    )

    return client


@pytest.fixture
def mock_async_client() -> AsyncMock:
    client = AsyncMock(spec=AsyncLumlClient)
    client.organization = "0199c337-09f2-7af1-af5e-83fd7a5b51a0"
    client.orbit = "0199c337-09f3-753e-9def-b27745e69be6"
    client.collection = "0199c337-09f4-7a01-9f5f-5f68db62cf70"

    client.get = AsyncMock()
    client.post = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()
    client.filter_none = Mock(
        side_effect=lambda x: {k: v for k, v in x.items() if v is not None}
    )

    return client


@pytest.fixture
def sample_organization() -> Organization:
    return Organization(
        id="0199c337-09f2-7af1-af5e-83fd7a5b51a0",
        name="Test Organization",
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_orbit() -> Orbit:
    return Orbit(
        id="0199c337-09f3-753e-9def-b27745e69be6",
        name="Test Orbit",
        organization_id="0199c337-09f2-7af1-af5e-83fd7a5b51a0",
        bucket_secret_id="0199c337-09f4-7a01-9f5f-5f68a562cf70",
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_collection() -> Collection:
    return Collection(
        id="0199c337-09f4-7a01-9f5f-5f68db62cf70",
        name="Test Collection",
        description="Test collection description",
        collection_type="model",
        orbit_id="0199c337-09f3-753e-9def-b27745e69be6",
        total_models=0,
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_bucket_secret() -> BucketSecret:
    return BucketSecret(
        id="0199c337-09f4-7a01-9f5f-5f68a562cf70",
        endpoint="test.endpoint.com",
        bucket_name="test-bucket",
        organization_id="0199c337-09f2-7af1-af5e-83fd7a5b51a0",
        created_at=str(datetime.datetime.now()),
    )


@pytest.fixture
def sample_model_artifact() -> ModelArtifact:
    return ModelArtifact(
        id="0199c337-09f4-7a01-9f5f-5f68a562cf70",
        file_name="model.pkl",
        model_name="test-model",
        collection_id="0199c337-09f4-7a01-9f5f-5f68db62cf70",
        size=1024,
        file_hash="abc123",
        created_at=str(datetime.datetime.now()),
        metrics={},
        manifest={},
        file_index={},
        bucket_location="location",
        unique_identifier="unique_identifier",
        status="status",
    )


@pytest.fixture
def mock_initialization_requests(
    respx_mock: Any,  # noqa: ANN401
    sample_organization: Organization,
    sample_orbit: Orbit,
    sample_collection: Collection,
) -> dict:
    organization_id = sample_organization.id

    respx_mock.get("/users/me/organizations").mock(
        return_value=httpx.Response(200, json=[sample_organization.model_dump()])
    )

    respx_mock.get(f"/organizations/{organization_id}/orbits").mock(
        return_value=httpx.Response(200, json=[sample_orbit.model_dump()])
    )

    respx_mock.get(
        f"/organizations/{organization_id}/orbits/{sample_orbit.id}/collections"
    ).mock(return_value=httpx.Response(200, json=[sample_collection.model_dump()]))

    return {
        "organization": sample_organization,
        "orbit": sample_orbit,
        "collection": sample_collection,
    }


@pytest.fixture
def client_with_mocks(mock_initialization_requests: dict) -> LumlClient:
    return LumlClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)


@pytest_asyncio.fixture
async def async_client_with_mocks(
    mock_initialization_requests: dict,
    sample_organization: Organization,
    sample_orbit: Orbit,
    sample_collection: Collection,
) -> AsyncLumlClient:
    client = AsyncLumlClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    await client.setup_config(
        organization=sample_organization.id,
        orbit=sample_orbit.id,
        collection=sample_collection.id,
    )
    return client
