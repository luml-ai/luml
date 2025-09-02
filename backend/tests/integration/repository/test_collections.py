import pytest

from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.schemas.model_artifacts import (
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

    orbit_collections = await repo.get_orbit_collections(orbit.id)

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
