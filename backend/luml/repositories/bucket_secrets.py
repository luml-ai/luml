from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from luml.infra.encryption import decrypt, encrypt
from luml.infra.exceptions import DatabaseConstraintError
from luml.models import BucketSecretOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.bucket_secrets import (
    AzureBucketSecretCreateIn,
    BucketSecret,
    BucketSecretCreate,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketType,
    azure_public_endpoint,
)


class BucketSecretRepository(RepositoryBase, CrudMixin):
    async def _check_azure_duplicate(
        self,
        session: AsyncSession,
        organization_id: UUID,
        bucket_name: str,
        endpoint: str,
        exclude_id: UUID | None = None,
    ) -> None:
        conditions: list[Any] = [
            BucketSecretOrm.organization_id == organization_id,
            BucketSecretOrm.type == BucketType.AZURE,
            BucketSecretOrm.bucket_name == bucket_name,
        ]
        if exclude_id is not None:
            conditions.append(BucketSecretOrm.id != exclude_id)
        public_endpoint = azure_public_endpoint(endpoint)
        for existing in await self.get_models_where(
            session, BucketSecretOrm, *conditions
        ):
            if azure_public_endpoint(decrypt(existing.endpoint)) == public_endpoint:
                raise DatabaseConstraintError()

    async def _prepare_azure_update(
        self,
        session: AsyncSession,
        db_secret: BucketSecretOrm,
        update_data: dict[str, Any],
    ) -> None:
        endpoint = decrypt(db_secret.endpoint)
        new_endpoint = update_data.get("endpoint")
        if new_endpoint == azure_public_endpoint(endpoint):
            update_data.pop("endpoint")
        elif new_endpoint is not None:
            AzureBucketSecretCreateIn(
                endpoint=new_endpoint, bucket_name=db_secret.bucket_name
            )
            endpoint = new_endpoint
            update_data["endpoint"] = encrypt(endpoint)
        if "endpoint" in update_data or "bucket_name" in update_data:
            await self._check_azure_duplicate(
                session,
                db_secret.organization_id,
                update_data.get("bucket_name", db_secret.bucket_name),
                endpoint,
                exclude_id=db_secret.id,
            )

    async def create_bucket_secret(self, secret: BucketSecretCreate) -> BucketSecret:
        async with self._get_session() as session:
            if secret.type == BucketType.AZURE:
                await self._check_azure_duplicate(
                    session, secret.organization_id, secret.bucket_name, secret.endpoint
                )
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
            return db_secret.to_bucket_secret_out() if db_secret else None

    async def get_organization_bucket_secrets(
        self, organization_id: UUID
    ) -> list[BucketSecretOut]:
        async with self._get_session() as session:
            db_secrets = await self.get_models_where(
                session,
                BucketSecretOrm,
                BucketSecretOrm.organization_id == organization_id,
            )
            return [secret.to_bucket_secret_out() for secret in db_secrets]

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
                for field in ("access_key", "secret_key", "session_token"):
                    value = getattr(secret, field)
                    if value is not None:
                        update_data[field] = encrypt(value)
            elif db_secret.type == BucketType.AZURE:
                await self._prepare_azure_update(session, db_secret, update_data)
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
            if db_secret.orbits:
                raise DatabaseConstraintError()
            await session.delete(db_secret)
            try:
                await session.commit()
            except IntegrityError as e:
                raise DatabaseConstraintError() from e
            return True
