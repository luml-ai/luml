from unittest.mock import AsyncMock, Mock

import pytest

from luml.api._types import ModelArtifact
from luml.api.resources.model_artifacts import (
    AsyncModelArtifactResource,
    ModelArtifactResource,
)


def test_model_artifact_list(
    mock_sync_client: Mock, sample_model_artifact: ModelArtifact
) -> None:
    mock_sync_client.get.return_value = [sample_model_artifact]

    resource = ModelArtifactResource(mock_sync_client)
    artifacts = resource.list()

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{mock_sync_client.organization}/orbits/{mock_sync_client.orbit}/collections/{mock_sync_client.collection}/model_artifacts"
    )
    assert len(artifacts) == 1
    assert artifacts[0].file_name == "model.pkl"


def test_model_artifact_get_by_name(
    mock_sync_client: Mock, sample_model_artifact: ModelArtifact
) -> None:
    model_name = "test-model"
    mock_sync_client.get.return_value = [sample_model_artifact]

    resource = ModelArtifactResource(mock_sync_client)
    artifact = resource.get(collection_id=None, model_value=model_name)

    assert artifact.model_name == model_name


def test_model_artifact_download_url(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/download"}
    mock_sync_client.get.return_value = expected

    resource = ModelArtifactResource(mock_sync_client)
    result = resource.download_url(model_id=model_id)

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}/download-url"
    )
    assert result == expected


def test_model_artifact_list_none_response(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = ModelArtifactResource(mock_sync_client)
    artifacts = resource.list()

    assert len(artifacts) == 0


def test_model_artifact_delete_url(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/delete"}
    mock_sync_client.get.return_value = expected

    resource = ModelArtifactResource(mock_sync_client)
    result = resource.delete_url(model_id=model_id)

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}/delete-url"
    )
    assert result == expected


def test_model_artifact_create(
    mock_sync_client: Mock, sample_model_artifact: ModelArtifact
) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    mock_sync_client.post.return_value = {
        "upload_details": {
            "url": "https://example.com/upload",
            "multipart": False,
            "bucket_location": "test/location",
            "bucket_secret_id": "0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        },
        "model": sample_model_artifact.model_dump(),
    }

    resource = ModelArtifactResource(mock_sync_client)
    artifact = resource.create(
        file_name="model.pkl",
        metrics={},
        manifest={},
        file_hash="abc123",
        file_index={},
        size=1024,
        model_name="test-model",
    )

    expected_json = {
        "file_name": "model.pkl",
        "metrics": {},
        "manifest": {},
        "file_hash": "abc123",
        "file_index": {},
        "size": 1024,
        "model_name": "test-model",
        "description": None,
        "tags": None,
    }

    mock_sync_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts",
        json=expected_json,
    )

    assert artifact.upload_details.url == "https://example.com/upload"
    assert artifact.model.file_name == expected_json["file_name"]


def test_model_artifact_update(
    mock_sync_client: Mock, sample_model_artifact: ModelArtifact
) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    model_name = "updated-model"
    update_data = {"model_name": model_name}
    model = sample_model_artifact.model_copy()
    model.model_name = model_name
    mock_sync_client.patch.return_value = model
    mock_sync_client.filter_none.return_value = update_data

    resource = ModelArtifactResource(mock_sync_client)
    artifact = resource.update(model_id=model_id, model_name=model_name)

    mock_sync_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}",
        json=update_data,
    )
    assert artifact.model_name == model_name


def test_model_artifact_delete(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = mock_sync_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    mock_sync_client.delete.return_value = None

    resource = ModelArtifactResource(mock_sync_client)
    result = resource.delete(model_id=model_id)

    mock_sync_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}"
    )
    assert result is None


@pytest.mark.asyncio
async def test_async_model_artifact_list(
    mock_async_client: AsyncMock, sample_model_artifact: ModelArtifact
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    mock_async_client.get.return_value = [sample_model_artifact]

    resource = AsyncModelArtifactResource(mock_async_client)
    artifacts = await resource.list()

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts"
    )
    assert len(artifacts) == 1
    assert artifacts[0].file_name == "model.pkl"


@pytest.mark.asyncio
async def test_async_model_artifact_get_string(
    mock_async_client: AsyncMock, sample_model_artifact: ModelArtifact
) -> None:
    name = sample_model_artifact.model_name
    mock_async_client.get.return_value = [sample_model_artifact]

    resource = AsyncModelArtifactResource(mock_async_client)
    artifact = await resource.get(model_value=name)

    assert artifact.model_name == name


@pytest.mark.asyncio
async def test_async_model_artifact_get_int(mock_async_client: AsyncMock) -> None:
    model_id = 999999
    resource = AsyncModelArtifactResource(mock_async_client)
    artifact = await resource.get(model_value=model_id)

    assert artifact is None


@pytest.mark.asyncio
async def test_async_model_artifact_get_by_name(
    mock_async_client: AsyncMock, sample_model_artifact: ModelArtifact
) -> None:
    name = sample_model_artifact.model_name
    mock_async_client.get.return_value = [sample_model_artifact]

    resource = AsyncModelArtifactResource(mock_async_client)
    artifact = await resource._get_by_name(collection_id=None, name=name)

    assert artifact.model_name == name


@pytest.mark.asyncio
async def test_async_model_artifact_list_none_response(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get.return_value = None

    resource = AsyncModelArtifactResource(mock_async_client)
    artifacts = await resource.list()

    assert len(artifacts) == 0


@pytest.mark.asyncio
async def test_async_model_artifact_download_url(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/download"}
    mock_async_client.get.return_value = expected

    resource = AsyncModelArtifactResource(mock_async_client)
    result = await resource.download_url(model_id=model_id)

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}/download-url"
    )
    assert result == expected


@pytest.mark.asyncio
async def test_async_model_artifact_delete_url(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    expected = {"url": "https://example.com/delete"}
    mock_async_client.get.return_value = expected

    resource = AsyncModelArtifactResource(mock_async_client)
    result = await resource.delete_url(model_id=model_id)

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}/delete-url"
    )
    assert result == expected


@pytest.mark.asyncio
async def test_async_model_artifact_create(
    mock_async_client: AsyncMock, sample_model_artifact: ModelArtifact
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    mock_async_client.post.return_value = {
        "upload_details": {
            "url": "https://example.com/upload",
            "multipart": False,
            "bucket_location": "test/location",
            "bucket_secret_id": "0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        },
        "model": sample_model_artifact.model_dump(),
    }

    resource = AsyncModelArtifactResource(mock_async_client)
    artifact = await resource.create(
        file_name="model.pkl",
        metrics={},
        manifest={},
        file_hash="abc123",
        file_index={},
        size=1024,
        model_name="test-model",
    )

    expected_json = {
        "file_name": "model.pkl",
        "metrics": {},
        "manifest": {},
        "file_hash": "abc123",
        "file_index": {},
        "size": 1024,
        "model_name": "test-model",
        "description": None,
        "tags": None,
    }

    mock_async_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts",
        json=expected_json,
    )
    assert artifact.upload_details.url == "https://example.com/upload"
    assert artifact.model.file_name == expected_json["file_name"]


@pytest.mark.asyncio
async def test_async_model_artifact_update(
    mock_async_client: AsyncMock, sample_model_artifact: ModelArtifact
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    model_name = "updated-model"
    update_data = {"model_name": model_name}
    model = sample_model_artifact.model_copy()
    model.model_name = model_name
    mock_async_client.patch.return_value = model
    mock_async_client.filter_none.return_value = update_data

    resource = AsyncModelArtifactResource(mock_async_client)
    artifact = await resource.update(model_id=model_id, model_name=model_name)

    mock_async_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}",
        json=update_data,
    )
    assert artifact.model_name == model_name


@pytest.mark.asyncio
async def test_async_model_artifact_delete(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = mock_async_client.collection
    model_id = "1236640f-fec6-478d-8772-90eb531cc727"
    mock_async_client.delete.return_value = None

    resource = AsyncModelArtifactResource(mock_async_client)
    result = await resource.delete(model_id=model_id)

    mock_async_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}/model_artifacts/{model_id}"
    )
    assert result is None
