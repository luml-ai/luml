from uuid import UUID

from sqlalchemy import select

from luml.models import DeploymentOrm, SatelliteQueueOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentDetailsUpdate,
    DeploymentStatus,
    DeploymentUpdate,
)
from luml.schemas.satellite import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)


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
                select(DeploymentOrm)
                .where(DeploymentOrm.orbit_id == orbit_id)
                .order_by(DeploymentOrm.created_at.desc())
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

    async def get_satellite_deployment(
        self, deployment_id: UUID, satellite_id: UUID
    ) -> Deployment | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(
                    DeploymentOrm.id == deployment_id,
                    DeploymentOrm.satellite_id == satellite_id,
                )
            )
            dep = result.scalar_one_or_none()
            return dep.to_deployment() if dep else None

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

            if dep.status == DeploymentStatus.DELETION_PENDING.value:
                return dep.to_deployment(), None

            dep.status = DeploymentStatus.DELETION_PENDING.value

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

    async def delete_deployment(self, deployment_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, DeploymentOrm, deployment_id)

    async def delete_deployments_by_model_id(self, model_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_models_where(
                session, DeploymentOrm, DeploymentOrm.model_id == model_id
            )

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

    async def enqueue_undeploy_task(
        self, deployment_id: UUID
    ) -> SatelliteQueueTask | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(DeploymentOrm).where(DeploymentOrm.id == deployment_id)
            )
            deployment = result.scalar_one_or_none()
            if not deployment:
                return None

            existing_task_result = await session.execute(
                select(SatelliteQueueOrm).where(
                    SatelliteQueueOrm.satellite_id == deployment.satellite_id,
                    SatelliteQueueOrm.type == SatelliteTaskType.UNDEPLOY,
                    SatelliteQueueOrm.status.in_(
                        [
                            SatelliteTaskStatus.PENDING,
                            SatelliteTaskStatus.RUNNING,
                        ]
                    ),
                    SatelliteQueueOrm.payload.contains(
                        {"deployment_id": str(deployment.id)}
                    ),
                )
            )
            existing_task = existing_task_result.scalar_one_or_none()
            if existing_task:
                await session.refresh(existing_task)
                return existing_task.to_queue_task()

            task = SatelliteQueueOrm(
                satellite_id=deployment.satellite_id,
                orbit_id=deployment.orbit_id,
                type=SatelliteTaskType.UNDEPLOY,
                payload={"deployment_id": str(deployment.id)},
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task.to_queue_task()
