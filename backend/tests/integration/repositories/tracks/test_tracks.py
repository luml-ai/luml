import uuid

from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.artifacts import ArtifactCreate, ArtifactType
from luml.schemas.general import PaginationParams
from luml.schemas.tracks import Track, TrackCreate, TrackEntryCreate, TrackUpdate
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData, OrbitFixtureData


class TestTrackRepository:
    async def test_create_track_returns_track_with_initial_counters(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="churn-model",
                artifact_type=ArtifactType.MODEL,
            )
        )

        assert track.id
        assert track.orbit_id == seeded_orbit.orbit.id
        assert track.name == "churn-model"
        assert track.artifact_type == "model"
        assert track.next_version == 1
        assert track.total_entries == 0

    async def test_get_track_returns_created_track(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        created = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="my-track",
                artifact_type=ArtifactType.MODEL,
                tags=["prod", "ml"],
            )
        )
        fetched = await repository.get_track(created.id)

        assert fetched is not None
        assert isinstance(fetched, Track)
        assert fetched.id == created.id
        assert fetched.name == "my-track"
        assert fetched.tags == ["prod", "ml"]

    async def test_get_orbit_tracks_returns_all_orbit_tracks(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        for i in range(3):
            await repository.create_track(
                TrackCreate(
                    orbit_id=seeded_orbit.orbit.id,
                    name=f"track-{i}",
                    artifact_type=ArtifactType.MODEL,
                )
            )

        pagination = PaginationParams(limit=100)
        tracks, cursor = await repository.get_orbit_tracks(
            seeded_orbit.orbit.id, pagination
        )

        assert len(tracks) == 3

    async def test_get_orbit_tracks_returns_tracks_with_any_tag_when_filtered_by_tags(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        tracks_data = [
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-1",
                artifact_type=ArtifactType.MODEL,
                tags=["production", "ml"],
            ),
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-2",
                artifact_type=ArtifactType.MODEL,
                tags=["staging"],
            ),
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-3",
                artifact_type=ArtifactType.MODEL,
            ),
        ]
        for track_data in tracks_data:
            await repository.create_track(track_data)

        pagination = PaginationParams(limit=100)

        filtered, _ = await repository.get_orbit_tracks(
            seeded_orbit.orbit.id, pagination, tags=["production"]
        )
        assert [t.name for t in filtered] == ["track-1"]

        filtered, _ = await repository.get_orbit_tracks(
            seeded_orbit.orbit.id, pagination, tags=["production", "staging"]
        )
        names = [t.name for t in filtered]
        assert len(filtered) == 2
        assert "track-1" in names
        assert "track-2" in names

        filtered, _ = await repository.get_orbit_tracks(
            seeded_orbit.orbit.id, pagination, tags=["nonexistent"]
        )
        assert filtered == []

    async def test_get_orbit_tracks_tags_returns_sorted_distinct_tags(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        tracks_data = [
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-1",
                artifact_type=ArtifactType.MODEL,
                tags=["production", "ml"],
            ),
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-2",
                artifact_type=ArtifactType.MODEL,
                tags=["staging", "production"],
            ),
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-3",
                artifact_type=ArtifactType.MODEL,
            ),
        ]
        for track_data in tracks_data:
            await repository.create_track(track_data)

        tags = await repository.get_orbit_tracks_tags(seeded_orbit.orbit.id)

        assert tags == ["ml", "production", "staging"]

    async def test_update_track_returns_renamed_track(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="original",
                artifact_type=ArtifactType.MODEL,
            )
        )

        updated = await repository.update_track(
            track.id, TrackUpdate(name="updated-name")
        )

        assert updated is not None
        assert updated.name == "updated-name"
        assert updated.artifact_type == "model"

    async def test_delete_track_removes_track(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="to-delete",
                artifact_type=ArtifactType.MODEL,
            )
        )

        fetched = await repository.get_track(track.id)
        assert fetched is not None

        await repository.delete_track(track.id)

        fetched_after = await repository.get_track(track.id)
        assert fetched_after is None

    async def test_create_track_creates_stages_when_stage_names_given(
        self,
        repository: TrackRepository,
        stage_repository: TrackStageRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="track-with-stages",
                artifact_type=ArtifactType.MODEL,
            ),
            stage_names=["Staging", "Production"],
        )

        stages = await stage_repository.list_stages(track.id)
        assert {s.name for s in stages} == {"Staging", "Production"}

    async def test_get_orbit_tracks_filters_by_search_and_by_type(
        self, repository: TrackRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="churn-model",
                artifact_type=ArtifactType.MODEL,
            )
        )
        await repository.create_track(
            TrackCreate(
                orbit_id=seeded_orbit.orbit.id,
                name="sales-dataset",
                artifact_type=ArtifactType.DATASET,
            )
        )

        by_search, _ = await repository.get_orbit_tracks(
            seeded_orbit.orbit.id, PaginationParams(limit=100), search="churn"
        )
        assert [t.name for t in by_search] == ["churn-model"]

        by_type, _ = await repository.get_orbit_tracks(
            seeded_orbit.orbit.id,
            PaginationParams(limit=100),
            types=[ArtifactType.DATASET.value],
        )
        assert [t.name for t in by_type] == ["sales-dataset"]

    async def test_update_track_returns_none_when_track_missing(
        self, repository: TrackRepository
    ) -> None:
        result = await repository.update_track(uuid.uuid4(), TrackUpdate(name="x"))
        assert result is None

    async def test_get_tracks_for_artifact_returns_tracks_with_entries_for_artifact(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )

        track_a = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="track-a",
                artifact_type=ArtifactType.MODEL,
            )
        )
        track_b = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="track-b",
                artifact_type=ArtifactType.MODEL,
            )
        )
        await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="track-c",
                artifact_type=ArtifactType.MODEL,
            )
        )

        for track in (track_a, track_b):
            await entry_repository.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=artifact.id,
                    added_by=seeded_collection.user.email,
                )
            )

        tracks = await repository.get_tracks_for_artifact(artifact.id)
        assert {t.id for t in tracks} == {track_a.id, track_b.id}

    async def test_get_tracks_for_artifact_returns_empty_list_when_artifact_unknown(
        self, repository: TrackRepository
    ) -> None:
        assert await repository.get_tracks_for_artifact(uuid.uuid4()) == []
