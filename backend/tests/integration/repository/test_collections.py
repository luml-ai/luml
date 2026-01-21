import pytest
from luml.repositories.collections import CollectionRepository
from luml.schemas.general import PaginationParams
from luml.schemas.model_artifacts import (
    Collection,
    CollectionCreate,
    CollectionType,
    CollectionUpdate,
)

from tests.conftest import CollectionFixtureData, OrbitFixtureData


@pytest.mark.asyncio
async def test_create_collection(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = CollectionRepository(engine)

    collection = CollectionCreate(
        orbit_id=orbit.id,
        description="desc",
        name="model-1",
        collection_type=CollectionType.MODEL,
    )
    created = await repo.create_collection(collection)

    assert created.id
    assert created.orbit_id == orbit.id
    assert created.name == collection.name


@pytest.mark.asyncio
async def test_get_collection(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = CollectionRepository(engine)

    fetched_collection = await repo.get_collection(collection.id)

    assert fetched_collection
    assert isinstance(fetched_collection, Collection)
    assert fetched_collection.id == collection.id
    assert fetched_collection.name == collection.name
    assert fetched_collection.description == collection.description
    assert fetched_collection.collection_type == collection.collection_type
    assert fetched_collection.tags == collection.tags


@pytest.mark.asyncio
async def test_get_orbit_collections(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = CollectionRepository(engine)
    collections_num = 3
    collections_data = []

    for _ in range(collections_num):
        collection_data = CollectionCreate(
            orbit_id=orbit.id,
            description="Collection",
            name="collection",
            collection_type=CollectionType.MODEL,
            tags=["tag"],
        )
        created = await repo.create_collection(collection_data)
        collections_data.append(created)

    pagination = PaginationParams(limit=100)
    orbit_collections = await repo.get_orbit_collections(orbit.id, pagination)

    assert len(orbit_collections) == collections_num

    collection_ids = [c.id for c in orbit_collections]
    for coll in collections_data:
        assert coll.id in collection_ids


@pytest.mark.asyncio
async def test_update_collection_partial(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = CollectionRepository(engine)

    update_data = CollectionUpdate(id=collection.id, name="updated-name-only")
    updated_collection = await repo.update_collection(collection.id, update_data)

    assert updated_collection
    assert updated_collection.name == update_data.name
    assert updated_collection.description == collection.description
    assert updated_collection.tags == collection.tags


@pytest.mark.asyncio
async def test_delete_collection(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = CollectionRepository(engine)

    fetched = await repo.get_collection(collection.id)
    assert fetched is not None

    await repo.delete_collection(collection.id)

    fetched_after_delete = await repo.get_collection(collection.id)
    assert fetched_after_delete is None


@pytest.mark.asyncio
async def test_get_orbit_collections_search_by_name(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = CollectionRepository(engine)

    collections_data = [
        CollectionCreate(
            orbit_id=orbit.id,
            description="First collection",
            name="my-model-collection",
            collection_type=CollectionType.MODEL,
            tags=["tag1"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Second collection",
            name="dataset-collection",
            collection_type=CollectionType.DATASET,
            tags=["tag2"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Third collection",
            name="another-model",
            collection_type=CollectionType.MODEL,
            tags=["tag3"],
        ),
    ]

    for collection_data in collections_data:
        await repo.create_collection(collection_data)

    pagination = PaginationParams(limit=100)
    search_results = await repo.get_orbit_collections(
        orbit.id, pagination, search="model"
    )

    assert len(search_results) == 2
    names = [c.name for c in search_results]
    assert "my-model-collection" in names
    assert "another-model" in names
    assert "dataset-collection" not in names


@pytest.mark.asyncio
async def test_get_orbit_collections_search_by_tags(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = CollectionRepository(engine)

    collections_data = [
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 1",
            name="collection-1",
            collection_type=CollectionType.MODEL,
            tags=["production", "ml-model"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 2",
            name="collection-2",
            collection_type=CollectionType.DATASET,
            tags=["staging", "dataset"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 3",
            name="collection-3",
            collection_type=CollectionType.MODEL,
            tags=["production", "dataset"],
        ),
    ]

    for collection_data in collections_data:
        await repo.create_collection(collection_data)

    pagination = PaginationParams(limit=100)
    search_results = await repo.get_orbit_collections(
        orbit.id, pagination, search="production"
    )

    assert len(search_results) == 2
    names = [c.name for c in search_results]
    assert "collection-1" in names
    assert "collection-3" in names
    assert "collection-2" not in names
