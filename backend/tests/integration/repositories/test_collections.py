import pytest
from luml.repositories.collections import CollectionRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.collections import (
    Collection,
    CollectionCreate,
    CollectionType,
    CollectionUpdate,
)
from luml.schemas.general import PaginationParams
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails

from tests.conftest import CollectionFixtureData, OrbitFixtureData


async def _create_sibling_orbit(data: OrbitFixtureData) -> OrbitDetails:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="sibling orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert orbit is not None
    return orbit


@pytest.mark.asyncio
async def test_create_collection(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = CollectionRepository(engine)

    collection = CollectionCreate(
        orbit_id=orbit.id,
        description="desc",
        name="model-1",
        type=CollectionType.MODEL,
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
    assert fetched_collection.type == collection.type
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
            type=CollectionType.MODEL,
            tags=["tag"],
        )
        created = await repo.create_collection(collection_data)
        collections_data.append(created)

    pagination = PaginationParams(limit=100)
    orbit_collections, cursor = await repo.get_orbit_collections(orbit.id, pagination)

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
    updated_collection = await repo.update_collection(
        collection.id, collection.orbit_id, update_data
    )

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

    await repo.delete_collection(collection.id, collection.orbit_id)

    fetched_after_delete = await repo.get_collection(collection.id)
    assert fetched_after_delete is None


@pytest.mark.asyncio
async def test_update_collection_from_another_orbit(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = CollectionRepository(data.engine)
    collection = data.collection
    sibling_orbit = await _create_sibling_orbit(data)

    result = await repo.update_collection(
        collection.id, sibling_orbit.id, CollectionUpdate(name="renamed")
    )

    assert result is None

    untouched = await repo.get_collection(collection.id)
    assert untouched is not None
    assert untouched.name == collection.name
    assert untouched.orbit_id == collection.orbit_id


@pytest.mark.asyncio
async def test_delete_collection_from_another_orbit(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = CollectionRepository(data.engine)
    collection = data.collection
    sibling_orbit = await _create_sibling_orbit(data)

    await repo.delete_collection(collection.id, sibling_orbit.id)

    assert await repo.get_collection(collection.id) is not None


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
            type=CollectionType.MODEL,
            tags=["tag1"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Second collection",
            name="dataset-collection",
            type=CollectionType.DATASET,
            tags=["tag2"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Third collection",
            name="another-model",
            type=CollectionType.MODEL,
            tags=["tag3"],
        ),
    ]

    for collection_data in collections_data:
        await repo.create_collection(collection_data)

    pagination = PaginationParams(limit=100)
    search_results, cursor = await repo.get_orbit_collections(
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
            type=CollectionType.MODEL,
            tags=["production", "ml-model"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 2",
            name="collection-2",
            type=CollectionType.DATASET,
            tags=["staging", "dataset"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 3",
            name="collection-3",
            type=CollectionType.MODEL,
            tags=["production", "dataset"],
        ),
    ]

    for collection_data in collections_data:
        await repo.create_collection(collection_data)

    pagination = PaginationParams(limit=100)
    search_results, cursor = await repo.get_orbit_collections(
        orbit.id, pagination, search="production"
    )

    assert len(search_results) == 2
    names = [c.name for c in search_results]
    assert "collection-1" in names
    assert "collection-3" in names
    assert "collection-2" not in names


@pytest.mark.asyncio
async def test_get_orbit_collections_filter_by_tags(
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
            type=CollectionType.MODEL,
            tags=["production", "ml-model"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 2",
            name="collection-2",
            type=CollectionType.DATASET,
            tags=["staging"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 3",
            name="collection-3",
            type=CollectionType.MODEL,
            tags=None,
        ),
    ]

    for collection_data in collections_data:
        await repo.create_collection(collection_data)

    pagination = PaginationParams(limit=100)

    filtered, _ = await repo.get_orbit_collections(
        orbit.id, pagination, tags=["production"]
    )
    assert [c.name for c in filtered] == ["collection-1"]

    filtered, _ = await repo.get_orbit_collections(
        orbit.id, pagination, tags=["production", "staging"]
    )
    names = [c.name for c in filtered]
    assert len(filtered) == 2
    assert "collection-1" in names
    assert "collection-2" in names

    filtered, _ = await repo.get_orbit_collections(
        orbit.id, pagination, tags=["nonexistent"]
    )
    assert filtered == []


@pytest.mark.asyncio
async def test_get_orbit_collections_tags(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = CollectionRepository(engine)

    collections_data = [
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 1",
            name="collection-1",
            type=CollectionType.MODEL,
            tags=["production", "ml-model"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 2",
            name="collection-2",
            type=CollectionType.DATASET,
            tags=["staging", "production"],
        ),
        CollectionCreate(
            orbit_id=orbit.id,
            description="Collection 3",
            name="collection-3",
            type=CollectionType.MODEL,
            tags=None,
        ),
    ]

    for collection_data in collections_data:
        await repo.create_collection(collection_data)

    tags = await repo.get_orbit_collections_tags(orbit.id)

    assert tags == ["ml-model", "production", "staging"]
