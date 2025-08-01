import pytest

from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.schemas.model_artifacts import CollectionCreate, CollectionType


@pytest.mark.asyncio
async def test_create_collection(create_orbit: dict) -> None:
    data = create_orbit
    engine, orbit = data["engine"], data["orbit"]
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
