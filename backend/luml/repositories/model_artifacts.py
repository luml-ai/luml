from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from luml.infra.exceptions import DatabaseConstraintError
from luml.models import ModelArtifactOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.general import PaginationParams
from luml.schemas.model_artifacts import (
    ModelArtifact,
    ModelArtifactCreate,
    ModelArtifactDetails,
    ModelArtifactStatus,
    ModelArtifactUpdate,
)


class ModelArtifactRepository(RepositoryBase, CrudMixin):
    async def create_model_artifact(
        self, model_artifact: ModelArtifactCreate
    ) -> ModelArtifact:
        async with self._get_session() as session:
            db_model = await self.create_model(
                session, ModelArtifactOrm, model_artifact
            )
            return db_model.to_model_artifact()

    async def update_status(
        self, model_artifact_id: UUID, status: ModelArtifactStatus
    ) -> ModelArtifact | None:
        async with self._get_session() as session:
            db_model = await self.update_model_where(
                session,
                ModelArtifactOrm,
                ModelArtifactUpdate(id=model_artifact_id, status=status),
                ModelArtifactOrm.id == model_artifact_id,
            )
            return db_model.to_model_artifact() if db_model else None

    async def delete_model_artifact(self, model_artifact_id: UUID) -> None:
        try:
            async with self._get_session() as session:
                await self.delete_model(session, ModelArtifactOrm, model_artifact_id)
        except IntegrityError as error:
            error_mess = "Cannot delete model artifact."
            raise DatabaseConstraintError(
                error_mess + " It is used in deployments."
                if "deployments" in str(error)
                else error_mess
            ) from error

    async def get_collection_model_artifacts_metrics(
        self, collection_id: UUID
    ) -> list[str]:
        async with self._get_session() as session:
            metrics_query = select(
                func.jsonb_each(ModelArtifactOrm.metrics).scalar_table_valued("key")
            ).where(
                ModelArtifactOrm.collection_id == collection_id,
                ModelArtifactOrm.metrics.is_not(None),
                ModelArtifactOrm.metrics != {},
            )
            metrics_query_result = await session.execute(metrics_query)

            return sorted({row[0] for row in metrics_query_result.unique().all()})

    async def get_collection_model_artifacts_tags(
        self, collection_id: UUID
    ) -> list[str]:
        async with self._get_session() as session:
            tags_query = select(ModelArtifactOrm.tags).where(
                ModelArtifactOrm.collection_id == collection_id,
                ModelArtifactOrm.tags.is_not(None),
            )
            tags_query_result = await session.execute(tags_query)
            return self.collect_unique_values_from_array_column(tags_query_result.all())

    async def get_collection_model_artifacts(
        self,
        collection_id: UUID,
        pagination: PaginationParams,
    ) -> list[ModelArtifact]:
        async with self._get_session() as session:
            db_models = await self.get_models_with_pagination(
                session,
                ModelArtifactOrm,
                ModelArtifactOrm.collection_id == collection_id,
                pagination=pagination,
            )
            return [model.to_model_artifact() for model in db_models]

    async def get_model_artifact(self, model_artifact_id: UUID) -> ModelArtifact | None:
        async with self._get_session() as session:
            db_model = await self.get_model(
                session, ModelArtifactOrm, model_artifact_id
            )
            return db_model.to_model_artifact() if db_model else None

    async def get_model_artifact_details(
        self, model_artifact_id: UUID
    ) -> ModelArtifactDetails | None:
        async with self._get_session() as session:
            db_model = await self.get_model(
                session,
                ModelArtifactOrm,
                model_artifact_id,
                options=[selectinload(ModelArtifactOrm.deployments)],
            )
            return db_model.to_model_artifact_details() if db_model else None

    async def update_model_artifact(
        self,
        model_artifact_id: UUID,
        collection_id: UUID,
        model_artifact: ModelArtifactUpdate,
    ) -> ModelArtifact | None:
        model_artifact.id = model_artifact_id
        async with self._get_session() as session:
            db_model = await self.update_model_where(
                session,
                ModelArtifactOrm,
                model_artifact,
                ModelArtifactOrm.id == model_artifact_id,
                ModelArtifactOrm.collection_id == collection_id,
            )
            return db_model.to_model_artifact() if db_model else None

    async def get_collection_model_artifacts_count(self, collection_id: UUID) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ModelArtifactOrm)
                .where(ModelArtifactOrm.collection_id == collection_id)
            )
            return result.scalar() or 0
