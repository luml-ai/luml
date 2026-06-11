from typing import Any
from uuid import UUID

from sqlalchemy import (
    String,
    cast,
    delete,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from luml.infra.exceptions import ApplicationError
from luml.models.artifacts import ArtifactOrm
from luml.models.tracks import TrackArtifactOrm, TrackOrm, TrackStageOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.general import Cursor, PaginationParams
from luml.schemas.track_base import TrackBase
from luml.schemas.tracks import (
    Stage,
    StageCreate,
    StageUpdate,
    StageUpsertIn,
    Track,
    TrackCreate,
    TrackEntry,
    TrackEntryCreate,
    TrackEntrySortBy,
    TrackEntryUpdate,
    TrackUpdate,
)


class TrackRepository(RepositoryBase, CrudMixin):
    async def create_track(
        self, track: TrackCreate, stage_names: list[str] | None = None
    ) -> Track:
        async with self._get_session() as session:
            db_track = TrackOrm(**track.model_dump())
            session.add(db_track)
            await session.flush()
            if stage_names:
                session.add_all(
                    TrackStageOrm(track_id=db_track.id, name=name)
                    for name in stage_names
                )
            await session.commit()
            await session.refresh(db_track)
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
                conditions.append(or_(*[TrackOrm.artifact_type == t for t in types]))

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
        self,
        track_id: UUID,
        data: TrackUpdate,
        stages: list[StageUpsertIn] | None = None,
    ) -> Track | None:
        data.id = track_id
        async with self._get_session() as session:
            db_track = await self.get_model(session, TrackOrm, track_id)
            if db_track is None:
                return None

            fields = data.model_dump(exclude_unset=True, exclude={"id"})
            for field, value in fields.items():
                setattr(db_track, field, value)

            if stages is not None:
                await TrackStageRepository.apply_stage_sync(session, track_id, stages)

            await session.commit()
            await session.refresh(db_track)
            return Track.model_validate(db_track)

    async def delete_track(self, track_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, TrackOrm, track_id)

    async def get_tracks_for_artifact(self, artifact_id: UUID) -> list[TrackBase]:
        async with self._get_session() as session:
            rows = await self.get_models_where(
                session,
                TrackOrm,
                TrackOrm.id.in_(
                    select(TrackArtifactOrm.track_id).where(
                        TrackArtifactOrm.artifact_id == artifact_id
                    )
                ),
                order_by=[TrackOrm.created_at],
            )
            return [TrackBase.model_validate(t) for t in rows]


class TrackStageRepository(RepositoryBase, CrudMixin):
    async def create_stage(self, stage: StageCreate) -> Stage:
        async with self._get_session() as session:
            db_stage = await self.create_model(session, TrackStageOrm, stage)
            return Stage.model_validate(db_stage)

    async def list_stages(self, track_id: UUID) -> list[Stage]:
        async with self._get_session() as session:
            rows = await self.get_models_where(
                session,
                TrackStageOrm,
                TrackStageOrm.track_id == track_id,
                order_by=[TrackStageOrm.created_at],
            )
            return [Stage.model_validate(r) for r in rows]

    async def update_stage(self, stage_id: UUID, data: StageUpdate) -> Stage | None:
        data.id = stage_id
        async with self._get_session() as session:
            db_stage = await self.update_model(
                session=session, orm_class=TrackStageOrm, data=data
            )
            return Stage.model_validate(db_stage) if db_stage else None

    async def get_stage(self, stage_id: UUID) -> Stage | None:
        async with self._get_session() as session:
            db_stage = await self.get_model(session, TrackStageOrm, stage_id)
            return Stage.model_validate(db_stage) if db_stage else None

    async def delete_stage(self, stage_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, TrackStageOrm, stage_id)

    async def clear_stage_from_entries(self, track_id: UUID, stage_id: UUID) -> None:
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

    async def is_stage_in_use(self, stage_id: UUID) -> bool:
        async with self._get_session() as session:
            count = await self.get_model_count(
                session,
                TrackArtifactOrm,
                TrackArtifactOrm.stage_id == stage_id,
            )
            return count > 0

    @staticmethod
    async def apply_stage_sync(
        session: AsyncSession, track_id: UUID, desired: list[StageUpsertIn]
    ) -> None:
        current = await CrudMixin.get_models_where(
            session, TrackStageOrm, TrackStageOrm.track_id == track_id
        )
        current_by_id = {stage.id: stage for stage in current}
        desired_ids = {item.id for item in desired if item.id is not None}

        for item in desired:
            if item.id is not None and item.id not in current_by_id:
                raise ApplicationError("Stage does not belong to this track.", 422)

        to_delete = [s for s in current if s.id not in desired_ids]

        if to_delete:
            delete_by_id = {s.id: s for s in to_delete}
            used_stage_ids = await CrudMixin.get_models_where(
                session,
                TrackArtifactOrm,
                TrackArtifactOrm.stage_id.in_(list(delete_by_id)),
                select_fields=[TrackArtifactOrm.stage_id],
                distinct=True,
            )
            if used_stage_ids:
                listed = ", ".join(
                    f"'{delete_by_id[sid].name}' ({sid})" for sid in used_stage_ids
                )
                raise ApplicationError(
                    f"Cannot remove stages that are assigned to a version: {listed}.",
                    409,
                )
            for stage in to_delete:
                await session.delete(stage)

        for item in desired:
            if item.id is not None and current_by_id[item.id].name != item.name:
                current_by_id[item.id].name = item.name

        session.add_all(
            TrackStageOrm(track_id=track_id, name=item.name)
            for item in desired
            if item.id is None
        )

    async def sync_stages(self, track_id: UUID, desired: list[StageUpsertIn]) -> None:
        async with self._get_session() as session:
            await self.apply_stage_sync(session, track_id, desired)
            try:
                await session.commit()
            except IntegrityError as error:
                raise ApplicationError(
                    "Duplicate stage names are not allowed.", 409
                ) from error


class TrackEntryRepository(RepositoryBase, CrudMixin):
    _SORT_COLUMNS = {
        TrackEntrySortBy.ARTIFACT_NAME.value: (
            select(ArtifactOrm.name)
            .where(ArtifactOrm.id == TrackArtifactOrm.artifact_id)
            .scalar_subquery()
        ),
        TrackEntrySortBy.DESCRIPTION.value: (
            select(ArtifactOrm.description)
            .where(ArtifactOrm.id == TrackArtifactOrm.artifact_id)
            .scalar_subquery()
        ),
        TrackEntrySortBy.STAGE.value: (
            select(TrackStageOrm.name)
            .where(TrackStageOrm.id == TrackArtifactOrm.stage_id)
            .scalar_subquery()
        ),
        TrackEntrySortBy.VERSION.value: TrackArtifactOrm.version,
        TrackEntrySortBy.CREATED_AT.value: TrackArtifactOrm.created_at,
    }

    @staticmethod
    def _entry_cursor_value(entry: TrackArtifactOrm, sort_by: str | None) -> Any:  # noqa: ANN401
        if sort_by == TrackEntrySortBy.ARTIFACT_NAME.value:
            return entry.artifact.name if entry.artifact else None
        if sort_by == TrackEntrySortBy.DESCRIPTION.value:
            return entry.artifact.description if entry.artifact else None
        if sort_by == TrackEntrySortBy.STAGE.value:
            return entry.stage.name if entry.stage else None
        return getattr(entry, sort_by or "created_at", entry.created_at)

    @staticmethod
    def _get_sort_col(  # type: ignore[override]
        orm_class: type[TrackArtifactOrm],
        sort_by: str | None = None,
        extra_sort_field: str | None = None,
    ) -> Any:  # noqa: ANN401
        return TrackEntryRepository._SORT_COLUMNS.get(
            sort_by or "created_at", TrackArtifactOrm.created_at
        )

    @staticmethod
    def _get_cursor_from_record(  # type: ignore[override]
        cursor_rec: TrackArtifactOrm,
        pagination: PaginationParams,
    ) -> Cursor:
        return Cursor(
            id=cursor_rec.id,
            value=TrackEntryRepository._entry_cursor_value(
                cursor_rec, pagination.sort_by
            ),
            sort_by=pagination.sort_by,
            order=pagination.order,
            scope_id=pagination.scope_id,
        )

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
                stage_id=entry.stage_id,
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

    async def delete_entries(self, track_id: UUID, entry_ids: list[UUID]) -> None:
        async with self._get_session() as session:
            await session.execute(
                delete(TrackArtifactOrm).where(
                    TrackArtifactOrm.track_id == track_id,
                    TrackArtifactOrm.id.in_(entry_ids),
                )
            )
            await session.commit()

    async def list_entries_for_artifact(self, artifact_id: UUID) -> list[TrackEntry]:
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
