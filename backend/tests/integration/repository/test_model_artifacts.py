import uuid

import pytest
from luml.infra.exceptions import DatabaseConstraintError
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.model_artifacts import ModelArtifactRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.model_artifacts import (
    ModelArtifactCreate,
    ModelArtifactStatus,
    ModelArtifactUpdate,
)
from luml.schemas.satellite import SatelliteCreate

from tests.conftest import CollectionFixtureData


@pytest.mark.asyncio
async def test_create_model_artifact(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_model_artifact(model)

    assert created_model
    assert created_model.collection_id == model.collection_id
    assert created_model.file_name == model.file_name
    assert created_model.model_name == model.model_name
    assert created_model.metrics == model.metrics
    assert created_model.file_hash == model.file_hash
    assert created_model.bucket_location == model.bucket_location
    assert created_model.size == model.size
    assert created_model.unique_identifier == model.unique_identifier
    assert created_model.tags == model.tags
    assert created_model.status == model.status


@pytest.mark.asyncio
async def test_get_model_artifact(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_model_artifact(model)
    fetched_model = await repo.get_model_artifact(created_model.id)

    assert fetched_model
    assert fetched_model.id == created_model.id
    assert fetched_model.collection_id == collection.id


@pytest.mark.asyncio
async def test_get_collection_model_artifacts(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)
    limit = 100

    model_data1 = test_model_artifact.model_copy()
    model_data1.collection_id = collection.id
    model_data1.unique_identifier = "uid1"

    model_data2 = test_model_artifact.model_copy()
    model_data2.collection_id = collection.id
    model_data2.unique_identifier = "uid2"

    created_model1 = await repo.create_model_artifact(model_data1)
    created_model2 = await repo.create_model_artifact(model_data2)

    models = await repo.get_collection_model_artifacts(collection.id, limit)

    assert len(models) == 2
    model_ids = [m.id for m in models]
    assert created_model1.id in model_ids
    assert created_model2.id in model_ids


@pytest.mark.asyncio
async def test_get_collection_model_artifacts_count(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)

    count = await repo.get_collection_model_artifacts_count(collection.id)
    assert count == 0

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id
    await repo.create_model_artifact(model)

    count = await repo.get_collection_model_artifacts_count(collection.id)
    assert count == 1


@pytest.mark.asyncio
async def test_update_status(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_model_artifact(model)
    assert created_model.status == ModelArtifactStatus.PENDING_UPLOAD

    updated_model = await repo.update_status(
        created_model.id, ModelArtifactStatus.UPLOADED
    )

    assert updated_model
    assert updated_model.id == created_model.id
    assert updated_model.status == ModelArtifactStatus.UPLOADED


@pytest.mark.asyncio
async def test_update_model_artifact(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_model_artifact(model)

    update_data = ModelArtifactUpdate(
        id=created_model.id, model_name="Updated Model Name", tags=["updated"]
    )
    updated_model = await repo.update_model_artifact(
        created_model.id, collection.id, update_data
    )

    assert updated_model
    assert updated_model.id == created_model.id
    assert updated_model.model_name == update_data.model_name
    assert updated_model.tags == update_data.tags


@pytest.mark.asyncio
async def test_delete_model_artifact(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ModelArtifactRepository(engine)

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_model_artifact(model)

    await repo.delete_model_artifact(created_model.id)

    fetched_model = await repo.get_model_artifact(created_model.id)
    assert fetched_model is None


@pytest.mark.asyncio
async def test_delete_model_artifact_with_deployment_constraint(
    create_collection: CollectionFixtureData, test_model_artifact: ModelArtifactCreate
) -> None:
    data = create_collection
    engine, orbit, collection = data.engine, data.orbit, data.collection
    repo = ModelArtifactRepository(engine)
    satellite_repo = SatelliteRepository(engine)
    deployment_repo = DeploymentRepository(engine)

    model = test_model_artifact.model_copy()
    model.collection_id = collection.id

    created_model = await repo.create_model_artifact(model)

    satellite = await satellite_repo.create_satellite(
        SatelliteCreate(
            orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test_satellite"
        )
    )

    deployment_data = DeploymentCreate(
        name="my-deployment",
        orbit_id=orbit.id,
        satellite_id=satellite.id,
        model_id=created_model.id,
        status=DeploymentStatus.PENDING,
    )
    await deployment_repo.create_deployment(deployment_data)

    with pytest.raises(DatabaseConstraintError) as error:
        await repo.delete_model_artifact(created_model.id)

    assert error.value.status_code == 409
