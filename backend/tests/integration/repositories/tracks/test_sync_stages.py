import uuid

import pytest
from luml.infra.exceptions import ApplicationError
from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.artifacts import ArtifactCreate, ArtifactType
from luml.schemas.tracks import (
    StageCreate,
    StageUpsertIn,
    TrackCreate,
    TrackEntryCreate,
    TrackEntryUpdate,
    TrackUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData, OrbitFixtureData


class TestTrackStageRepositorySyncStages:
    async def test_sync_stages_keeps_renames_creates_and_deletes_stages(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="sync-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        keep = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Keep")
        )
        rename = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Old")
        )
        await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="ToDelete")
        )

        await stage_repository.sync_stages(
            track.id,
            [
                StageUpsertIn(id=keep.id, name="Keep"),
                StageUpsertIn(id=rename.id, name="New"),
                StageUpsertIn(name="Brand"),
            ],
        )

        stages = await stage_repository.list_stages(track.id)
        by_id = {s.id: s.name for s in stages}
        assert by_id[keep.id] == "Keep"
        assert by_id[rename.id] == "New"
        assert {s.name for s in stages} == {"Keep", "New", "Brand"}

    async def test_sync_stages_removes_all_stages_when_list_empty(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="sync-empty",
                artifact_type=ArtifactType.MODEL,
            )
        )
        await stage_repository.create_stage(StageCreate(track_id=track.id, name="A"))
        await stage_repository.create_stage(StageCreate(track_id=track.id, name="B"))

        await stage_repository.sync_stages(track.id, [])

        assert await stage_repository.list_stages(track.id) == []

    async def test_sync_stages_raises_conflict_naming_used_stage_and_changes_nothing(
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
                name="sync-inuse",
                artifact_type=ArtifactType.MODEL,
            )
        )
        used = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Used")
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
            entry.id, TrackEntryUpdate(stage_id=used.id)
        )

        with pytest.raises(ApplicationError) as exc:
            await stage_repository.sync_stages(track.id, [StageUpsertIn(name="New")])
        assert exc.value.status_code == 409
        assert str(used.id) in exc.value.message
        assert "Used" in exc.value.message

        stages = await stage_repository.list_stages(track.id)
        assert {s.name for s in stages} == {"Used"}

    async def test_sync_stages_raises_unprocessable_when_stage_id_unknown(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="sync-foreign",
                artifact_type=ArtifactType.MODEL,
            )
        )

        with pytest.raises(ApplicationError) as exc:
            await stage_repository.sync_stages(
                track.id, [StageUpsertIn(id=uuid.uuid4(), name="Ghost")]
            )
        assert exc.value.status_code == 422

    async def test_sync_stages_raises_conflict_when_names_duplicate(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="sync-dup",
                artifact_type=ArtifactType.MODEL,
            )
        )

        with pytest.raises(ApplicationError) as exc:
            await stage_repository.sync_stages(
                track.id, [StageUpsertIn(name="Dup"), StageUpsertIn(name="Dup")]
            )
        assert exc.value.status_code == 409

    async def test_update_track_rolls_back_field_update_when_stage_sync_conflicts(
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
                name="atomic-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        used = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Used")
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
            entry.id, TrackEntryUpdate(stage_id=used.id)
        )

        with pytest.raises(ApplicationError) as exc:
            await repository.update_track(
                track.id,
                TrackUpdate(name="renamed"),
                stages=[StageUpsertIn(name="Brand")],
            )
        assert exc.value.status_code == 409

        after = await repository.get_track(track.id)
        assert after is not None
        assert after.name == "atomic-track"
        stages = await stage_repository.list_stages(track.id)
        assert {s.name for s in stages} == {"Used"}

    async def test_update_track_returns_fields_and_synced_stages_committed_together(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="combo-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        old = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Old")
        )

        updated = await repository.update_track(
            track.id,
            TrackUpdate(name="combo-renamed"),
            stages=[StageUpsertIn(id=old.id, name="New"), StageUpsertIn(name="Fresh")],
        )

        assert updated is not None
        assert updated.name == "combo-renamed"
        assert {s.name for s in updated.stages} == {"New", "Fresh"}
        stages = await stage_repository.list_stages(track.id)
        assert {s.name for s in stages} == {"New", "Fresh"}

    async def test_update_track_raises_conflict_and_keeps_stages_when_snapshot_is_stale(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="stale-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        review = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Review")
        )
        await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Added elsewhere")
        )

        with pytest.raises(ApplicationError) as exc:
            await repository.update_track(
                track.id,
                TrackUpdate(name="renamed"),
                stages=[
                    StageUpsertIn(id=review.id, name="Review"),
                    StageUpsertIn(name="Canary"),
                ],
                expected_stage_ids=[review.id],
            )
        assert exc.value.status_code == 409

        after = await repository.get_track(track.id)
        assert after is not None
        assert after.name == "stale-track"
        stages = await stage_repository.list_stages(track.id)
        assert {s.name for s in stages} == {"Review", "Added elsewhere"}

    async def test_update_track_syncs_stages_when_expected_stages_match(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="fresh-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        review = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Review")
        )
        staging = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Staging")
        )

        updated = await repository.update_track(
            track.id,
            TrackUpdate(),
            stages=[
                StageUpsertIn(id=review.id, name="Review"),
                StageUpsertIn(name="Canary"),
            ],
            expected_stage_ids=[staging.id, review.id],
        )

        assert updated is not None
        assert {s.name for s in updated.stages} == {"Review", "Canary"}
