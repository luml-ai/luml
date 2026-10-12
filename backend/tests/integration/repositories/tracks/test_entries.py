import uuid
from datetime import datetime
from unittest.mock import Mock

from luml.repositories.tracks import (
    TrackEntryRepository,
    TrackRepository,
    TrackStageRepository,
)
from luml.schemas.artifacts import ArtifactCreate, ArtifactType
from luml.schemas.general import PaginationParams, SortOrder
from luml.schemas.tracks import (
    StageCreate,
    TrackCreate,
    TrackEntryCreate,
    TrackEntryUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.repositories.tracks.conftest import (
    _collect_pages,
    _seed_entries,
)
from tests.support.builders import create_artifact, create_sibling_orbit
from tests.support.seeds import CollectionFixtureData


class TestTrackEntryRepository:
    async def test_create_entry_assigns_first_version_and_advances_next_version(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="entry-track",
                artifact_type=ArtifactType.MODEL,
            )
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

        assert entry.version == 1
        assert entry.stage_id is None

        updated_track = await repository.get_track(track.id)
        assert updated_track is not None
        assert updated_track.next_version == 2

    async def test_list_entries_returns_all_track_entries(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="list-entries-track",
                artifact_type=ArtifactType.MODEL,
            )
        )

        for _ in range(3):
            artifact = await create_artifact(
                engine,
                artifact_template,
                seeded_collection.collection.id,
                name=f"artifact-{uuid.uuid4().hex[:8]}",
            )
            await entry_repository.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=artifact.id,
                    added_by=seeded_collection.user.email,
                )
            )

        pagination = PaginationParams(limit=100)
        entries, cursor = await entry_repository.list_entries(track.id, pagination)

        assert len(entries) == 3
        versions = {e.version for e in entries}
        assert versions == {1, 2, 3}

    async def test_list_entries_sorts_by_artifact_name_version_and_stage(
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
                name="sort-entries-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
        )

        names = ["Charlie", "Alpha", "Bravo"]
        entries = []
        for name in names:
            artifact = await create_artifact(
                engine, artifact_template, seeded_collection.collection.id, name=name
            )
            entries.append(
                await entry_repository.create_entry(
                    TrackEntryCreate(
                        track_id=track.id,
                        artifact_id=artifact.id,
                        added_by=seeded_collection.user.email,
                    )
                )
            )

        items, _ = await entry_repository.list_entries(
            track.id,
            PaginationParams(limit=100, sort_by="artifact_name", order=SortOrder.ASC),
        )
        assert [e.artifact_name for e in items] == ["Alpha", "Bravo", "Charlie"]

        items, _ = await entry_repository.list_entries(
            track.id,
            PaginationParams(limit=100, sort_by="version", order=SortOrder.DESC),
        )
        assert [e.version for e in items] == [3, 2, 1]

        await entry_repository.update_entry(
            entries[0].id, TrackEntryUpdate(stage_id=stage.id)
        )
        items, _ = await entry_repository.list_entries(
            track.id,
            PaginationParams(limit=100, sort_by="stage", order=SortOrder.ASC),
        )
        assert items[-1].stage_name == "Production"

    async def test_list_entries_sorts_by_version_in_both_orders(
        self,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, _ = await _seed_entries(
            seeded_collection,
            [("a", None), ("b", None), ("c", None)],
            artifact_template=artifact_template,
        )

        asc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="version", order=SortOrder.ASC),
        )
        assert [e.version for e in asc] == [1, 2, 3]

        desc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="version", order=SortOrder.DESC),
        )
        assert [e.version for e in desc] == [3, 2, 1]

    async def test_list_entries_sorts_newest_first_when_sort_by_missing(
        self,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, _ = await _seed_entries(
            seeded_collection,
            [("a", None), ("b", None), ("c", None)],
            artifact_template=artifact_template,
        )

        items, _ = await entry_repository.list_entries(
            track_id, PaginationParams(limit=100)
        )
        assert [e.version for e in items] == [3, 2, 1]

    async def test_list_entries_sorts_by_artifact_name_in_both_orders(
        self,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, _ = await _seed_entries(
            seeded_collection,
            [("Charlie", None), ("Alpha", None), ("Bravo", None)],
            artifact_template=artifact_template,
        )

        asc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="artifact_name", order=SortOrder.ASC),
        )
        assert [e.artifact_name for e in asc] == ["Alpha", "Bravo", "Charlie"]

        desc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="artifact_name", order=SortOrder.DESC),
        )
        assert [e.artifact_name for e in desc] == ["Charlie", "Bravo", "Alpha"]

    async def test_list_entries_sorts_by_description_ascending(
        self,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, _ = await _seed_entries(
            seeded_collection,
            [("a", "zeta"), ("b", "alpha"), ("c", "mu")],
            artifact_template=artifact_template,
        )

        asc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="description", order=SortOrder.ASC),
        )
        assert [e.artifact_description for e in asc] == ["alpha", "mu", "zeta"]

    async def test_list_entries_sorts_stageless_entries_first_ascending_last_descending(
        self,
        stage_repository: TrackStageRepository,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, entries = await _seed_entries(
            seeded_collection,
            [("a", None), ("b", None), ("c", None)],
            artifact_template=artifact_template,
        )

        alpha = await stage_repository.create_stage(
            StageCreate(track_id=track_id, name="Alpha")
        )
        beta = await stage_repository.create_stage(
            StageCreate(track_id=track_id, name="Beta")
        )
        await entry_repository.update_entry(
            entries[0].id, TrackEntryUpdate(stage_id=beta.id)
        )
        await entry_repository.update_entry(
            entries[1].id, TrackEntryUpdate(stage_id=alpha.id)
        )

        asc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="stage", order=SortOrder.ASC),
        )
        assert [e.stage_name for e in asc] == [None, "Alpha", "Beta"]

        desc, _ = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=100, sort_by="stage", order=SortOrder.DESC),
        )
        assert [e.stage_name for e in desc] == ["Beta", "Alpha", None]

    async def test_list_entries_pages_by_version_without_gaps_or_duplicates(
        self,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, _ = await _seed_entries(
            seeded_collection,
            [(f"a{i}", None) for i in range(5)],
            artifact_template=artifact_template,
        )

        page, cursor = await entry_repository.list_entries(
            track_id,
            PaginationParams(limit=2, sort_by="version", order=SortOrder.ASC),
        )
        assert [e.version for e in page] == [1, 2]
        assert cursor is not None

        collected = await _collect_pages(
            entry_repository, track_id, "version", SortOrder.ASC, limit=2
        )
        assert [e.version for e in collected] == [1, 2, 3, 4, 5]
        assert len({e.id for e in collected}) == 5

    async def test_list_entries_pages_by_artifact_name_without_gaps_or_duplicates(
        self,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        names = ["Delta", "Alpha", "Echo", "Bravo", "Charlie"]
        track_id, _ = await _seed_entries(
            seeded_collection,
            [(n, None) for n in names],
            artifact_template=artifact_template,
        )

        collected = await _collect_pages(
            entry_repository, track_id, "artifact_name", SortOrder.ASC, limit=2
        )
        assert [e.artifact_name for e in collected] == sorted(names)
        assert len({e.id for e in collected}) == len(names)

    def test_entry_cursor_value_maps_sort_fields_and_falls_back_to_created_at(
        self,
    ) -> None:
        artifact = Mock()
        artifact.name = "model-x"
        artifact.description = "the desc"
        stage = Mock()
        stage.name = "Production"
        now = datetime.now()
        entry = Mock(artifact=artifact, stage=stage, version=7, created_at=now)

        cursor_value = TrackEntryRepository._entry_cursor_value
        assert cursor_value(entry, "artifact_name") == "model-x"
        assert cursor_value(entry, "description") == "the desc"
        assert cursor_value(entry, "stage") == "Production"
        assert cursor_value(entry, "version") == 7
        assert cursor_value(entry, "created_at") == now
        assert cursor_value(entry, None) == now

        entry_no_rel = Mock(artifact=None, stage=None, version=1, created_at=now)
        assert cursor_value(entry_no_rel, "stage") is None
        assert cursor_value(entry_no_rel, "artifact_name") is None

    async def test_update_entry_assigns_stage(
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
                name="stage-entry-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
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

        updated = await entry_repository.update_entry(
            entry.id, TrackEntryUpdate(stage_id=stage.id)
        )
        assert updated is not None
        assert updated.stage_id == stage.id

    async def test_delete_entry_removes_entry(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="delete-entry-track",
                artifact_type=ArtifactType.MODEL,
            )
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

        await entry_repository.delete_entry(entry.id)
        fetched = await entry_repository.get_entry(entry.id)
        assert fetched is None

    async def test_delete_entries_removes_only_listed_entries(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="bulk-delete-track",
                artifact_type=ArtifactType.MODEL,
            )
        )

        entries = []
        for _ in range(3):
            artifact = await create_artifact(
                engine,
                artifact_template,
                seeded_collection.collection.id,
                name=f"artifact-{uuid.uuid4().hex[:8]}",
            )
            entries.append(
                await entry_repository.create_entry(
                    TrackEntryCreate(
                        track_id=track.id,
                        artifact_id=artifact.id,
                        added_by=seeded_collection.user.email,
                    )
                )
            )

        await entry_repository.delete_entries(track.id, [entries[0].id, entries[1].id])

        remaining, _ = await entry_repository.list_entries(
            track.id, PaginationParams(limit=100)
        )
        assert {e.id for e in remaining} == {entries[2].id}

    async def test_delete_entries_keeps_entry_when_it_belongs_to_another_track(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
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

        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )
        entry_b = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track_b.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )

        await entry_repository.delete_entries(track_a.id, [entry_b.id])

        assert await entry_repository.get_entry(entry_b.id) is not None

    async def test_list_entries_for_artifact_returns_entries_across_tracks(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track1 = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="track-1",
                artifact_type=ArtifactType.MODEL,
            )
        )
        track2 = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="track-2",
                artifact_type=ArtifactType.MODEL,
            )
        )

        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )

        await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track1.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )
        await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track2.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )

        entries = await entry_repository.list_entries_for_artifact(
            artifact.id, orbit_id=seeded_collection.orbit.id
        )
        assert len(entries) == 2
        track_ids = {e.track_id for e in entries}
        assert track_ids == {track1.id, track2.id}

    async def test_has_entries_for_artifact_returns_true_only_after_entry_created(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="has-entries-track",
                artifact_type=ArtifactType.MODEL,
            )
        )

        artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )

        assert await entry_repository.has_entries_for_artifact(artifact.id) is False

        await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=artifact.id,
                added_by=seeded_collection.user.email,
            )
        )

        assert await entry_repository.has_entries_for_artifact(artifact.id) is True

    async def test_create_entry_does_not_reuse_version_after_deletion(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="monotonic-track",
                artifact_type=ArtifactType.MODEL,
            )
        )

        artifacts = []
        for _ in range(3):
            a = await create_artifact(
                engine,
                artifact_template,
                seeded_collection.collection.id,
                name=f"artifact-{uuid.uuid4().hex[:8]}",
            )
            artifacts.append(a)

        entries = []
        for a in artifacts:
            e = await entry_repository.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=a.id,
                    added_by=seeded_collection.user.email,
                )
            )
            entries.append(e)

        assert entries[0].version == 1
        assert entries[1].version == 2
        assert entries[2].version == 3

        await entry_repository.delete_entry(entries[1].id)

        replacement_artifact = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )
        new_entry = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=replacement_artifact.id,
                added_by=seeded_collection.user.email,
            )
        )

        assert new_entry.version == 4

    async def test_update_entry_moves_stage_from_other_entry_when_forced(
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
                name="force-reassign-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
        )

        art1 = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )
        art2 = await create_artifact(
            engine,
            artifact_template,
            seeded_collection.collection.id,
            name=f"artifact-{uuid.uuid4().hex[:8]}",
        )

        entry1 = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=art1.id,
                added_by=seeded_collection.user.email,
            )
        )
        entry2 = await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id,
                artifact_id=art2.id,
                added_by=seeded_collection.user.email,
            )
        )

        await entry_repository.update_entry(
            entry1.id, TrackEntryUpdate(stage_id=stage.id)
        )

        updated_entry2 = await entry_repository.update_entry(
            entry2.id, TrackEntryUpdate(stage_id=stage.id), force=True
        )
        assert updated_entry2 is not None
        assert updated_entry2.stage_id == stage.id

        refreshed_entry1 = await entry_repository.get_entry(entry1.id)
        assert refreshed_entry1 is not None
        assert refreshed_entry1.stage_id is None

    async def test_list_entries_returns_cursor_pages_until_exhausted(
        self,
        repository: TrackRepository,
        entry_repository: TrackEntryRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track = await repository.create_track(
            TrackCreate(
                orbit_id=seeded_collection.orbit.id,
                name="pagination-track",
                artifact_type=ArtifactType.MODEL,
            )
        )

        for _ in range(5):
            art = await create_artifact(
                engine,
                artifact_template,
                seeded_collection.collection.id,
                name=f"artifact-{uuid.uuid4().hex[:8]}",
            )
            await entry_repository.create_entry(
                TrackEntryCreate(
                    track_id=track.id,
                    artifact_id=art.id,
                    added_by=seeded_collection.user.email,
                )
            )

        pagination = PaginationParams(limit=2)
        entries_page1, cursor1 = await entry_repository.list_entries(
            track.id, pagination
        )
        assert len(entries_page1) == 2
        assert cursor1 is not None

        pagination2 = PaginationParams(limit=2, cursor=cursor1)
        entries_page2, cursor2 = await entry_repository.list_entries(
            track.id, pagination2
        )
        assert len(entries_page2) == 2
        assert cursor2 is not None

        pagination3 = PaginationParams(limit=2, cursor=cursor2)
        entries_page3, cursor3 = await entry_repository.list_entries(
            track.id, pagination3
        )
        assert len(entries_page3) == 1
        assert cursor3 is None

        all_ids = {e.id for e in entries_page1 + entries_page2 + entries_page3}
        assert len(all_ids) == 5

    async def test_get_entry_by_stage_returns_assigned_entry_or_none(
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
                name="entry-by-stage-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
        )

        result = await entry_repository.get_entry_by_stage(track.id, stage.id)
        assert result is None

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

        result = await entry_repository.get_entry_by_stage(track.id, stage.id)
        assert result is not None
        assert result.id == entry.id

    async def test_get_entry_returns_none_when_entry_missing(
        self, entry_repository: TrackEntryRepository
    ) -> None:
        assert await entry_repository.get_entry(uuid.uuid4()) is None

    async def test_list_entries_returns_stage_entries_when_filtered_by_stage(
        self,
        stage_repository: TrackStageRepository,
        entry_repository: TrackEntryRepository,
        seeded_collection: CollectionFixtureData,
        artifact_template: ArtifactCreate,
    ) -> None:
        track_id, entries = await _seed_entries(
            seeded_collection,
            [("a", None), ("b", None), ("c", None)],
            artifact_template=artifact_template,
        )

        stage = await stage_repository.create_stage(
            StageCreate(track_id=track_id, name="Production")
        )
        await entry_repository.update_entry(
            entries[0].id, TrackEntryUpdate(stage_id=stage.id)
        )

        items, _ = await entry_repository.list_entries(
            track_id, PaginationParams(limit=100), stage_id=stage.id
        )
        assert [e.id for e in items] == [entries[0].id]

    async def test_update_entry_returns_none_when_entry_missing(
        self, entry_repository: TrackEntryRepository
    ) -> None:
        result = await entry_repository.update_entry(
            uuid.uuid4(), TrackEntryUpdate(stage_id=None)
        )
        assert result is None

    async def test_create_entry_assigns_given_stage(
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
                name="entry-stage-track",
                artifact_type=ArtifactType.MODEL,
            )
        )
        stage = await stage_repository.create_stage(
            StageCreate(track_id=track.id, name="Production")
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
                stage_id=stage.id,
            )
        )

        assert entry.stage_id == stage.id
        assert entry.stage_name == "Production"


async def test_artifact_entry_listing_excludes_tracks_outside_orbit(
    repository: TrackRepository,
    entry_repository: TrackEntryRepository,
    seeded_collection: CollectionFixtureData,
    artifact_template: ArtifactCreate,
) -> None:
    data = seeded_collection
    sibling = await create_sibling_orbit(
        data.engine, data.organization.id, data.bucket_secret.id
    )
    artifact = await create_artifact(
        data.engine, artifact_template, data.collection.id, name="artifact"
    )
    own_track = await repository.create_track(
        TrackCreate(
            orbit_id=data.orbit.id, name="own", artifact_type=ArtifactType.MODEL
        )
    )
    foreign_track = await repository.create_track(
        TrackCreate(
            orbit_id=sibling.id, name="foreign", artifact_type=ArtifactType.MODEL
        )
    )
    for track in (own_track, foreign_track):
        await entry_repository.create_entry(
            TrackEntryCreate(
                track_id=track.id, artifact_id=artifact.id, added_by=data.user.email
            )
        )
    entries = await entry_repository.list_entries_for_artifact(
        artifact.id, orbit_id=data.orbit.id
    )
    assert [entry.track_id for entry in entries] == [own_track.id]
