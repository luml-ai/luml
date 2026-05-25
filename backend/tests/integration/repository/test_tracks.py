import uuid

import pytest
from luml.models.tracks import TrackOrm
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.tracks import TrackRepository
from luml.schemas.artifacts import Artifact, ArtifactCreate, ArtifactType
from luml.schemas.tracks import (
    TrackCreate,
    TrackStageCreate,
    TrackStageUpdate,
    TrackUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import CollectionFixtureData


async def _create_track(
    repo: TrackRepository,
    orbit_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str = "my-track",
    artifact_type: ArtifactType = ArtifactType.MODEL,
) -> TrackOrm:
    data = TrackCreate(
        name=name,
        artifact_type=artifact_type,
        description="test track",
        tags=["tag1"],
    )
    return await repo.create_track(data, orbit_id, user_id)


async def _create_artifact(
    engine: AsyncEngine,
    collection_id: uuid.UUID,
    test_artifact: ArtifactCreate,
    uid: str | None = None,
) -> Artifact:
    artifact_repo = ArtifactRepository(engine)
    artifact_data = test_artifact.model_copy()
    artifact_data.collection_id = collection_id
    if uid:
        artifact_data.unique_identifier = uid
    return await artifact_repo.create_artifact(artifact_data)


# --- Track CRUD ---


@pytest.mark.asyncio
async def test_create_track(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)

    assert track.id is not None
    assert track.orbit_id == data.orbit.id
    assert track.name == "my-track"
    assert track.artifact_type == ArtifactType.MODEL
    assert track.next_version == 1
    assert track.created_by == data.user.id


@pytest.mark.asyncio
async def test_create_track_creates_default_stages(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stages = await repo.list_stages(track.id)

    stage_names = {s.name for s in stages}
    assert stage_names == {"Staging", "Pre-Production", "Production", "Archived"}


@pytest.mark.asyncio
async def test_list_tracks(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    await _create_track(repo, data.orbit.id, data.user.id, name="t1")
    await _create_track(repo, data.orbit.id, data.user.id, name="t2")

    tracks = await repo.list_tracks(data.orbit.id)
    assert len(tracks) == 2
    names = {t.name for t in tracks}
    assert names == {"t1", "t2"}


@pytest.mark.asyncio
async def test_get_track(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    fetched = await repo.get_track(track.id)

    assert fetched is not None
    assert fetched.id == track.id
    assert fetched.name == track.name


@pytest.mark.asyncio
async def test_get_track_not_found(
    create_collection: CollectionFixtureData,
) -> None:
    repo = TrackRepository(create_collection.engine)
    result = await repo.get_track(uuid.uuid7())
    assert result is None


@pytest.mark.asyncio
async def test_update_track(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    updated = await repo.update_track(
        track, TrackUpdate(name="renamed", tags=["new-tag"])
    )

    assert updated.name == "renamed"
    assert updated.tags == ["new-tag"]
    assert updated.description == "test track"


@pytest.mark.asyncio
async def test_delete_track(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    await repo.delete_track(track)

    assert await repo.get_track(track.id) is None


# --- Stage CRUD ---


@pytest.mark.asyncio
async def test_create_stage(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stage = await repo.create_stage(
        track.id, TrackStageCreate(name="Custom")
    )

    assert stage.name == "Custom"
    assert stage.track_id == track.id


@pytest.mark.asyncio
async def test_list_stages(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    await repo.create_stage(track.id, TrackStageCreate(name="Custom"))

    stages = await repo.list_stages(track.id)
    assert len(stages) == 5  # 4 default + 1 custom


@pytest.mark.asyncio
async def test_update_stage(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stage = await repo.create_stage(
        track.id, TrackStageCreate(name="Old")
    )

    updated = await repo.update_stage(stage, TrackStageUpdate(name="New"))
    assert updated.name == "New"


@pytest.mark.asyncio
async def test_delete_stage(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stage = await repo.create_stage(
        track.id, TrackStageCreate(name="Temp")
    )
    await repo.delete_stage(stage)

    fetched = await repo.get_stage(stage.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_clear_stage_from_entries(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stages = await repo.list_stages(track.id)
    prod_stage = next(s for s in stages if s.name == "Production")

    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )
    entry = await repo.add_entry(track, artifact.id, data.user.id)
    entry = await repo.update_entry_stage(entry, prod_stage.id)
    assert entry.stage_id == prod_stage.id

    await repo.clear_stage_from_entries(prod_stage.id)

    refreshed = await repo.get_entry(entry.id)
    assert refreshed is not None
    assert refreshed.stage_id is None


# --- Entry CRUD ---


@pytest.mark.asyncio
async def test_add_entry(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )

    entry = await repo.add_entry(track, artifact.id, data.user.id)

    assert entry.version == 1
    assert entry.track_id == track.id
    assert entry.artifact_id == artifact.id
    assert entry.added_by == data.user.id

    refreshed_track = await repo.get_track(track.id)
    assert refreshed_track is not None
    assert refreshed_track.next_version == 2


@pytest.mark.asyncio
async def test_add_entry_increments_version(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    a1 = await _create_artifact(
        data.engine, data.collection.id, test_artifact, uid="uid1"
    )
    a2 = await _create_artifact(
        data.engine, data.collection.id, test_artifact, uid="uid2"
    )

    e1 = await repo.add_entry(track, a1.id, data.user.id)
    refetched = await repo.get_track(track.id)
    assert refetched is not None
    e2 = await repo.add_entry(refetched, a2.id, data.user.id)

    assert e1.version == 1
    assert e2.version == 2


@pytest.mark.asyncio
async def test_list_entries(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    a1 = await _create_artifact(
        data.engine, data.collection.id, test_artifact, uid="uid1"
    )
    a2 = await _create_artifact(
        data.engine, data.collection.id, test_artifact, uid="uid2"
    )

    await repo.add_entry(track, a1.id, data.user.id)
    refetched = await repo.get_track(track.id)
    assert refetched is not None
    await repo.add_entry(refetched, a2.id, data.user.id)

    entries = await repo.list_entries(track.id)
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_list_entries_filter_by_stage(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stages = await repo.list_stages(track.id)
    prod_stage = next(s for s in stages if s.name == "Production")

    a1 = await _create_artifact(
        data.engine, data.collection.id, test_artifact, uid="uid1"
    )
    a2 = await _create_artifact(
        data.engine, data.collection.id, test_artifact, uid="uid2"
    )

    e1 = await repo.add_entry(track, a1.id, data.user.id)
    refetched = await repo.get_track(track.id)
    assert refetched is not None
    await repo.add_entry(refetched, a2.id, data.user.id)

    await repo.update_entry_stage(e1, prod_stage.id)

    prod_entries = await repo.list_entries(track.id, stage_name="Production")
    assert len(prod_entries) == 1
    assert prod_entries[0].artifact_id == a1.id


@pytest.mark.asyncio
async def test_list_entries_pagination(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)

    for i in range(5):
        a = await _create_artifact(
            data.engine, data.collection.id, test_artifact, uid=f"uid{i}"
        )
        current_track = await repo.get_track(track.id)
        assert current_track is not None
        await repo.add_entry(current_track, a.id, data.user.id)

    page1 = await repo.list_entries(track.id, page_size=3)
    assert len(page1) == 3

    from luml.schemas.general import Cursor, SortOrder

    cursor = Cursor(
        id=page1[-1].id,
        value=page1[-1].created_at,
        sort_by="created_at",
        order=SortOrder.DESC,
    )
    page2 = await repo.list_entries(track.id, cursor=cursor, page_size=3)
    assert len(page2) == 2

    all_ids = [e.id for e in page1] + [e.id for e in page2]
    assert len(set(all_ids)) == 5


@pytest.mark.asyncio
async def test_get_entry_holding_stage(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stages = await repo.list_stages(track.id)
    prod_stage = next(s for s in stages if s.name == "Production")

    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )
    entry = await repo.add_entry(track, artifact.id, data.user.id)
    await repo.update_entry_stage(entry, prod_stage.id)

    holder = await repo.get_entry_holding_stage(track.id, prod_stage.id)
    assert holder is not None
    assert holder.id == entry.id

    staging_stage = next(s for s in stages if s.name == "Staging")
    no_holder = await repo.get_entry_holding_stage(track.id, staging_stage.id)
    assert no_holder is None


@pytest.mark.asyncio
async def test_update_entry_stage(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    stages = await repo.list_stages(track.id)
    prod_stage = next(s for s in stages if s.name == "Production")

    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )
    entry = await repo.add_entry(track, artifact.id, data.user.id)

    updated = await repo.update_entry_stage(entry, prod_stage.id)
    assert updated.stage_id == prod_stage.id

    cleared = await repo.update_entry_stage(updated, None)
    assert cleared.stage_id is None


@pytest.mark.asyncio
async def test_delete_entry(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )
    entry = await repo.add_entry(track, artifact.id, data.user.id)

    await repo.delete_entry(entry)

    fetched = await repo.get_entry(entry.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_list_entries_for_artifact(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    t1 = await _create_track(
        repo, data.orbit.id, data.user.id, name="track-1"
    )
    t2 = await _create_track(
        repo, data.orbit.id, data.user.id, name="track-2"
    )

    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )

    await repo.add_entry(t1, artifact.id, data.user.id)
    t2_refetched = await repo.get_track(t2.id)
    assert t2_refetched is not None
    await repo.add_entry(t2_refetched, artifact.id, data.user.id)

    entries = await repo.list_entries_for_artifact(
        data.orbit.id, artifact.id
    )
    assert len(entries) == 2
    track_ids = {e.track_id for e in entries}
    assert len(track_ids) == 2


@pytest.mark.asyncio
async def test_has_entries_for_artifact(
    create_collection: CollectionFixtureData,
    test_artifact: ArtifactCreate,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)

    track = await _create_track(repo, data.orbit.id, data.user.id)
    artifact = await _create_artifact(
        data.engine, data.collection.id, test_artifact
    )

    assert await repo.has_entries_for_artifact(artifact.id) is False

    entry = await repo.add_entry(track, artifact.id, data.user.id)
    assert await repo.has_entries_for_artifact(artifact.id) is True

    await repo.delete_entry(entry)
    assert await repo.has_entries_for_artifact(artifact.id) is False
