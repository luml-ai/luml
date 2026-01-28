from unittest.mock import AsyncMock, Mock

import pytest

from luml.api._types import Artifact, BucketType
from luml.api.resources.artifacts import (
    ArtifactResource,
    AsyncArtifactResource,
)


def test_artifact_list(mock_sync_client: Mock, sample_artifact: Artifact) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    mock_sync_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }

    resource = ArtifactResource(mock_sync_client)
    artifacts = resource.list()

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts",
        params={"limit": 100, "order": "desc"},
    )
    assert len(artifacts.items) == 1
    assert artifacts.items[0].file_name == "model.pkl"


def test_artifact_get_by_name(
    mock_sync_client: Mock, sample_artifact: Artifact
) -> None:
    name = "test-model"
    mock_sync_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }

    resource = ArtifactResource(mock_sync_client)
    artifact = resource.get(artifact_value=name)

    assert artifact.name == name


def test_artifact_download_url(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/download"}
    mock_sync_client.get.return_value = expected

    resource = ArtifactResource(mock_sync_client)
    result = resource.download_url(artifact_id=artifact_id)

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}/download-url"
    )
    assert result == expected


def test_artifact_list_none_response(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = ArtifactResource(mock_sync_client)
    artifacts = resource.list()

    assert len(artifacts.items) == 0


def test_artifact_delete_url(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/delete"}
    mock_sync_client.get.return_value = expected

    resource = ArtifactResource(mock_sync_client)
    result = resource.delete_url(artifact_id=artifact_id)

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}/delete-url"
    )
    assert result == expected


def test_artifact_create(mock_sync_client: Mock, sample_artifact: Artifact) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    mock_sync_client.post.return_value = {
        "upload_details": {
            "type": BucketType.S3,
            "url": "https://example.com/upload",
            "multipart": False,
            "bucket_location": "test/location",
            "bucket_secret_id": "0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        },
        "artifact": sample_artifact.model_dump(),
    }

    resource = ArtifactResource(mock_sync_client)
    result = resource.create(
        file_name="model.pkl",
        extra_values={},
        manifest={},
        file_hash="abc123",
        file_index={},
        size=1024,
        name="test-model",
    )

    expected_json = {
        "file_name": "model.pkl",
        "extra_values": {},
        "manifest": {},
        "file_hash": "abc123",
        "file_index": {},
        "size": 1024,
        "name": "test-model",
        "description": None,
        "tags": None,
    }

    mock_sync_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts",
        json=expected_json,
    )

    assert result.upload_details.url == "https://example.com/upload"
    assert result.artifact.file_name == expected_json["file_name"]


def test_artifact_update(mock_sync_client: Mock, sample_artifact: Artifact) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    name = "updated-model"
    update_data = {"name": name}
    model = sample_artifact.model_copy()
    model.name = name
    mock_sync_client.patch.return_value = model
    mock_sync_client.filter_none.return_value = update_data

    resource = ArtifactResource(mock_sync_client)
    artifact = resource.update(artifact_id=artifact_id, name=name)

    mock_sync_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}",
        json=update_data,
    )
    assert artifact.name == name


def test_artifact_delete(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    mock_sync_client.delete.return_value = None

    resource = ArtifactResource(mock_sync_client)
    result = resource.delete(artifact_id=artifact_id)

    mock_sync_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}"
    )
    assert result is None


@pytest.mark.asyncio
async def test_async_artifact_list(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    mock_async_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }

    resource = AsyncArtifactResource(mock_async_client)
    artifacts = await resource.list()

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts",
        params={"limit": 100, "order": "desc"},
    )
    assert len(artifacts.items) == 1
    assert artifacts.items[0].file_name == "model.pkl"


@pytest.mark.asyncio
async def test_async_artifact_get_string(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    name = sample_artifact.name
    mock_async_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }

    resource = AsyncArtifactResource(mock_async_client)
    artifact = await resource.get(artifact_value=name)

    assert artifact.name == name


@pytest.mark.asyncio
async def test_async_artifact_get_int(mock_async_client: AsyncMock) -> None:
    artifact_id = "999999"
    mock_async_client.get.return_value = {"items": [], "cursor": None}

    resource = AsyncArtifactResource(mock_async_client)
    artifact = await resource.get(artifact_value=artifact_id)

    assert artifact is None


@pytest.mark.asyncio
async def test_async_artifact_get_by_name(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    name = sample_artifact.name
    mock_async_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }

    resource = AsyncArtifactResource(mock_async_client)
    artifact = await resource._get_by_name(
        collection_id=mock_async_client.collection, name=name
    )

    assert artifact is not None
    assert artifact.name == name


@pytest.mark.asyncio
async def test_async_artifact_list_none_response(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get.return_value = None

    resource = AsyncArtifactResource(mock_async_client)
    artifacts = await resource.list()

    assert len(artifacts.items) == 0


@pytest.mark.asyncio
async def test_async_artifact_download_url(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/download"}
    mock_async_client.get.return_value = expected

    resource = AsyncArtifactResource(mock_async_client)
    result = await resource.download_url(artifact_id=artifact_id)

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}/download-url"
    )
    assert result == expected


@pytest.mark.asyncio
async def test_async_artifact_delete_url(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/delete"}
    mock_async_client.get.return_value = expected

    resource = AsyncArtifactResource(mock_async_client)
    result = await resource.delete_url(artifact_id=artifact_id)

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}/delete-url"
    )
    assert result == expected


@pytest.mark.asyncio
async def test_async_artifact_create(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    mock_async_client.post.return_value = {
        "upload_details": {
            "type": BucketType.S3,
            "url": "https://example.com/upload",
            "multipart": False,
            "bucket_location": "test/location",
            "bucket_secret_id": "0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        },
        "artifact": sample_artifact.model_dump(),
    }

    resource = AsyncArtifactResource(mock_async_client)
    result = await resource.create(
        file_name="model.pkl",
        extra_values={},
        manifest={},
        file_hash="abc123",
        file_index={},
        size=1024,
        name="test-model",
    )

    expected_json = {
        "file_name": "model.pkl",
        "extra_values": {},
        "manifest": {},
        "file_hash": "abc123",
        "file_index": {},
        "size": 1024,
        "name": "test-model",
        "description": None,
        "tags": None,
    }

    mock_async_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts",
        json=expected_json,
    )
    assert result.upload_details.url == "https://example.com/upload"
    assert result.artifact.file_name == expected_json["file_name"]


@pytest.mark.asyncio
async def test_async_artifact_update(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    name = "updated-model"
    update_data = {"name": name}
    model = sample_artifact.model_copy()
    model.name = name
    mock_async_client.patch.return_value = model
    mock_async_client.filter_none.return_value = update_data

    resource = AsyncArtifactResource(mock_async_client)
    artifact = await resource.update(artifact_id=artifact_id, name=name)

    mock_async_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}",
        json=update_data,
    )
    assert artifact.name == name


@pytest.mark.asyncio
async def test_async_artifact_delete(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    artifact_id = "1236640f-fec6-478d-8772-90eb531cc727"
    mock_async_client.delete.return_value = None

    resource = AsyncArtifactResource(mock_async_client)
    result = await resource.delete(artifact_id=artifact_id)

    mock_async_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/artifacts/{artifact_id}"
    )
    assert result is None
