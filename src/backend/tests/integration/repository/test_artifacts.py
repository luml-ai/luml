import uuid

import pytest
from luml.infra.exceptions import DatabaseConstraintError, InvalidSortingError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.tracks import TrackEntryRepository, TrackRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
)
from luml.schemas.collections import CollectionCreate, CollectionType
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.general import PaginationParams, SortOrder
from luml.schemas.orbit import OrbitCreateIn
from luml.schemas.satellite import SatelliteCreate
from luml.schemas.tracks import TrackCreate, TrackEntryCreate
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import CollectionFixtureData


async def _make_artifact(
    repo: ArtifactRepository,
    template: ArtifactCreate,
    collection_id: uuid.UUID,
    *,
    name: str,
    artifact_type: ArtifactType = ArtifactType.MODEL,
    extra_values: dict[str, object] | None = None,
) -> Artifact:
    model = template.model_copy()
    model.collection_id = collection_id
    model.name = name
    model.type = artifact_type
    model.unique_identifier = str(uuid.uuid4())
    if extra_values is not None:
        model.extra_values = extra_values
    return await repo.create_artifact(model)


async def _make_collection(
    engine: AsyncEngine, orbit_id: uuid.UUID, name: str
) -> uuid.UUID:
    collection = await CollectionRepository(engine).create_collection(
        CollectionCreate(
            orbit_id=orbit_id,
            description=name,
            name=name,
            type=CollectionType.MODEL,
            tags=[],
        )
    )
    return collection.id


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
    models, _ = await repo.get_collection_artifacts(
        data.orbit.id, pagination, collection_ids=[collection.id]
    )

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
    models, _ = await repo.get_collection_artifacts(
        orbit.id, pagination, collection_ids=[collection.id]
    )

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
async def test_get_collection_artifacts_sort_by_metric(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    low = test_artifact.model_copy()
    low.collection_id = collection.id
    low.unique_identifier = "low"
    low.extra_values = {"accuracy": 0.1}

    high = test_artifact.model_copy()
    high.collection_id = collection.id
    high.unique_identifier = "high"
    high.extra_values = {"accuracy": 0.9}

    await repo.create_artifact(low)
    await repo.create_artifact(high)

    # Sort by the metric key, ASC, page size 1 -> lowest first + a cursor.
    first, cursor = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=1, sort_by="accuracy", order=SortOrder.ASC),
        collection_ids=[collection.id],
    )
    assert len(first) == 1
    assert first[0].extra_values["accuracy"] == 0.1
    assert cursor is not None

    second, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(
            limit=1, sort_by="accuracy", order=SortOrder.ASC, cursor=cursor
        ),
        collection_ids=[collection.id],
    )
    assert second[0].extra_values["accuracy"] == 0.9


@pytest.mark.asyncio
async def test_get_collection_artifacts_sort_extra_values_key_raises(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)
    with pytest.raises(InvalidSortingError):
        await repo.get_collection_artifacts(
            data.orbit.id,
            PaginationParams(limit=10, sort_by="extra_values"),
            collection_ids=[data.collection.id],
        )


@pytest.mark.asyncio
async def test_get_collection_artifacts_invalid_metric_raises(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    model = test_artifact.model_copy()
    model.collection_id = data.collection.id
    model.extra_values = {"accuracy": 0.5}
    await repo.create_artifact(model)

    with pytest.raises(InvalidSortingError, match="Invalid sorting column"):
        await repo.get_collection_artifacts(
            data.orbit.id,
            PaginationParams(limit=10, sort_by="nonexistent_metric"),
            collection_ids=[data.collection.id],
        )


@pytest.mark.asyncio
async def test_get_collection_artifacts_filtered_by_type(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    engine, collection = data.engine, data.collection
    repo = ArtifactRepository(engine)

    model = test_artifact.model_copy()
    model.collection_id = collection.id
    model.unique_identifier = "a-model"
    model.type = ArtifactType.MODEL

    dataset = test_artifact.model_copy()
    dataset.collection_id = collection.id
    dataset.unique_identifier = "a-dataset"
    dataset.type = ArtifactType.DATASET

    await repo.create_artifact(model)
    await repo.create_artifact(dataset)

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=100),
        collection_ids=[collection.id],
        artifact_types=[ArtifactType.MODEL],
    )
    assert all(a.type == ArtifactType.MODEL for a in items)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_get_collection_artifacts_search_partial_case_insensitive(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    resnet = await _make_artifact(
        repo, test_artifact, data.collection.id, name="ResNet50"
    )
    await _make_artifact(repo, test_artifact, data.collection.id, name="BERT")

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100), search="resnet"
    )

    assert [a.id for a in items] == [resnet.id]


@pytest.mark.asyncio
async def test_get_collection_artifacts_search_no_match(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    await _make_artifact(repo, test_artifact, data.collection.id, name="ResNet50")

    items, cursor = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100), search="nonexistent"
    )

    assert items == []
    assert cursor is None


@pytest.mark.asyncio
async def test_get_collection_artifacts_pagination_by_created_at(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    for i in range(3):
        await _make_artifact(repo, test_artifact, data.collection.id, name=f"model-{i}")

    first_page, cursor = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=2)
    )
    assert len(first_page) == 2
    assert cursor is not None

    second_page, next_cursor = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=2, cursor=cursor)
    )
    assert len(second_page) == 1
    assert next_cursor is None

    all_ids = {a.id for a in first_page} | {a.id for a in second_page}
    assert len(all_ids) == 3


@pytest.mark.asyncio
async def test_get_collection_artifacts_excludes_other_orbit(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    in_scope = await _make_artifact(
        repo, test_artifact, data.collection.id, name="in-scope"
    )

    other_orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="other orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert other_orbit is not None
    other_collection_id = await _make_collection(
        data.engine, other_orbit.id, "other-collection"
    )
    await _make_artifact(repo, test_artifact, other_collection_id, name="out-of-scope")

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100)
    )

    assert [a.id for a in items] == [in_scope.id]


@pytest.mark.asyncio
async def test_get_collection_artifacts_whole_orbit_without_collection_ids(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    second_collection_id = await _make_collection(
        data.engine, data.orbit.id, "second-collection"
    )

    a1 = await _make_artifact(repo, test_artifact, data.collection.id, name="a1")
    a2 = await _make_artifact(repo, test_artifact, second_collection_id, name="a2")

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100)
    )

    assert {a.id for a in items} == {a1.id, a2.id}


@pytest.mark.asyncio
async def test_get_collection_artifacts_collection_ids_subset(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    second_collection_id = await _make_collection(
        data.engine, data.orbit.id, "second-collection"
    )

    target = await _make_artifact(repo, test_artifact, data.collection.id, name="t")
    await _make_artifact(repo, test_artifact, second_collection_id, name="other")

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=100),
        collection_ids=[data.collection.id],
    )

    assert [a.id for a in items] == [target.id]


@pytest.mark.asyncio
async def test_get_collection_artifacts_multiple_collection_ids(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    second_collection_id = await _make_collection(
        data.engine, data.orbit.id, "second-collection"
    )
    third_collection_id = await _make_collection(
        data.engine, data.orbit.id, "third-collection"
    )

    a1 = await _make_artifact(repo, test_artifact, data.collection.id, name="a1")
    a2 = await _make_artifact(repo, test_artifact, second_collection_id, name="a2")
    await _make_artifact(repo, test_artifact, third_collection_id, name="a3")

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=100),
        collection_ids=[data.collection.id, second_collection_id],
    )

    assert {a.id for a in items} == {a1.id, a2.id}


@pytest.mark.asyncio
async def test_get_collection_artifacts_multiple_types(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    model = await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="m",
        artifact_type=ArtifactType.MODEL,
    )
    dataset = await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="d",
        artifact_type=ArtifactType.DATASET,
    )
    await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="e",
        artifact_type=ArtifactType.EXPERIMENT,
    )

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=100),
        artifact_types=[ArtifactType.MODEL, ArtifactType.DATASET],
    )

    assert {a.id for a in items} == {model.id, dataset.id}


@pytest.mark.asyncio
async def test_get_collection_artifacts_combined_filters(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    second_collection_id = await _make_collection(
        data.engine, data.orbit.id, "second-collection"
    )

    target = await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="prod-model",
        artifact_type=ArtifactType.MODEL,
    )
    # Right collection + name, wrong type.
    await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="prod-model",
        artifact_type=ArtifactType.DATASET,
    )
    # Right type + name, wrong collection.
    await _make_artifact(
        repo,
        test_artifact,
        second_collection_id,
        name="prod-model",
        artifact_type=ArtifactType.MODEL,
    )
    # Right type + collection, name does not match search.
    await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="staging-model",
        artifact_type=ArtifactType.MODEL,
    )

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=100),
        collection_ids=[data.collection.id],
        artifact_types=[ArtifactType.MODEL],
        search="prod",
    )

    assert [a.id for a in items] == [target.id]


@pytest.mark.asyncio
async def test_get_collection_artifacts_empty_orbit(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    items, cursor = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100)
    )

    assert items == []
    assert cursor is None


@pytest.mark.asyncio
async def test_get_collection_artifacts_metric_sort_without_collection_ids_falls_back(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    # Metric sort only applies when collection_ids is provided. Without it the
    # metric key is not validated and silently falls back to created_at order.
    data = create_collection
    repo = ArtifactRepository(data.engine)

    first = await _make_artifact(
        repo, test_artifact, data.collection.id, name="first", extra_values={"acc": 0.1}
    )
    second = await _make_artifact(
        repo,
        test_artifact,
        data.collection.id,
        name="second",
        extra_values={"acc": 0.9},
    )

    items, _ = await repo.get_collection_artifacts(
        data.orbit.id,
        PaginationParams(limit=100, sort_by="acc", order=SortOrder.DESC),
    )

    # created_at DESC -> most recently created first (no InvalidSortingError raised).
    assert [a.id for a in items] == [second.id, first.id]


async def _add_artifact_to_track(
    engine: AsyncEngine,
    orbit_id: uuid.UUID,
    artifact_id: uuid.UUID,
    added_by: uuid.UUID,
    name: str = "track",
) -> uuid.UUID:
    track = await TrackRepository(engine).create_track(
        TrackCreate(orbit_id=orbit_id, name=name, artifact_type=ArtifactType.MODEL)
    )
    await TrackEntryRepository(engine).create_entry(
        TrackEntryCreate(track_id=track.id, artifact_id=artifact_id, added_by=added_by)
    )
    return track.id


@pytest.mark.asyncio
async def test_get_collection_artifacts_excludes_tracks(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    in_track = await _make_artifact(
        repo, test_artifact, data.collection.id, name="in-track"
    )
    free = await _make_artifact(repo, test_artifact, data.collection.id, name="free")

    track_id = await _add_artifact_to_track(
        data.engine, data.orbit.id, in_track.id, data.user.id
    )

    # Without the filter both artifacts are returned.
    all_items, _ = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100)
    )
    assert {a.id for a in all_items} == {in_track.id, free.id}

    # Excluding the track drops the artifact that belongs to it.
    items, _ = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100), excluded_tracks=[track_id]
    )
    assert [a.id for a in items] == [free.id]


@pytest.mark.asyncio
async def test_get_collection_artifacts_excludes_only_listed_tracks(
    create_collection: CollectionFixtureData, test_artifact: ArtifactCreate
) -> None:
    data = create_collection
    repo = ArtifactRepository(data.engine)

    a_in_t1 = await _make_artifact(repo, test_artifact, data.collection.id, name="t1")
    a_in_t2 = await _make_artifact(repo, test_artifact, data.collection.id, name="t2")

    t1 = await _add_artifact_to_track(
        data.engine, data.orbit.id, a_in_t1.id, data.user.id, name="track-1"
    )
    await _add_artifact_to_track(
        data.engine, data.orbit.id, a_in_t2.id, data.user.id, name="track-2"
    )

    # Only t1 is excluded -> the artifact in t2 stays.
    items, _ = await repo.get_collection_artifacts(
        data.orbit.id, PaginationParams(limit=100), excluded_tracks=[t1]
    )

    assert [a.id for a in items] == [a_in_t2.id]
