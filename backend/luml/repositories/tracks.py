from uuid import UUID

from sqlalchemy import String, cast, or_, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from luml.models.tracks import TrackArtifactOrm, TrackOrm, TrackStageOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.general import Cursor, PaginationParams
from luml.schemas.tracks import (
    Track,
    TrackCreate,
    TrackEntry,
    TrackEntryCreate,
    TrackEntryUpdate,
    TrackStage,
    TrackStageCreate,
    TrackStageUpdate,
    TrackUpdate,
)


class TrackRepository(RepositoryBase, CrudMixin):
    # --- Tracks ---

    async def create_track(self, track: TrackCreate) -> Track:
        async with self._get_session() as session:
            db_track = await self.create_model(session, TrackOrm, track)
            return Track.model_validate(db_track)

    async def get_track(self, track_id: UUID) -> Track | None:
        async with self._get_session() as session:
            db_track = await self.get_model(session, TrackOrm, track_id)
            return Track.model_validate(db_track) if db_track else None

    async def get_orbit_tracks(
        self,
        orbit_id: UUID,
        pagination: PaginationParams,
        search: str | None = None,
        types: list[str] | None = None,
    ) -> tuple[list[Track], Cursor | None]:
        async with self._get_session() as session:
            conditions = [TrackOrm.orbit_id == orbit_id]

            if search:
                search_pattern = f"%{search}%"
                conditions.append(
                    or_(
                        TrackOrm.name.ilike(search_pattern),
                        cast(TrackOrm.tags, String).ilike(search_pattern),
                    )
                )

            if types:
                conditions.append(
                    or_(*[TrackOrm.artifact_type == t for t in types])
                )

            result = await self.get_models_with_pagination(
                session,
                TrackOrm,
                *conditions,
                pagination=pagination,
            )
            db_tracks = result.items
            cursor = (
                None
                if not result.has_more
                else self._get_cursor_from_record(db_tracks[-1], pagination)
            )
            return [Track.model_validate(t) for t in db_tracks], cursor

    async def update_track(
        self, track_id: UUID, data: TrackUpdate
    ) -> Track | None:
        data.id = track_id
        async with self._get_session() as session:
            db_track = await self.update_model(
                session=session, orm_class=TrackOrm, data=data
            )
            return Track.model_validate(db_track) if db_track else None

    async def delete_track(self, track_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, TrackOrm, track_id)

    # --- Stages ---

    async def create_stage(self, stage: TrackStageCreate) -> TrackStage:
        async with self._get_session() as session:
            db_stage = await self.create_model(session, TrackStageOrm, stage)
            return TrackStage.model_validate(db_stage)

    async def list_stages(self, track_id: UUID) -> list[TrackStage]:
        async with self._get_session() as session:
            rows = await self.get_models_where(
                session,
                TrackStageOrm,
                TrackStageOrm.track_id == track_id,
                order_by=[TrackStageOrm.created_at],
            )
            return [TrackStage.model_validate(r) for r in rows]

    async def update_stage(
        self, stage_id: UUID, data: TrackStageUpdate
    ) -> TrackStage | None:
        data.id = stage_id
        async with self._get_session() as session:
            db_stage = await self.update_model(
                session=session, orm_class=TrackStageOrm, data=data
            )
            return TrackStage.model_validate(db_stage) if db_stage else None

    async def get_stage(self, stage_id: UUID) -> TrackStage | None:
        async with self._get_session() as session:
            db_stage = await self.get_model(session, TrackStageOrm, stage_id)
            return TrackStage.model_validate(db_stage) if db_stage else None

    async def delete_stage(self, stage_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, TrackStageOrm, stage_id)

    # --- Entries ---

    async def create_entry(self, entry: TrackEntryCreate) -> TrackEntry:
        async with self._get_session() as session:
            result = await session.execute(
                text(
                    "UPDATE tracks SET next_version = next_version + 1 "
                    "WHERE id = :track_id RETURNING next_version"
                ),
                {"track_id": entry.track_id},
            )
            row = result.fetchone()
            assert row is not None
            version = row[0] - 1

            db_entry = TrackArtifactOrm(
                track_id=entry.track_id,
                artifact_id=entry.artifact_id,
                version=version,
                added_by=entry.added_by,
            )
            session.add(db_entry)
            await session.commit()
            await session.refresh(db_entry)
            return TrackEntry.model_validate(db_entry)

    async def list_entries(
        self,
        track_id: UUID,
        pagination: PaginationParams,
        stage_id: UUID | None = None,
    ) -> tuple[list[TrackEntry], Cursor | None]:
        async with self._get_session() as session:
            conditions = [TrackArtifactOrm.track_id == track_id]
            if stage_id is not None:
                conditions.append(TrackArtifactOrm.stage_id == stage_id)

            result = await self.get_models_with_pagination(
                session,
                TrackArtifactOrm,
                *conditions,
                pagination=pagination,
            )
            db_entries = result.items
            cursor = (
                None
                if not result.has_more
                else self._get_cursor_from_record(db_entries[-1], pagination)
            )
            return [TrackEntry.model_validate(e) for e in db_entries], cursor

    async def get_entry(self, entry_id: UUID) -> TrackEntry | None:
        async with self._get_session() as session:
            db_entry = await self.get_model(session, TrackArtifactOrm, entry_id)
            return TrackEntry.model_validate(db_entry) if db_entry else None

    async def update_entry(
        self,
        entry_id: UUID,
        data: TrackEntryUpdate,
        force: bool = False,
    ) -> TrackEntry | None:
        data.id = entry_id
        async with self._get_session() as session:
            db_entry = await self.get_model(session, TrackArtifactOrm, entry_id)
            if db_entry is None:
                return None

            if force and data.stage_id is not None:
                await self.clear_stage_from_entries_in_session(
                    session, db_entry.track_id, data.stage_id
                )
                await session.refresh(db_entry)

            fields = data.model_dump(exclude_unset=True, exclude={"id"})
            for field, value in fields.items():
                setattr(db_entry, field, value)

            await session.commit()
            await session.refresh(db_entry)
            return TrackEntry.model_validate(db_entry)

    async def delete_entry(self, entry_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, TrackArtifactOrm, entry_id)

    async def list_entries_for_artifact(
        self, artifact_id: UUID
    ) -> list[TrackEntry]:
        async with self._get_session() as session:
            rows = await self.get_models_where(
                session,
                TrackArtifactOrm,
                TrackArtifactOrm.artifact_id == artifact_id,
                order_by=[TrackArtifactOrm.created_at],
            )
            return [TrackEntry.model_validate(r) for r in rows]

    async def has_entries_for_artifact(self, artifact_id: UUID) -> bool:
        async with self._get_session() as session:
            count = await self.get_model_count(
                session,
                TrackArtifactOrm,
                TrackArtifactOrm.artifact_id == artifact_id,
            )
            return count > 0

    async def clear_stage_from_entries(
        self, track_id: UUID, stage_id: UUID
    ) -> None:
        async with self._get_session() as session:
            await session.execute(
                update(TrackArtifactOrm)
                .where(
                    TrackArtifactOrm.track_id == track_id,
                    TrackArtifactOrm.stage_id == stage_id,
                )
                .values(stage_id=None)
            )
            await session.commit()

    @staticmethod
    async def clear_stage_from_entries_in_session(
        session: AsyncSession,
        track_id: UUID,
        stage_id: UUID,
    ) -> None:
        await session.execute(
            update(TrackArtifactOrm)
            .where(
                TrackArtifactOrm.track_id == track_id,
                TrackArtifactOrm.stage_id == stage_id,
            )
            .values(stage_id=None)
        )
        await session.flush()

    async def get_entry_by_stage(
        self, track_id: UUID, stage_id: UUID
    ) -> TrackEntry | None:
        async with self._get_session() as session:
            db_entry = await self.get_model_where(
                session,
                TrackArtifactOrm,
                TrackArtifactOrm.track_id == track_id,
                TrackArtifactOrm.stage_id == stage_id,
            )
            return TrackEntry.model_validate(db_entry) if db_entry else None

    async def is_stage_in_use(self, stage_id: UUID) -> bool:
        async with self._get_session() as session:
            count = await self.get_model_count(
                session,
                TrackArtifactOrm,
                TrackArtifactOrm.stage_id == stage_id,
            )
            return count > 0
