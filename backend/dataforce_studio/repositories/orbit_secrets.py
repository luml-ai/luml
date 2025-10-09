from uuid import UUID

from sqlalchemy.exc import IntegrityError

from dataforce_studio.infra.encryption import encrypt
from dataforce_studio.infra.exceptions import DatabaseConstraintError
from dataforce_studio.models import OrbitSecretOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.orbit_secret import (
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

    async def get_orbit_secret(self, secret_id: UUID) -> OrbitSecret | None:
        async with self._get_session() as session:
            db_secret = await self.get_model(session, OrbitSecretOrm, secret_id)
            return db_secret.to_orbit_secret() if db_secret else None

    async def get_orbit_secrets(self, orbit_id: UUID) -> list[OrbitSecret]:
        async with self._get_session() as session:
            db_secrets = await self.get_models_where(
                session, OrbitSecretOrm, OrbitSecretOrm.orbit_id == orbit_id
            )
            return [s.to_orbit_secret() for s in db_secrets]

    async def delete_orbit_secret(self, secret_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, OrbitSecretOrm, secret_id)

    async def update_orbit_secret(
        self, secret_id: UUID, secret: OrbitSecretUpdate
    ) -> OrbitSecret | None:
        async with self._get_session() as session:
            db_secret = await self.get_model(session, OrbitSecretOrm, secret_id)
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
