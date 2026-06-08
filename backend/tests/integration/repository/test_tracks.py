import uuid

import pytest
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.artifacts import (
    NDJSON,
    Artifact,
    ArtifactCreate,
    ArtifactStatus,
    ArtifactType,
    Manifest,
)
from luml.schemas.general import PaginationParams
from luml.schemas.tracks import (
    StageCreate,
    StageUpdate,
    Track,
    TrackCreate,
    TrackEntryCreate,
    TrackEntryUpdate,
    TrackUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import CollectionFixtureData, OrbitFixtureData


def _make_manifest() -> Manifest:
    return Manifest(
        variant="pipeline",
        description="",
        producer_name="test",
        producer_version="0.1.0",
        producer_tags=["test::v1"],
        inputs=[
            NDJSON(
                name="x",
                content_type="NDJSON",
                dtype="Array[float32]",
                shape=["batch", 1],
            ),
        ],
        outputs=[
            NDJSON(
                name="y",
                content_type="NDJSON",
                dtype="Array[string]",
                shape=["batch"],
            ),
        ],
        dynamic_attributes=[],
        env_vars=[],
    )


async def _create_artifact(
    engine: AsyncEngine,
    collection_id: uuid.UUID,
    artifact_type: ArtifactType = ArtifactType.MODEL,
) -> Artifact:
    repo = ArtifactRepository(engine)
    data = ArtifactCreate(
        collection_id=collection_id,
        file_name="artifact.luml",
        name=f"artifact-{uuid.uuid4().hex[:8]}",
        extra_values={"accuracy": 0.9},
        manifest=_make_manifest(),
        file_hash=str(uuid.uuid4()),
        file_index={"model": (0, 100)},
        bucket_location="orbit/col/artifact.luml",
        size=100,
        unique_identifier=f"uid_{uuid.uuid4().hex[:8]}",
        tags=["test"],
        status=ArtifactStatus.UPLOADED,
        type=artifact_type,
        created_by_user="Test User",
    )
    return await repo.create_artifact(data)


# --- Track CRUD ---


@pytest.mark.asyncio
async def test_create_track(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)

    track_data = TrackCreate(
        orbit_id=data.orbit.id,
        name="churn-model",
        artifact_type=ArtifactType.MODEL,
    )
    track = await repo.create_track(track_data)

    assert track.id
    assert track.orbit_id == data.orbit.id
    assert track.name == "churn-model"
    assert track.artifact_type == "model"
    assert track.next_version == 1
    assert track.total_entries == 0


@pytest.mark.asyncio
async def test_get_track(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)

    track_data = TrackCreate(
        orbit_id=data.orbit.id,
        name="my-track",
        artifact_type=ArtifactType.MODEL,
        tags=["prod", "ml"],
    )
    created = await repo.create_track(track_data)
    fetched = await repo.get_track(created.id)

    assert fetched is not None
    assert isinstance(fetched, Track)
    assert fetched.id == created.id
    assert fetched.name == "my-track"
    assert fetched.tags == ["prod", "ml"]


@pytest.mark.asyncio
async def test_list_orbit_tracks(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)

    for i in range(3):
        await repo.create_track(
            TrackCreate(
                orbit_id=data.orbit.id,
                name=f"track-{i}",
                artifact_type=ArtifactType.MODEL,
            )
        )

    pagination = PaginationParams(limit=100)
    tracks, cursor = await repo.get_orbit_tracks(data.orbit.id, pagination)

    assert len(tracks) == 3


@pytest.mark.asyncio
async def test_update_track(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="original",
            artifact_type=ArtifactType.MODEL,
        )
    )

    updated = await repo.update_track(track.id, TrackUpdate(name="updated-name"))

    assert updated is not None
    assert updated.name == "updated-name"
    assert updated.artifact_type == "model"


@pytest.mark.asyncio
async def test_delete_track(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="to-delete",
            artifact_type=ArtifactType.MODEL,
        )
    )

    fetched = await repo.get_track(track.id)
    assert fetched is not None

    await repo.delete_track(track.id)

    fetched_after = await repo.get_track(track.id)
    assert fetched_after is None


# --- Stages ---


@pytest.mark.asyncio
async def test_create_and_list_stages(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="stage-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    stage1 = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Staging")
    )
    stage2 = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Production")
    )

    stages = await stage_repo.list_stages(track.id)
    assert len(stages) == 2
    names = {s.name for s in stages}
    assert names == {"Staging", "Production"}
    assert stage1.track_id == track.id
    assert stage2.track_id == track.id


@pytest.mark.asyncio
async def test_update_stage(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="stage-update-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    stage = await stage_repo.create_stage(StageCreate(track_id=track.id, name="Old"))

    updated = await stage_repo.update_stage(stage.id, StageUpdate(name="New"))
    assert updated is not None
    assert updated.name == "New"


# --- Entries ---


@pytest.mark.asyncio
async def test_create_entry_and_version_assignment(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="entry-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    artifact = await _create_artifact(data.engine, data.collection.id)

    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )

    assert entry.version == 1
    assert entry.stage_id is None

    updated_track = await repo.get_track(track.id)
    assert updated_track is not None
    assert updated_track.next_version == 2


@pytest.mark.asyncio
async def test_list_entries(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="list-entries-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    for _ in range(3):
        artifact = await _create_artifact(data.engine, data.collection.id)
        await entry_repo.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=data.user.id,
            )
        )

    pagination = PaginationParams(limit=100)
    entries, cursor = await entry_repo.list_entries(track.id, pagination)

    assert len(entries) == 3
    versions = {e.version for e in entries}
    assert versions == {1, 2, 3}


@pytest.mark.asyncio
async def test_update_entry_stage(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="stage-entry-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Production")
    )

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )

    updated = await entry_repo.update_entry(
        entry.id, TrackEntryUpdate(stage_id=stage.id)
    )
    assert updated is not None
    assert updated.stage_id == stage.id


@pytest.mark.asyncio
async def test_stage_is_used_flag(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="is-used-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    used_stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Production")
    )
    free_stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Staging")
    )

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )
    await entry_repo.update_entry(entry.id, TrackEntryUpdate(stage_id=used_stage.id))

    stages = await stage_repo.list_stages(track.id)
    by_id = {s.id: s for s in stages}
    assert by_id[used_stage.id].is_used is True
    assert by_id[free_stage.id].is_used is False

    # Also exposed via the embedded Track.stages.
    fetched = await repo.get_track(track.id)
    assert fetched is not None
    track_by_id = {s.id: s for s in fetched.stages}
    assert track_by_id[used_stage.id].is_used is True
    assert track_by_id[free_stage.id].is_used is False


@pytest.mark.asyncio
async def test_delete_entry(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="delete-entry-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )

    await entry_repo.delete_entry(entry.id)
    fetched = await entry_repo.get_entry(entry.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_delete_entries_bulk(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="bulk-delete-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    entries = []
    for _ in range(3):
        artifact = await _create_artifact(data.engine, data.collection.id)
        entries.append(
            await entry_repo.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=artifact.id,
                    added_by=data.user.id,
                )
            )
        )

    await entry_repo.delete_entries(track.id, [entries[0].id, entries[1].id])

    remaining, _ = await entry_repo.list_entries(track.id, PaginationParams(limit=100))
    assert {e.id for e in remaining} == {entries[2].id}


@pytest.mark.asyncio
async def test_delete_entries_scoped_to_track(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track_a = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id, name="track-a", artifact_type=ArtifactType.MODEL
        )
    )
    track_b = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id, name="track-b", artifact_type=ArtifactType.MODEL
        )
    )

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry_b = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track_b.id, artifact_id=artifact.id, added_by=data.user.id
        )
    )

    # Attempt to delete track_b's entry via track_a -> no-op (scoped by track_id).
    await entry_repo.delete_entries(track_a.id, [entry_b.id])

    assert await entry_repo.get_entry(entry_b.id) is not None


@pytest.mark.asyncio
async def test_list_entries_for_artifact(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track1 = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="track-1",
            artifact_type=ArtifactType.MODEL,
        )
    )
    track2 = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="track-2",
            artifact_type=ArtifactType.MODEL,
        )
    )

    artifact = await _create_artifact(data.engine, data.collection.id)

    await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track1.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )
    await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track2.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )

    entries = await entry_repo.list_entries_for_artifact(artifact.id)
    assert len(entries) == 2
    track_ids = {e.track_id for e in entries}
    assert track_ids == {track1.id, track2.id}


@pytest.mark.asyncio
async def test_has_entries_for_artifact(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="has-entries-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    artifact = await _create_artifact(data.engine, data.collection.id)

    assert await entry_repo.has_entries_for_artifact(artifact.id) is False

    await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )

    assert await entry_repo.has_entries_for_artifact(artifact.id) is True


@pytest.mark.asyncio
async def test_clear_stage_from_entries(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="clear-stage-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Staging")
    )

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )

    await entry_repo.update_entry(entry.id, TrackEntryUpdate(stage_id=stage.id))

    await stage_repo.clear_stage_from_entries(track.id, stage.id)

    refreshed = await entry_repo.get_entry(entry.id)
    assert refreshed is not None
    assert refreshed.stage_id is None


@pytest.mark.asyncio
async def test_version_monotonicity_after_deletion(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="monotonic-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    artifacts = []
    for _ in range(3):
        a = await _create_artifact(data.engine, data.collection.id)
        artifacts.append(a)

    entries = []
    for a in artifacts:
        e = await entry_repo.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=a.id,
                added_by=data.user.id,
            )
        )
        entries.append(e)

    assert entries[0].version == 1
    assert entries[1].version == 2
    assert entries[2].version == 3

    await entry_repo.delete_entry(entries[1].id)

    new_artifact = await _create_artifact(data.engine, data.collection.id)
    new_entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=new_artifact.id,
            added_by=data.user.id,
        )
    )

    assert new_entry.version == 4


@pytest.mark.asyncio
async def test_force_stage_reassign(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="force-reassign-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Production")
    )

    art1 = await _create_artifact(data.engine, data.collection.id)
    art2 = await _create_artifact(data.engine, data.collection.id)

    entry1 = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=art1.id,
            added_by=data.user.id,
        )
    )
    entry2 = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=art2.id,
            added_by=data.user.id,
        )
    )

    await entry_repo.update_entry(entry1.id, TrackEntryUpdate(stage_id=stage.id))

    updated_entry2 = await entry_repo.update_entry(
        entry2.id, TrackEntryUpdate(stage_id=stage.id), force=True
    )
    assert updated_entry2 is not None
    assert updated_entry2.stage_id == stage.id

    refreshed_entry1 = await entry_repo.get_entry(entry1.id)
    assert refreshed_entry1 is not None
    assert refreshed_entry1.stage_id is None


@pytest.mark.asyncio
async def test_pagination(create_collection: CollectionFixtureData) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="pagination-track",
            artifact_type=ArtifactType.MODEL,
        )
    )

    for _ in range(5):
        art = await _create_artifact(data.engine, data.collection.id)
        await entry_repo.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=art.id,
                added_by=data.user.id,
            )
        )

    pagination = PaginationParams(limit=2)
    entries_page1, cursor1 = await entry_repo.list_entries(track.id, pagination)
    assert len(entries_page1) == 2
    assert cursor1 is not None

    pagination2 = PaginationParams(limit=2, cursor=cursor1)
    entries_page2, cursor2 = await entry_repo.list_entries(track.id, pagination2)
    assert len(entries_page2) == 2
    assert cursor2 is not None

    pagination3 = PaginationParams(limit=2, cursor=cursor2)
    entries_page3, cursor3 = await entry_repo.list_entries(track.id, pagination3)
    assert len(entries_page3) == 1
    assert cursor3 is None

    all_ids = {e.id for e in entries_page1 + entries_page2 + entries_page3}
    assert len(all_ids) == 5


@pytest.mark.asyncio
async def test_is_stage_in_use(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="stage-in-use-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Staging")
    )

    assert await stage_repo.is_stage_in_use(stage.id) is False

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )
    await entry_repo.update_entry(entry.id, TrackEntryUpdate(stage_id=stage.id))

    assert await stage_repo.is_stage_in_use(stage.id) is True


@pytest.mark.asyncio
async def test_get_entry_by_stage(
    create_collection: CollectionFixtureData,
) -> None:
    data = create_collection
    repo = TrackRepository(data.engine)
    stage_repo = TrackStageRepository(data.engine)
    entry_repo = TrackEntryRepository(data.engine)

    track = await repo.create_track(
        TrackCreate(
            orbit_id=data.orbit.id,
            name="entry-by-stage-track",
            artifact_type=ArtifactType.MODEL,
        )
    )
    stage = await stage_repo.create_stage(
        StageCreate(track_id=track.id, name="Production")
    )

    result = await entry_repo.get_entry_by_stage(track.id, stage.id)
    assert result is None

    artifact = await _create_artifact(data.engine, data.collection.id)
    entry = await entry_repo.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            added_by=data.user.id,
        )
    )
    await entry_repo.update_entry(entry.id, TrackEntryUpdate(stage_id=stage.id))

    result = await entry_repo.get_entry_by_stage(track.id, stage.id)
    assert result is not None
    assert result.id == entry.id
