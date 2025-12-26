from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from luml.infra.exceptions import DatabaseConstraintError
from luml.models import SatelliteOrm, SatelliteQueueOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.satellite import (
    Satellite,
    SatelliteCreate,
    SatellitePair,
    SatelliteQueueTask,
    SatelliteRegenerateApiKey,
    SatelliteTaskStatus,
    SatelliteUpdate,
)


class SatelliteRepository(RepositoryBase, CrudMixin):
    async def create_satellite(self, satellite: SatelliteCreate) -> Satellite:
        async with self._get_session() as session:
            db_sat = await self.create_model(session, SatelliteOrm, satellite)
            return db_sat.to_satellite()

    async def get_satellite(self, satellite_id: UUID) -> Satellite | None:
        async with self._get_session() as session:
            db_sat = await self.get_model(session, SatelliteOrm, satellite_id)
            return db_sat.to_satellite() if db_sat else None

    async def get_satellite_by_hash(self, api_key_hash: str) -> Satellite | None:
        async with self._get_session() as session:
            db_sat = await self.get_model_where(
                session, SatelliteOrm, SatelliteOrm.api_key_hash == api_key_hash
            )
            return db_sat.to_satellite() if db_sat else None

    async def update_satellite(
        self, satellite: SatelliteUpdate | SatelliteRegenerateApiKey
    ) -> Satellite | None:
        async with self._get_session() as session:
            db_satellite = await self.update_model(session, SatelliteOrm, satellite)
            return db_satellite.to_satellite() if db_satellite else None

    async def list_satellites(
        self, orbit_id: UUID, paired: bool | None = None
    ) -> list[Satellite]:
        async with self._get_session() as session:
            query = select(SatelliteOrm).where(SatelliteOrm.orbit_id == orbit_id)
            if paired is not None:
                query = query.where(SatelliteOrm.paired == paired)
            result = await session.execute(query.order_by(SatelliteOrm.id))
            satellites = result.scalars().all()
            return [s.to_satellite() for s in satellites]

    async def pair_satellite(self, satellite: SatellitePair) -> Satellite | None:
        async with self._get_session() as session:
            db_satellite = await self.update_model(session, SatelliteOrm, satellite)
            return db_satellite.to_satellite() if db_satellite else None

    async def list_tasks(
        self,
        satellite_id: UUID,
        status: SatelliteTaskStatus | None = None,
    ) -> list[SatelliteQueueTask]:
        async with self._get_session() as session:
            query = select(SatelliteQueueOrm).where(
                SatelliteQueueOrm.satellite_id == satellite_id
            )
            if status:
                query = query.where(SatelliteQueueOrm.status == status)
            result = await session.execute(
                query.order_by(SatelliteQueueOrm.scheduled_at)
            )
            tasks = result.scalars().all()
            return [t.to_queue_task() for t in tasks]

    async def update_task_status(
        self,
        satellite_id: UUID,
        task_id: UUID,
        status: SatelliteTaskStatus,
        result_payload: dict[str, Any] | None = None,
    ) -> SatelliteQueueTask | None:
        async with self._get_session() as session:
            res = await session.execute(
                select(SatelliteQueueOrm).where(
                    SatelliteQueueOrm.id == task_id,
                    SatelliteQueueOrm.satellite_id == satellite_id,
                )
            )
            task = res.scalar_one_or_none()
            if not task:
                return None
            now = datetime.now(UTC)
            if status == SatelliteTaskStatus.RUNNING:
                task.started_at = now
            if status in {SatelliteTaskStatus.DONE, SatelliteTaskStatus.FAILED}:
                task.finished_at = now
            task.status = status
            if result_payload is not None:
                task.result = result_payload
            await session.commit()
            await session.refresh(task)
            return task.to_queue_task()

    async def touch_last_seen(self, satellite_id: UUID) -> None:
        async with self._get_session() as session:
            result = await session.execute(
                select(SatelliteOrm).where(SatelliteOrm.id == satellite_id)
            )
            sat = result.scalar_one_or_none()
            if sat:
                sat.last_seen_at = datetime.now(UTC)
                await session.commit()

    async def delete_satellite(self, satellite_id: UUID) -> None:
        try:
            async with self._get_session() as session:
                return await self.delete_model(session, SatelliteOrm, satellite_id)
        except IntegrityError as error:
            error_mess = "Cannot delete satellite."
            raise DatabaseConstraintError(
                error_mess + " It is used in deployments."
                if "deployments" in str(error)
                else error_mess
            ) from error
