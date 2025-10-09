from uuid import UUID

from sqlalchemy import select

from dataforce_studio.models import DeploymentOrm, SatelliteQueueOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentDetailsUpdate,
    DeploymentStatus,
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
                payload={"deployment_id": str(db_dep.id)},
            )
            session.add(task)
            await session.commit()
            await session.refresh(db_dep)
            await session.refresh(task)
            return db_dep.to_deployment(), task.to_queue_task()

    async def list_deployments(self, orbit_id: UUID) -> list[Deployment]:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(DeploymentOrm.orbit_id == orbit_id)
            )
            deployments = result.scalars().all()
            return [d.to_deployment() for d in deployments]

    async def get_deployment(
        self, deployment_id: UUID, orbit_id: UUID | None = None
    ) -> Deployment | None:
        async with self._get_session() as session:
            query = select(DeploymentOrm).where(DeploymentOrm.id == deployment_id)
            if orbit_id is not None:
                query = query.where(DeploymentOrm.orbit_id == orbit_id)
            result = await session.execute(query)
            dep = result.scalar_one_or_none()
            return dep.to_deployment() if dep else None

    async def list_satellite_deployments(self, satellite_id: UUID) -> list[Deployment]:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(DeploymentOrm.satellite_id == satellite_id)
            )
            deployments = result.scalars().all()
            return [d.to_deployment() for d in deployments]

    async def update_deployment(
        self,
        deployment_id: UUID,
        satellite_id: UUID,
        update: DeploymentUpdate,
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

    async def request_deployment_deletion(
        self, orbit_id: UUID, deployment_id: UUID
    ) -> tuple[Deployment, SatelliteQueueTask | None] | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm)
                .where(
                    DeploymentOrm.id == deployment_id,
                    DeploymentOrm.orbit_id == orbit_id,
                )
                .with_for_update()
            )
            dep = result.scalar_one_or_none()
            if not dep:
                return None

            if dep.status in (
                DeploymentStatus.DELETION_PENDING.value,
                DeploymentStatus.DELETED.value,
            ):
                return dep.to_deployment(), None

            dep.status = DeploymentStatus.DELETION_PENDING

            task = SatelliteQueueOrm(
                satellite_id=dep.satellite_id,
                orbit_id=dep.orbit_id,
                type=SatelliteTaskType.UNDEPLOY,
                payload={"deployment_id": str(dep.id)},
            )
            session.add(task)
            await session.commit()
            await session.refresh(dep)
            await session.refresh(task)
            return dep.to_deployment(), task.to_queue_task()

    async def update_deployment_details(
        self,
        orbit_id: UUID,
        deployment_id: UUID,
        update: DeploymentDetailsUpdate,
    ) -> Deployment | None:
        async with self._get_session() as session:
            db_dep = await self.update_model_where(
                session,
                DeploymentOrm,
                update,
                DeploymentOrm.id == deployment_id,
                DeploymentOrm.orbit_id == orbit_id,
            )
            return db_dep.to_deployment() if db_dep else None
