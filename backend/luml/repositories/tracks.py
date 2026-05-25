from uuid import UUID

from sqlalchemy import func, select, update

from luml.models.tracks import TrackArtifactOrm, TrackOrm, TrackStageOrm
from luml.repositories.base import RepositoryBase
from luml.schemas.general import Cursor, SortOrder
from luml.schemas.tracks import (
    TrackCreate,
    TrackStageCreate,
    TrackStageUpdate,
    TrackUpdate,
)

DEFAULT_STAGES = ["Staging", "Pre-Production", "Production", "Archived"]


class TrackRepository(RepositoryBase):
    async def create_track(
        self, data: TrackCreate, orbit_id: UUID, user_id: UUID
    ) -> TrackOrm:
        async with self._get_session() as session:
            track = TrackOrm(
                orbit_id=orbit_id,
                created_by=user_id,
                **data.model_dump(),
            )
            session.add(track)
            await session.flush()

            for stage_name in DEFAULT_STAGES:
                stage = TrackStageOrm(track_id=track.id, name=stage_name)
                session.add(stage)

            await session.commit()
            await session.refresh(track)
            return track

    async def get_track(self, track_id: UUID) -> TrackOrm | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackOrm).where(TrackOrm.id == track_id)
            )
            return result.scalar_one_or_none()

    async def list_tracks(self, orbit_id: UUID) -> list[TrackOrm]:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackOrm)
                .where(TrackOrm.orbit_id == orbit_id)
                .order_by(TrackOrm.created_at.desc())
            )
            return list(result.scalars().all())

    async def update_track(
        self, track: TrackOrm, data: TrackUpdate
    ) -> TrackOrm:
        async with self._get_session() as session:
            merged = await session.merge(track)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(merged, field, value)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def delete_track(self, track: TrackOrm) -> None:
        async with self._get_session() as session:
            merged = await session.merge(track)
            await session.delete(merged)
            await session.commit()

    # --- Stages ---

    async def create_stage(
        self, track_id: UUID, data: TrackStageCreate
    ) -> TrackStageOrm:
        async with self._get_session() as session:
            stage = TrackStageOrm(track_id=track_id, **data.model_dump())
            session.add(stage)
            await session.commit()
            await session.refresh(stage)
            return stage

    async def get_stage(self, stage_id: UUID) -> TrackStageOrm | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackStageOrm).where(TrackStageOrm.id == stage_id)
            )
            return result.scalar_one_or_none()

    async def list_stages(self, track_id: UUID) -> list[TrackStageOrm]:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackStageOrm)
                .where(TrackStageOrm.track_id == track_id)
                .order_by(TrackStageOrm.created_at.asc())
            )
            return list(result.scalars().all())

    async def update_stage(
        self, stage: TrackStageOrm, data: TrackStageUpdate
    ) -> TrackStageOrm:
        async with self._get_session() as session:
            merged = await session.merge(stage)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(merged, field, value)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def delete_stage(self, stage: TrackStageOrm) -> None:
        async with self._get_session() as session:
            merged = await session.merge(stage)
            await session.delete(merged)
            await session.commit()

    async def clear_stage_from_entries(self, stage_id: UUID) -> None:
        async with self._get_session() as session:
            await session.execute(
                update(TrackArtifactOrm)
                .where(TrackArtifactOrm.stage_id == stage_id)
                .values(stage_id=None)
            )
            await session.commit()

    # --- Entries ---

    async def add_entry(
        self, track: TrackOrm, artifact_id: UUID, user_id: UUID
    ) -> TrackArtifactOrm:
        async with self._get_session() as session:
            merged_track = await session.merge(track)
            version = merged_track.next_version
            merged_track.next_version = version + 1

            entry = TrackArtifactOrm(
                track_id=merged_track.id,
                artifact_id=artifact_id,
                version=version,
                added_by=user_id,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def get_entry(self, entry_id: UUID) -> TrackArtifactOrm | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackArtifactOrm).where(
                    TrackArtifactOrm.id == entry_id
                )
            )
            return result.scalar_one_or_none()

    async def list_entries(
        self,
        track_id: UUID,
        stage_name: str | None = None,
        cursor: Cursor | None = None,
        page_size: int = 20,
    ) -> list[TrackArtifactOrm]:
        async with self._get_session() as session:
            stmt = select(TrackArtifactOrm).where(
                TrackArtifactOrm.track_id == track_id
            )

            if stage_name is not None:
                stmt = stmt.join(TrackStageOrm).where(
                    TrackStageOrm.name == stage_name
                )

            if cursor is not None and cursor.value is not None:
                from operator import gt, lt

                op = lt if cursor.order == SortOrder.DESC else gt
                stmt = stmt.where(op(TrackArtifactOrm.created_at, cursor.value))

            stmt = stmt.order_by(TrackArtifactOrm.created_at.desc()).limit(
                page_size
            )

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_entry_holding_stage(
        self, track_id: UUID, stage_id: UUID
    ) -> TrackArtifactOrm | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackArtifactOrm).where(
                    TrackArtifactOrm.track_id == track_id,
                    TrackArtifactOrm.stage_id == stage_id,
                )
            )
            return result.scalar_one_or_none()

    async def update_entry_stage(
        self, entry: TrackArtifactOrm, stage_id: UUID | None
    ) -> TrackArtifactOrm:
        async with self._get_session() as session:
            merged = await session.merge(entry)
            merged.stage_id = stage_id
            await session.commit()
            await session.refresh(merged)
            return merged

    async def delete_entry(self, entry: TrackArtifactOrm) -> None:
        async with self._get_session() as session:
            merged = await session.merge(entry)
            await session.delete(merged)
            await session.commit()

    async def list_entries_for_artifact(
        self, orbit_id: UUID, artifact_id: UUID
    ) -> list[TrackArtifactOrm]:
        async with self._get_session() as session:
            result = await session.execute(
                select(TrackArtifactOrm)
                .join(TrackOrm)
                .where(
                    TrackOrm.orbit_id == orbit_id,
                    TrackArtifactOrm.artifact_id == artifact_id,
                )
                .order_by(TrackArtifactOrm.created_at.desc())
            )
            return list(result.scalars().all())

    async def has_entries_for_artifact(self, artifact_id: UUID) -> bool:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(TrackArtifactOrm)
                .where(TrackArtifactOrm.artifact_id == artifact_id)
            )
            count = result.scalar() or 0
            return count > 0
