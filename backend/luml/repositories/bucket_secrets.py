from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from luml.infra.encryption import encrypt
from luml.infra.exceptions import DatabaseConstraintError
from luml.models import BucketSecretOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.bucket_secrets import (
    BucketSecret,
    BucketSecretCreate,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketType,
    validate_bucket_secret_out,
)


class BucketSecretRepository(RepositoryBase, CrudMixin):
    async def create_bucket_secret(self, secret: BucketSecretCreate) -> BucketSecret:
        async with self._get_session() as session:
            orm_secret = BucketSecretOrm.from_bucket_secret(secret)
            session.add(orm_secret)
            try:
                await session.commit()
                await session.refresh(orm_secret)
                return orm_secret.to_bucket_secret()
            except IntegrityError as e:
                raise DatabaseConstraintError() from e

    async def get_bucket_secret(
        self, secret_id: UUID, organization_id: UUID | None = None
    ) -> BucketSecret | None:
        async with self._get_session() as session:
            conditions: list[Any] = [BucketSecretOrm.id == secret_id]
            if organization_id is not None:
                conditions.append(BucketSecretOrm.organization_id == organization_id)
            db_secret = await self.get_model_where(
                session, BucketSecretOrm, *conditions
            )
            return db_secret.to_bucket_secret() if db_secret else None

    async def get_bucket_secret_details(
        self, secret_id: UUID, organization_id: UUID
    ) -> BucketSecretOut | None:
        async with self._get_session() as session:
            db_secret = await self.get_model_where(
                session,
                BucketSecretOrm,
                BucketSecretOrm.id == secret_id,
                BucketSecretOrm.organization_id == organization_id,
            )
            return validate_bucket_secret_out(db_secret) if db_secret else None

    async def get_organization_bucket_secrets(
        self, organization_id: UUID
    ) -> list[BucketSecretOut]:
        async with self._get_session() as session:
            db_secrets = await self.get_models_where(
                session,
                BucketSecretOrm,
                BucketSecretOrm.organization_id == organization_id,
            )
            return [validate_bucket_secret_out(secret) for secret in db_secrets]

    async def update_bucket_secret(
        self, secret: BucketSecretUpdate, organization_id: UUID
    ) -> BucketSecret | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(BucketSecretOrm).where(
                    BucketSecretOrm.id == secret.id,
                    BucketSecretOrm.organization_id == organization_id,
                )
            )
            db_secret = result.scalar_one_or_none()

            if not db_secret:
                return None

            update_data = secret.model_dump(exclude_unset=True, exclude={"type"})
            if db_secret.type == BucketType.S3:
                if secret.access_key is not None:
                    update_data["access_key"] = encrypt(secret.access_key)
                if secret.secret_key is not None:
                    update_data["secret_key"] = encrypt(secret.secret_key)
                if secret.session_token is not None:
                    update_data["session_token"] = encrypt(secret.session_token)
            for field, value in update_data.items():
                setattr(db_secret, field, value)
            try:
                await session.commit()
                await session.refresh(db_secret)
                return db_secret.to_bucket_secret()
            except IntegrityError as e:
                raise DatabaseConstraintError() from e

    async def delete_bucket_secret(
        self, secret_id: UUID, organization_id: UUID
    ) -> bool:
        async with self._get_session() as session:
            db_secret = await self.get_model_where(
                session,
                BucketSecretOrm,
                BucketSecretOrm.id == secret_id,
                BucketSecretOrm.organization_id == organization_id,
            )
            if not db_secret:
                return False
            await session.delete(db_secret)
            try:
                await session.commit()
            except IntegrityError as e:
                raise DatabaseConstraintError() from e
            return True
