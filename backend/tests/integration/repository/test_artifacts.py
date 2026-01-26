import uuid

import pytest
from luml.infra.exceptions import DatabaseConstraintError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactStatus,
    ArtifactUpdate,
)
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.general import PaginationParams
from luml.schemas.satellite import SatelliteCreate

from tests.conftest import CollectionFixtureData


@pytest.mark.asyncio
async def test_create_artifact(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_artifact(model)

    assert created_model
    assert created_model.collection_id == model.collection_id
    assert created_model.file_name == model.file_name
    assert created_model.name == model.name
    assert created_model.extra_values == model.extra_values
    assert created_model.file_hash == model.file_hash
    assert created_model.bucket_location == model.bucket_location
    assert created_model.size == model.size
    assert created_model.unique_identifier == model.unique_identifier
    assert created_model.tags == model.tags
    assert created_model.status == model.status


@pytest.mark.asyncio
async def test_get_artifact(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_artifact(model)
    fetched_model = await repo.get_artifact(created_model.id)

    assert fetched_model
    assert fetched_model.id == created_model.id
    assert fetched_model.collection_id == collection.id


@pytest.mark.asyncio
async def test_get_collection_artifacts(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)
    limit = 100

    model_data1 = test_artifact.model_copy()
    model_data1.collection_id = collection.id
    model_data1.unique_identifier = "uid1"

    model_data2 = test_artifact.model_copy()
    model_data2.collection_id = collection.id
    model_data2.unique_identifier = "uid2"

    created_model1 = await repo.create_artifact(model_data1)
    created_model2 = await repo.create_artifact(model_data2)

    pagination = PaginationParams(limit=limit)
    models = await repo.get_collection_artifacts(collection.id, pagination)

    assert len(models) == 2
    model_ids = [m.id for m in models]
    assert created_model1.id in model_ids
    assert created_model2.id in model_ids


@pytest.mark.asyncio
async def test_get_collection_artifacts_count(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    count = await repo.get_collection_artifacts_count(collection.id)
    assert count == 0

    model = test_artifact.model_copy()
    model.collection_id = collection.id
    await repo.create_artifact(model)

    count = await repo.get_collection_artifacts_count(collection.id)
    assert count == 1


@pytest.mark.asyncio
async def test_update_status(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_artifact(model)
    assert created_model.status == ArtifactStatus.PENDING_UPLOAD

    updated_model = await repo.update_status(created_model.id, ArtifactStatus.UPLOADED)

    assert updated_model
    assert updated_model.id == created_model.id
    assert updated_model.status == ArtifactStatus.UPLOADED


@pytest.mark.asyncio
async def test_update_artifact(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_artifact(model)

    update_data = ArtifactUpdate(
        id=created_model.id, name="Updated Model Name", tags=["updated"]
    )
    updated_model = await repo.update_artifact(
        created_model.id, collection.id, update_data
    )

    assert updated_model
    assert updated_model.id == created_model.id
    assert updated_model.name == update_data.name
    assert updated_model.tags == update_data.tags


@pytest.mark.asyncio
async def test_delete_artifact(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_artifact(model)

    await repo.delete_artifact(created_model.id)

    fetched_model = await repo.get_artifact(created_model.id)
    assert fetched_model is None


@pytest.mark.asyncio
async def test_delete_artifact_with_deployment_constraint(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, orbit, collection = data.engine, data.orbit, data.collection
    repo = ArtifactRepository(engine)
    satellite_repo = SatelliteRepository(engine)
    deployment_repo = DeploymentRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_artifact(model)

    satellite = await satellite_repo.create_satellite(
        SatelliteCreate(
            orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test_satellite"
        )
    )

    deployment_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        artifact_id=created_model.id,
        status=DeploymentStatus.PENDING,
    )
    await deployment_repo.create_deployment(deployment_data)

    with pytest.raises(DatabaseConstraintError) as error:
        await repo.delete_artifact(created_model.id)

    assert error.value.status_code == 409
