from sqlalchemy import select

from dataforce_studio.models import DeploymentOrm, SatelliteQueueOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentUpdate,
)
from dataforce_studio.schemas.satellite import SatelliteQueueTask, SatelliteTaskType


class DeploymentRepository(RepositoryBase, CrudMixin):
    async def create_deployment(
        self, deployment: DeploymentCreate
    ) -> tuple[Deployment, SatelliteQueueTask]:
        async with self._get_session() as session:
            db_dep = DeploymentOrm(**deployment.model_dump())
            session.add(db_dep)
            await session.flush()
            task = SatelliteQueueOrm(
                satellite_id=deployment.satellite_id,
                orbit_id=deployment.orbit_id,
                type=SatelliteTaskType.DEPLOY,
                payload={"deployment_id": db_dep.id},
            )
            session.add(task)
            await session.commit()
            await session.refresh(db_dep)
            await session.refresh(task)
            return db_dep.to_deployment(), task.to_queue_task()

    async def list_deployments(self, orbit_id: int) -> list[Deployment]:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(DeploymentOrm.orbit_id == orbit_id)
            )
            deployments = result.scalars().all()
            return [d.to_deployment() for d in deployments]

    async def get_deployment(
        self, deployment_id: int, orbit_id: int | None = None
    ) -> Deployment | None:
        async with self._get_session() as session:
            query = select(DeploymentOrm).where(DeploymentOrm.id == deployment_id)
            if orbit_id is not None:
                query = query.where(DeploymentOrm.orbit_id == orbit_id)
            result = await session.execute(query)
            dep = result.scalar_one_or_none()
            return dep.to_deployment() if dep else None

    async def list_satellite_deployments(self, satellite_id: int) -> list[Deployment]:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(DeploymentOrm.satellite_id == satellite_id)
            )
            deployments = result.scalars().all()
            return [d.to_deployment() for d in deployments]

    async def update_deployment(
        self, deployment_id: int, satellite_id: int, update: DeploymentUpdate
    ) -> Deployment | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(
                    DeploymentOrm.id == deployment_id,
                    DeploymentOrm.satellite_id == satellite_id,
                )
            )
            dep = result.scalar_one_or_none()
            if not dep:
                return None
            for field, value in update.model_dump(exclude_unset=True).items():
                setattr(dep, field, value)
            await session.commit()
            await session.refresh(dep)
            return dep.to_deployment()
