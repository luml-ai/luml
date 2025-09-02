from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from dataforce_studio.models import SatelliteOrm, SatelliteQueueOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.satellite import (
    Satellite,
    SatelliteCapability,
    SatelliteCreate,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)


class SatelliteRepository(RepositoryBase, CrudMixin):
    async def create_satellite(
        self, satellite: SatelliteCreate, payload: dict[str, Any] | None = None
    ) -> tuple[Satellite, SatelliteQueueTask]:
        async with self._get_session() as session:
            db_sat = SatelliteOrm(**satellite.model_dump())
            session.add(db_sat)
            await session.flush()
            task = SatelliteQueueOrm(
                satellite_id=db_sat.id,
                orbit_id=satellite.orbit_id,
                type=SatelliteTaskType.PAIRING,
                payload=payload or {},
            )
            session.add(task)
            await session.commit()
            await session.refresh(db_sat)
            await session.refresh(task)
            return db_sat.to_satellite(), task.to_queue_task()

    async def get_satellite(self, satellite_id: int) -> Satellite | None:
        async with self._get_session() as session:
            db_sat = await self.get_model(session, SatelliteOrm, satellite_id)
            return db_sat.to_satellite() if db_sat else None

    async def get_satellite_by_hash(self, api_key_hash: str) -> Satellite | None:
        async with self._get_session() as session:
            db_sat = await self.get_model_where(
                session, SatelliteOrm, SatelliteOrm.api_key_hash == api_key_hash
            )
            return db_sat.to_satellite() if db_sat else None

    async def list_satellites(
        self, orbit_id: int, paired: bool | None = None
    ) -> list[Satellite]:
        async with self._get_session() as session:
            query = select(SatelliteOrm).where(SatelliteOrm.orbit_id == orbit_id)
            if paired is not None:
                query = query.where(SatelliteOrm.paired == paired)
            result = await session.execute(query.order_by(SatelliteOrm.id))
            sats = result.scalars().all()
            return [s.to_satellite() for s in sats]

    async def pair_satellite(
        self,
        satellite_id: int,
        base_url: str,
        capabilities: dict[SatelliteCapability, dict[str, str | int] | None],
    ) -> Satellite | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(SatelliteOrm).where(SatelliteOrm.id == satellite_id)
            )
            sat = result.scalar_one_or_none()
            if not sat:
                return None
            sat.paired = True
            sat.base_url = base_url
            sat.capabilities = capabilities
            sat.last_seen_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(sat)
            return sat.to_satellite()

    async def list_tasks(
        self,
        satellite_id: int,
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
        satellite_id: int,
        task_id: int,
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
            now = datetime.utcnow()
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

    async def touch_last_seen(self, satellite_id: int) -> None:
        async with self._get_session() as session:
            result = await session.execute(
                select(SatelliteOrm).where(SatelliteOrm.id == satellite_id)
            )
            sat = result.scalar_one_or_none()
            if sat:
                sat.last_seen_at = datetime.now(UTC)
                await session.commit()
