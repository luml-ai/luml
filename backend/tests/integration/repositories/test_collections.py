import pytest
from luml.repositories.collections import CollectionRepository
from luml.schemas.collections import (
    Collection,
    CollectionCreate,
    CollectionType,
    CollectionUpdate,
)
from luml.schemas.general import PaginationParams
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_sibling_orbit
from tests.support.seeds import CollectionFixtureData, OrbitFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> CollectionRepository:
    return CollectionRepository(engine)


class TestCollectionRepository:
    async def test_create_collection_returns_collection_in_orbit(
        self, repository: CollectionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        collection = CollectionCreate(
            orbit_id=seeded_orbit.orbit.id,
            description="desc",
            name="model-1",
            type=CollectionType.MODEL,
        )
        created = await repository.create_collection(collection)

        assert created.id
        assert created.orbit_id == seeded_orbit.orbit.id
        assert created.name == collection.name

    async def test_get_collection_returns_stored_collection(
        self,
        repository: CollectionRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        fetched_collection = await repository.get_collection(
            seeded_collection.collection.id
        )

        assert fetched_collection
        assert isinstance(fetched_collection, Collection)
        assert fetched_collection.id == seeded_collection.collection.id
        assert fetched_collection.name == seeded_collection.collection.name
        assert (
            fetched_collection.description == seeded_collection.collection.description
        )
        assert fetched_collection.type == seeded_collection.collection.type
        assert fetched_collection.tags == seeded_collection.collection.tags

    async def test_get_orbit_collections_returns_all_orbit_collections(
        self, repository: CollectionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        collections_num = 3
        collections_data = []

        for _ in range(collections_num):
            collection_data = CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection",
                name="collection",
                type=CollectionType.MODEL,
                tags=["tag"],
            )
            created = await repository.create_collection(collection_data)
            collections_data.append(created)

        pagination = PaginationParams(limit=100)
        orbit_collections, cursor = await repository.get_orbit_collections(
            seeded_orbit.orbit.id, pagination
        )

        assert len(orbit_collections) == collections_num

        collection_ids = [c.id for c in orbit_collections]
        for coll in collections_data:
            assert coll.id in collection_ids

    async def test_update_collection_changes_only_given_fields(
        self,
        repository: CollectionRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        update_data = CollectionUpdate(
            id=seeded_collection.collection.id, name="updated-name-only"
        )
        updated_collection = await repository.update_collection(
            seeded_collection.collection.id,
            seeded_collection.collection.orbit_id,
            update_data,
        )

        assert updated_collection
        assert updated_collection.name == update_data.name
        assert (
            updated_collection.description == seeded_collection.collection.description
        )
        assert updated_collection.tags == seeded_collection.collection.tags

    async def test_delete_collection_removes_collection(
        self,
        repository: CollectionRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        fetched = await repository.get_collection(seeded_collection.collection.id)
        assert fetched is not None

        await repository.delete_collection(
            seeded_collection.collection.id, seeded_collection.collection.orbit_id
        )

        fetched_after_delete = await repository.get_collection(
            seeded_collection.collection.id
        )
        assert fetched_after_delete is None

    async def test_update_collection_returns_none_when_orbit_differs(
        self,
        repository: CollectionRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        sibling_orbit = await create_sibling_orbit(
            seeded_collection.engine,
            seeded_collection.organization.id,
            seeded_collection.bucket_secret.id,
        )

        result = await repository.update_collection(
            seeded_collection.collection.id,
            sibling_orbit.id,
            CollectionUpdate(name="renamed"),
        )

        assert result is None

        untouched = await repository.get_collection(seeded_collection.collection.id)
        assert untouched is not None
        assert untouched.name == seeded_collection.collection.name
        assert untouched.orbit_id == seeded_collection.collection.orbit_id

    async def test_delete_collection_keeps_collection_when_orbit_differs(
        self,
        repository: CollectionRepository,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        sibling_orbit = await create_sibling_orbit(
            seeded_collection.engine,
            seeded_collection.organization.id,
            seeded_collection.bucket_secret.id,
        )

        await repository.delete_collection(
            seeded_collection.collection.id, sibling_orbit.id
        )

        assert (
            await repository.get_collection(seeded_collection.collection.id) is not None
        )

    async def test_get_orbit_collections_returns_matches_when_searching_by_name(
        self, repository: CollectionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        collections_data = [
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="First collection",
                name="my-model-collection",
                type=CollectionType.MODEL,
                tags=["tag1"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Second collection",
                name="dataset-collection",
                type=CollectionType.DATASET,
                tags=["tag2"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Third collection",
                name="another-model",
                type=CollectionType.MODEL,
                tags=["tag3"],
            ),
        ]

        for collection_data in collections_data:
            await repository.create_collection(collection_data)

        pagination = PaginationParams(limit=100)
        search_results, cursor = await repository.get_orbit_collections(
            seeded_orbit.orbit.id, pagination, search="model"
        )

        assert len(search_results) == 2
        names = [c.name for c in search_results]
        assert "my-model-collection" in names
        assert "another-model" in names
        assert "dataset-collection" not in names

    async def test_get_orbit_collections_returns_matches_when_searching_by_tag(
        self, repository: CollectionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        collections_data = [
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 1",
                name="collection-1",
                type=CollectionType.MODEL,
                tags=["production", "ml-model"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 2",
                name="collection-2",
                type=CollectionType.DATASET,
                tags=["staging", "dataset"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 3",
                name="collection-3",
                type=CollectionType.MODEL,
                tags=["production", "dataset"],
            ),
        ]

        for collection_data in collections_data:
            await repository.create_collection(collection_data)

        pagination = PaginationParams(limit=100)
        search_results, cursor = await repository.get_orbit_collections(
            seeded_orbit.orbit.id, pagination, search="production"
        )

        assert len(search_results) == 2
        names = [c.name for c in search_results]
        assert "collection-1" in names
        assert "collection-3" in names
        assert "collection-2" not in names

    async def test_get_orbit_collections_filters_by_any_given_tag(
        self, repository: CollectionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        collections_data = [
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 1",
                name="collection-1",
                type=CollectionType.MODEL,
                tags=["production", "ml-model"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 2",
                name="collection-2",
                type=CollectionType.DATASET,
                tags=["staging"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 3",
                name="collection-3",
                type=CollectionType.MODEL,
                tags=None,
            ),
        ]

        for collection_data in collections_data:
            await repository.create_collection(collection_data)

        pagination = PaginationParams(limit=100)

        filtered, _ = await repository.get_orbit_collections(
            seeded_orbit.orbit.id, pagination, tags=["production"]
        )
        assert [c.name for c in filtered] == ["collection-1"]

        filtered, _ = await repository.get_orbit_collections(
            seeded_orbit.orbit.id, pagination, tags=["production", "staging"]
        )
        names = [c.name for c in filtered]
        assert len(filtered) == 2
        assert "collection-1" in names
        assert "collection-2" in names

        filtered, _ = await repository.get_orbit_collections(
            seeded_orbit.orbit.id, pagination, tags=["nonexistent"]
        )
        assert filtered == []

    async def test_get_orbit_collections_tags_returns_sorted_distinct_tags(
        self, repository: CollectionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        collections_data = [
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 1",
                name="collection-1",
                type=CollectionType.MODEL,
                tags=["production", "ml-model"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 2",
                name="collection-2",
                type=CollectionType.DATASET,
                tags=["staging", "production"],
            ),
            CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description="Collection 3",
                name="collection-3",
                type=CollectionType.MODEL,
                tags=None,
            ),
        ]

        for collection_data in collections_data:
            await repository.create_collection(collection_data)

        tags = await repository.get_orbit_collections_tags(seeded_orbit.orbit.id)

        assert tags == ["ml-model", "production", "staging"]
