from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from luml.infra.encryption import encrypt
from luml.infra.exceptions import DatabaseConstraintError, OrbitSecretInUseError
from luml.models import DeploymentOrm, OrbitSecretOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretUpdate,
)


class OrbitSecretRepository(RepositoryBase, CrudMixin):
    async def create_orbit_secret(self, secret: OrbitSecretCreate) -> OrbitSecret:
        async with self._get_session() as session:
            orm_secret = OrbitSecretOrm.from_orbit_secret(secret)
            try:
                session.add(orm_secret)
                await session.commit()
                await session.refresh(orm_secret)
            except IntegrityError as error:
                raise DatabaseConstraintError() from error
            return orm_secret.to_orbit_secret()

    async def get_orbit_secret(
        self, secret_id: UUID, orbit_id: UUID
    ) -> OrbitSecret | None:
        async with self._get_session() as session:
            db_secret = await self.get_model_where(
                session,
                OrbitSecretOrm,
                OrbitSecretOrm.id == secret_id,
                OrbitSecretOrm.orbit_id == orbit_id,
            )
            return db_secret.to_orbit_secret() if db_secret else None

    async def get_orbit_secrets(self, orbit_id: UUID) -> list[OrbitSecret]:
        async with self._get_session() as session:
            db_secrets = await self.get_models_where(
                session, OrbitSecretOrm, OrbitSecretOrm.orbit_id == orbit_id
            )
            return [s.to_orbit_secret() for s in db_secrets]

    async def delete_orbit_secret(self, secret_id: UUID, orbit_id: UUID) -> bool:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrbitSecretOrm)
                .where(
                    OrbitSecretOrm.id == secret_id,
                    OrbitSecretOrm.orbit_id == orbit_id,
                )
                .with_for_update()
            )
            db_secret = result.scalar_one_or_none()
            if not db_secret:
                return False
            deployments = await session.execute(
                select(
                    DeploymentOrm.name,
                    DeploymentOrm.dynamic_attributes_secrets,
                    DeploymentOrm.env_variables_secrets,
                )
                .where(DeploymentOrm.orbit_id == orbit_id)
                .order_by(DeploymentOrm.name)
            )
            secret_ref = str(secret_id)
            users = [
                name
                for name, attributes, variables in deployments
                if secret_ref in (attributes or {}).values()
                or secret_ref in (variables or {}).values()
            ]
            if users:
                raise OrbitSecretInUseError(users)
            await session.delete(db_secret)
            await session.commit()
            return True

    async def update_orbit_secret(
        self, secret_id: UUID, orbit_id: UUID, secret: OrbitSecretUpdate
    ) -> OrbitSecret | None:
        async with self._get_session() as session:
            db_secret = await self.get_model_where(
                session,
                OrbitSecretOrm,
                OrbitSecretOrm.id == secret_id,
                OrbitSecretOrm.orbit_id == orbit_id,
            )
            if not db_secret:
                return None
            update_data = secret.model_dump(exclude_unset=True)
            if "value" in update_data:
                update_data["value"] = encrypt(update_data["value"])
            for field, value in update_data.items():
                setattr(db_secret, field, value)
            await session.commit()
            await session.refresh(db_secret)
            return db_secret.to_orbit_secret()
