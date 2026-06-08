import uuid

import pytest
from luml.infra.exceptions import DatabaseConstraintError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
)
from luml.schemas.collections import CollectionCreate, CollectionType
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.general import PaginationParams
from luml.schemas.satellite import SatelliteCreate

from tests.conftest import CollectionFixtureData


async def _make_artifact(
    repo: ArtifactRepository,
    template: ArtifactCreate,
    collection_id: uuid.UUID,
    *,
    name: str,
    artifact_type: ArtifactType = ArtifactType.MODEL,
    unique_identifier: str | None = None,
) -> Artifact:
    model = template.model_copy()
    model.collection_id = collection_id
    model.name = name
    model.type = artifact_type
    model.unique_identifier = unique_identifier or str(uuid.uuid4())
    return await repo.create_artifact(model)


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
    models, _ = await repo.get_collection_artifacts(collection.id, pagination)

    assert len(models) == 2
    model_ids = [m.id for m in models]
    assert created_model1.id in model_ids
    assert created_model2.id in model_ids


@pytest.mark.asyncio
async def test_get_collection_artifacts_returns_only_active_deployments(
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

    active, _ = await deployment_repo.create_deployment(
        DeploymentCreate(
            name="active-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=created_model.id,
            status=DeploymentStatus.ACTIVE,
        )
    )
    await deployment_repo.create_deployment(
        DeploymentCreate(
            name="pending-deployment",
            orbit_id=orbit.id,
            satellite_id=satellite.id,
            artifact_id=created_model.id,
            status=DeploymentStatus.PENDING,
        )
    )

    pagination = PaginationParams(limit=100)
    models, _ = await repo.get_collection_artifacts(collection.id, pagination)

    assert len(models) == 1
    assert [d.id for d in models[0].deployments] == [active.id]


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


@pytest.mark.asyncio
async def test_get_collection_artifacts_extra_values(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id
    model.extra_values = {"accuracy": 0.95, "f1": 0.88}
    await repo.create_artifact(model)

    result = await repo.get_collection_artifacts_extra_values(collection.id)

    assert "accuracy" in result
    assert "f1" in result
    assert result == sorted(result)


@pytest.mark.asyncio
async def test_get_collection_artifacts_extra_values_empty(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    result = await repo.get_collection_artifacts_extra_values(collection.id)

    assert result == []


@pytest.mark.asyncio
async def test_get_collection_artifacts_tags(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model1 = test_artifact.model_copy()
    model1.collection_id = collection.id
    model1.unique_identifier = "uid1"
    model1.tags = ["v1", "prod"]

    model2 = test_artifact.model_copy()
    model2.collection_id = collection.id
    model2.unique_identifier = "uid2"
    model2.tags = ["v2", "prod"]

    await repo.create_artifact(model1)
    await repo.create_artifact(model2)

    result = await repo.get_collection_artifacts_tags(collection.id)

    assert set(result) == {"v1", "v2", "prod"}


@pytest.mark.asyncio
async def test_get_artifact_details(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id
    created = await repo.create_artifact(model)

    details = await repo.get_artifact_details(created.id)

    assert details is not None
    assert details.id == created.id
    assert details.collection_id == collection.id
    assert details.collection is not None
    assert details.deployments is not None


@pytest.mark.asyncio
async def test_get_artifact_details_not_found(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    engine = data.engine
    repo = ArtifactRepository(engine)

    result = await repo.get_artifact_details(uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_orbit_artifacts_filters_by_type(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = await _make_artifact(
        repo,
        test_artifact,
        collection.id,
        name="a-model",
        artifact_type=ArtifactType.MODEL,
    )
    await _make_artifact(
        repo,
        test_artifact,
        collection.id,
        name="a-dataset",
        artifact_type=ArtifactType.DATASET,
    )

    items, _ = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=100),
        data.orbit.id,
    )

    assert [a.id for a in items] == [model.id]
    assert all(a.type == ArtifactType.MODEL for a in items)


@pytest.mark.asyncio
async def test_get_orbit_artifacts_filters_by_collection_ids(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, orbit, collection = data.engine, data.orbit, data.collection
    repo = ArtifactRepository(engine)
    collection_repo = CollectionRepository(engine)

    other_collection = await collection_repo.create_collection(
        CollectionCreate(
            orbit_id=orbit.id,
            description="other",
            name="other",
            type=CollectionType.MODEL,
            tags=[],
        )
    )

    in_scope = await _make_artifact(repo, test_artifact, collection.id, name="in-scope")
    await _make_artifact(repo, test_artifact, other_collection.id, name="out-of-scope")

    items, _ = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=100),
        orbit.id,
        collection_ids=[collection.id],
    )

    assert [a.id for a in items] == [in_scope.id]


@pytest.mark.asyncio
async def test_get_orbit_artifacts_search_by_name_partial_and_case_insensitive(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    resnet = await _make_artifact(repo, test_artifact, collection.id, name="ResNet50")
    await _make_artifact(repo, test_artifact, collection.id, name="BERT")

    items, _ = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=100),
        data.orbit.id,
        collection_ids=[collection.id],
        search="resnet",
    )

    assert [a.id for a in items] == [resnet.id]


@pytest.mark.asyncio
async def test_get_orbit_artifacts_search_no_match(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    await _make_artifact(repo, test_artifact, collection.id, name="ResNet50")

    items, cursor = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=100),
        data.orbit.id,
        collection_ids=[collection.id],
        search="nonexistent",
    )

    assert items == []
    assert cursor is None


@pytest.mark.asyncio
async def test_get_orbit_artifacts_combined_filters(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    target = await _make_artifact(
        repo,
        test_artifact,
        collection.id,
        name="prod-model",
        artifact_type=ArtifactType.MODEL,
    )
    # Same name but wrong type -> excluded by type filter.
    await _make_artifact(
        repo,
        test_artifact,
        collection.id,
        name="prod-model",
        artifact_type=ArtifactType.DATASET,
    )
    # Matches type but not the search term.
    await _make_artifact(
        repo,
        test_artifact,
        collection.id,
        name="staging-model",
        artifact_type=ArtifactType.MODEL,
    )

    items, _ = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=100),
        data.orbit.id,
        collection_ids=[collection.id],
        search="prod",
    )

    assert [a.id for a in items] == [target.id]


@pytest.mark.asyncio
async def test_get_orbit_artifacts_empty(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    items, cursor = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=100),
        data.orbit.id,
    )

    assert items == []
    assert cursor is None


@pytest.mark.asyncio
async def test_get_orbit_artifacts_pagination(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    for i in range(3):
        await _make_artifact(repo, test_artifact, collection.id, name=f"model-{i}")

    first_page, cursor = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=2),
        data.orbit.id,
    )

    assert len(first_page) == 2
    assert cursor is not None

    second_page, next_cursor = await repo.get_orbit_artifacts(
        ArtifactType.MODEL,
        PaginationParams(limit=2, cursor=cursor),
        data.orbit.id,
    )

    assert len(second_page) == 1
    assert next_cursor is None

    all_ids = {a.id for a in first_page} | {a.id for a in second_page}
    assert len(all_ids) == 3
