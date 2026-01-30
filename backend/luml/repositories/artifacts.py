from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from luml.infra.exceptions import DatabaseConstraintError
from luml.models import ArtifactOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactDetails,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
)
from luml.schemas.general import PaginationParams


class ArtifactRepository(RepositoryBase, CrudMixin):
    async def create_artifact(self, artifact: ArtifactCreate) -> Artifact:
        async with self._get_session() as session:
            db_artifact = await self.create_model(session, ArtifactOrm, artifact)
            return db_artifact.to_artifact()

    async def update_status(
        self, artifact_id: UUID, status: ArtifactStatus
    ) -> Artifact | None:
        async with self._get_session() as session:
            db_artifact = await self.update_model_where(
                session,
                ArtifactOrm,
                ArtifactUpdate(id=artifact_id, status=status),
                ArtifactOrm.id == artifact_id,
            )
            return db_artifact.to_artifact() if db_artifact else None

    async def delete_artifact(self, artifact_id: UUID) -> None:
        try:
            async with self._get_session() as session:
                await self.delete_model(session, ArtifactOrm, artifact_id)
        except IntegrityError as error:
            error_mess = "Cannot delete artifact."
            raise DatabaseConstraintError(
                error_mess + " It is used in deployments."
                if "deployments" in str(error)
                else error_mess
            ) from error

    async def get_collection_artifacts_extra_values(
        self, collection_id: UUID
    ) -> list[str]:
        async with self._get_session() as session:
            query = select(
                func.jsonb_each(ArtifactOrm.extra_values).scalar_table_valued("key")
            ).where(
                ArtifactOrm.collection_id == collection_id,
                ArtifactOrm.extra_values.is_not(None),
                ArtifactOrm.extra_values != {},
            )
            result = await session.execute(query)

            return sorted({row[0] for row in result.unique().all()})

    async def get_collection_artifacts_tags(self, collection_id: UUID) -> list[str]:
        async with self._get_session() as session:
            tags_query = select(ArtifactOrm.tags).where(
                ArtifactOrm.collection_id == collection_id,
                ArtifactOrm.tags.is_not(None),
            )
            tags_query_result = await session.execute(tags_query)
            return self.collect_unique_values_from_array_column(tags_query_result.all())

    async def get_collection_artifacts(
        self,
        collection_id: UUID,
        pagination: PaginationParams,
        artifact_type: ArtifactType | None = None,
    ) -> list[Artifact]:
        async with self._get_session() as session:
            conditions = [ArtifactOrm.collection_id == collection_id]
            if artifact_type is not None:
                conditions.append(ArtifactOrm.type == artifact_type.value)

            db_artifacts = await self.get_models_with_pagination(
                session,
                ArtifactOrm,
                *conditions,
                pagination=pagination,
            )
            return [artifact.to_artifact() for artifact in db_artifacts]

    async def get_artifact(self, artifact_id: UUID) -> Artifact | None:
        async with self._get_session() as session:
            db_artifact = await self.get_model(session, ArtifactOrm, artifact_id)
            return db_artifact.to_artifact() if db_artifact else None

    async def get_artifact_details(self, artifact_id: UUID) -> ArtifactDetails | None:
        async with self._get_session() as session:
            db_artifact = await self.get_model(
                session,
                ArtifactOrm,
                artifact_id,
                options=[selectinload(ArtifactOrm.deployments)],
            )
            return db_artifact.to_artifact_details() if db_artifact else None

    async def update_artifact(
        self,
        artifact_id: UUID,
        collection_id: UUID,
        artifact: ArtifactUpdate,
    ) -> Artifact | None:
        artifact.id = artifact_id
        async with self._get_session() as session:
            db_artifact = await self.update_model_where(
                session,
                ArtifactOrm,
                artifact,
                ArtifactOrm.id == artifact_id,
                ArtifactOrm.collection_id == collection_id,
            )
            return db_artifact.to_artifact() if db_artifact else None

    async def get_collection_artifacts_count(self, collection_id: UUID) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ArtifactOrm)
                .where(ArtifactOrm.collection_id == collection_id)
            )
            return result.scalar() or 0
