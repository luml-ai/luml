import uuid

from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.artifacts import ArtifactCreate, ArtifactType
from luml.schemas.tracks import (
    StageCreate,
    StageUpdate,
    TrackCreate,
    TrackEntryCreate,
    TrackEntryUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData, OrbitFixtureData


class TestTrackStageRepository:
    async def test_list_stages_returns_created_stages(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="stage-track",
                artifact_type=ArtifactType.MODEL,
            )
        )

        stage1 = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )
        stage2 = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
        )

        stages = await stage_repository.list_stages(track.id)
        assert len(stages) == 2
        names = {s.name for s in stages}
        assert names == {"Staging", "Production"}
        assert stage1.track_id == track.id
        assert stage2.track_id == track.id

    async def test_update_stage_returns_renamed_stage(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="stage-update-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Old")
        )

        updated = await stage_repository.update_stage(stage.id, StageUpdate(name="New"))
        assert updated is not None
        assert updated.name == "New"

    async def test_list_stages_and_get_track_mark_only_assigned_stage_as_used(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="is-used-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        used_stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
        )
        free_stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )

        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )
        entry = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )
        await entry_repository.update_entry(
            entry.id, TrackEntryUpdate(stage_id=used_stage.id)
        )

        stages = await stage_repository.list_stages(track.id)
        by_id = {s.id: s for s in stages}
        assert by_id[used_stage.id].is_used is True
        assert by_id[free_stage.id].is_used is False

        fetched = await repository.get_track(track.id)
        assert fetched is not None
        track_by_id = {s.id: s for s in fetched.stages}
        assert track_by_id[used_stage.id].is_used is True
        assert track_by_id[free_stage.id].is_used is False

    async def test_clear_stage_from_entries_unassigns_stage(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="clear-stage-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )

        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )
        entry = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )

        await entry_repository.update_entry(
            entry.id, TrackEntryUpdate(stage_id=stage.id)
        )

        await stage_repository.clear_stage_from_entries(track.id, stage.id)

        refreshed = await entry_repository.get_entry(entry.id)
        assert refreshed is not None
        assert refreshed.stage_id is None

    async def test_is_stage_in_use_returns_true_only_after_stage_assigned(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="stage-in-use-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )

        assert await stage_repository.is_stage_in_use(stage.id) is False

        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )
        entry = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )
        await entry_repository.update_entry(
            entry.id, TrackEntryUpdate(stage_id=stage.id)
        )

        assert await stage_repository.is_stage_in_use(stage.id) is True

    async def test_get_stage_returns_stage_or_none_when_missing(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="get-stage-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )

        fetched = await stage_repository.get_stage(stage.id)
        assert fetched is not None
        assert fetched.id == stage.id

        assert await stage_repository.get_stage(uuid.uuid4()) is None

    async def test_delete_stage_removes_stage(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="delete-stage-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )

        await stage_repository.delete_stage(stage.id)
        assert await stage_repository.get_stage(stage.id) is None
