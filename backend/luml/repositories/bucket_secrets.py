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
    BucketSecretUpdate,
    S3BucketSecretUpdate,
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

    async def get_bucket_secret(self, secret_id: UUID) -> BucketSecret | None:
        async with self._get_session() as session:
            db_secret = await self.get_model(session, BucketSecretOrm, secret_id)
            return db_secret.to_bucket_secret() if db_secret else None

    async def get_organization_bucket_secrets(
        self, organization_id: UUID
    ) -> list[BucketSecret]:
        async with self._get_session() as session:
            db_secrets = await self.get_models_where(
                session,
                BucketSecretOrm,
                BucketSecretOrm.organization_id == organization_id,
            )
            return [secret.to_bucket_secret() for secret in db_secrets]

    async def update_bucket_secret(
        self, secret: BucketSecretUpdate
    ) -> BucketSecret | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(BucketSecretOrm).where(BucketSecretOrm.id == secret.id)
            )
            db_secret = result.scalar_one_or_none()
            if not db_secret:
                return None
            update_data = secret.model_dump(exclude_unset=True)
            if isinstance(secret, S3BucketSecretUpdate):
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

    async def delete_bucket_secret(self, secret_id: UUID) -> None:
        async with self._get_session() as session:
            try:
                return await self.delete_model(session, BucketSecretOrm, secret_id)
            except IntegrityError as e:
                raise DatabaseConstraintError() from e
