from unittest.mock import AsyncMock, Mock

import pytest

from dataforce.api._types import Collection, CollectionType
from dataforce.api.resources.collections import (
    AsyncCollectionResource,
    CollectionResource,
)


def test_collection_get(mock_sync_client: Mock, sample_collection: Collection) -> None:
    collection_name = sample_collection.name
    mock_sync_client.get.return_value = [sample_collection]

    resource = CollectionResource(mock_sync_client)
    collection = resource.get(collection_name)

    assert collection.name == collection_name


def test_collection_get_by_name(
    mock_sync_client: Mock, sample_collection: Collection
) -> None:
    collection_name = sample_collection.name
    mock_sync_client.get.return_value = [sample_collection]

    resource = CollectionResource(mock_sync_client)
    collection = resource._get_by_name(collection_name)

    assert collection.name == collection_name


def test_collection_list(mock_sync_client: Mock, sample_collection: Collection) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    mock_sync_client.get.return_value = [sample_collection]

    resource = CollectionResource(mock_sync_client)
    collections = resource.list()

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections"
    )
    assert len(collections) == 1
    assert collections[0].name == sample_collection.name


def test_collection_list_none_response(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = CollectionResource(mock_sync_client)
    collections = resource.list()

    assert len(collections) == 0


def test_collection_create(
    mock_sync_client: Mock, sample_collection: Collection
) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    mock_sync_client.post.return_value = sample_collection

    resource = CollectionResource(mock_sync_client)
    collection = resource.create(
        description="Test Description",
        name="Test Collection",
        collection_type=CollectionType.MODEL,
        tags=["tag1", "tag2"],
    )

    expected_json = {
        "description": "Test Description",
        "name": "Test Collection",
        "collection_type": CollectionType.MODEL,
        "tags": ["tag1", "tag2"],
    }

    mock_sync_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
        json=expected_json,
    )
    assert isinstance(collection, Collection)


def test_collection_create_no_tags(
    mock_sync_client: Mock, sample_collection: Collection
) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    mock_sync_client.post.return_value = sample_collection

    resource = CollectionResource(mock_sync_client)
    collection = resource.create(
        description="Test Description",
        name="Test Collection",
        collection_type=CollectionType.DATASET,
    )

    expected_json = {
        "description": "Test Description",
        "name": "Test Collection",
        "collection_type": CollectionType.DATASET,
        "tags": None,
    }

    mock_sync_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
        json=expected_json,
    )
    assert isinstance(collection, Collection)


def test_collection_update(
    mock_sync_client: Mock, sample_collection: Collection
) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = sample_collection.id
    update_data = {"name": "Updated Collection"}

    mock_sync_client.patch.return_value = sample_collection
    mock_sync_client.filter_none.return_value = update_data

    resource = CollectionResource(mock_sync_client)
    collection = resource.update(collection_id=collection_id, name="Updated Collection")

    mock_sync_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
        json=update_data,
    )
    assert isinstance(collection, Collection)


def test_collection_update_all_params(
    mock_sync_client: Mock, sample_collection: Collection
) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = sample_collection.id
    update_data = {
        "description": "Updated Description",
        "name": "Updated Collection",
        "tags": ["new_tag"],
    }

    mock_sync_client.patch.return_value = sample_collection
    mock_sync_client.filter_none.return_value = update_data

    resource = CollectionResource(mock_sync_client)
    collection = resource.update(
        collection_id=collection_id,
        description="Updated Description",
        name="Updated Collection",
        tags=["new_tag"],
    )

    mock_sync_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
        json=update_data,
    )
    assert isinstance(collection, Collection)


def test_collection_delete(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    collection_id = 15
    mock_sync_client.delete.return_value = None

    resource = CollectionResource(mock_sync_client)
    result = resource.delete(collection_id=collection_id)

    mock_sync_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}"
    )
    assert result is None


@pytest.mark.asyncio
async def test_async_collection_get(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    collection_name = sample_collection.name
    mock_async_client.get.return_value = [sample_collection]

    resource = AsyncCollectionResource(mock_async_client)
    collection = await resource.get(collection_name)

    assert collection.name == collection_name


@pytest.mark.asyncio
async def test_async_collection_get_by_name(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    collection_name = sample_collection.name
    mock_async_client.get.return_value = [sample_collection]

    resource = AsyncCollectionResource(mock_async_client)
    collection = await resource._get_by_name(collection_name)

    assert collection.name == collection_name


@pytest.mark.asyncio
async def test_async_collection_list(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    mock_async_client.get.return_value = [sample_collection]

    resource = AsyncCollectionResource(mock_async_client)
    collections = await resource.list()

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections"
    )
    assert len(collections) == 1
    assert collections[0].name == sample_collection.name


@pytest.mark.asyncio
async def test_async_collection_list_none_response(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get.return_value = None

    resource = AsyncCollectionResource(mock_async_client)
    collections = await resource.list()

    assert len(collections) == 0


@pytest.mark.asyncio
async def test_async_collection_create(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    mock_async_client.post.return_value = sample_collection

    resource = AsyncCollectionResource(mock_async_client)
    collection = await resource.create(
        description="Test Description",
        name="Test Collection",
        collection_type=CollectionType.MODEL,
        tags=["tag1", "tag2"],
    )

    expected_json = {
        "description": "Test Description",
        "name": "Test Collection",
        "collection_type": CollectionType.MODEL,
        "tags": ["tag1", "tag2"],
    }

    mock_async_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
        json=expected_json,
    )
    assert isinstance(collection, Collection)


@pytest.mark.asyncio
async def test_async_collection_create_no_tags(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    mock_async_client.post.return_value = sample_collection

    resource = AsyncCollectionResource(mock_async_client)
    collection = await resource.create(
        description="Test Description",
        name="Test Collection",
        collection_type=CollectionType.DATASET,
    )

    expected_json = {
        "description": "Test Description",
        "name": "Test Collection",
        "collection_type": CollectionType.DATASET,
        "tags": None,
    }

    mock_async_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
        json=expected_json,
    )
    assert isinstance(collection, Collection)


@pytest.mark.asyncio
async def test_async_collection_update(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = sample_collection.id
    update_data = {"name": "Updated Collection"}

    mock_async_client.patch.return_value = sample_collection
    mock_async_client.filter_none.return_value = update_data

    resource = AsyncCollectionResource(mock_async_client)
    collection = await resource.update(collection_id=collection_id, name="Updated Collection")

    mock_async_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
        json=update_data,
    )
    assert isinstance(collection, Collection)


@pytest.mark.asyncio
async def test_async_collection_update_all_params(
    mock_async_client: AsyncMock, sample_collection: Collection
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = sample_collection.id
    update_data = {
        "description": "Updated Description",
        "name": "Updated Collection",
        "tags": ["new_tag"],
    }

    mock_async_client.patch.return_value = sample_collection
    mock_async_client.filter_none.return_value = update_data

    resource = AsyncCollectionResource(mock_async_client)
    collection = await resource.update(
        collection_id=collection_id,
        description="Updated Description",
        name="Updated Collection",
        tags=["new_tag"],
    )

    mock_async_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
        json=update_data,
    )
    assert isinstance(collection, Collection)


@pytest.mark.asyncio
async def test_async_collection_delete(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    collection_id = 15
    mock_async_client.delete.return_value = None

    resource = AsyncCollectionResource(mock_async_client)
    result = await resource.delete(collection_id=collection_id)

    mock_async_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}"
    )
    assert result is None
