from operator import gt, lt
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from luml.infra.exceptions import DatabaseConstraintError
from luml.models import ModelArtifactOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.model_artifacts import (
    ModelArtifact,
    ModelArtifactCreate,
    ModelArtifactDetails,
    ModelArtifactStatus,
    ModelArtifactUpdate,
)


class ModelArtifactRepository(RepositoryBase, CrudMixin):
    _SORT_COLUMNS = {
        "created_at": ModelArtifactOrm.created_at,
        "model_name": ModelArtifactOrm.model_name,
        "file_name": ModelArtifactOrm.file_name,
        "size": ModelArtifactOrm.size,
    }

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

    async def get_collection_model_artifacts(
        self,
        collection_id: UUID,
        limit: int,
        cursor: UUID | None = None,
        sort_by: str | None = None,
        order: str | None = "desc",
    ) -> list[ModelArtifact]:
        async with self._get_session() as session:
            query = select(ModelArtifactOrm).where(
                ModelArtifactOrm.collection_id == collection_id
            )

            if cursor and (
                cursor_record := await session.get(ModelArtifactOrm, cursor)
            ):
                op = lt if order == "desc" else gt

                if sort_by and sort_by in self._SORT_COLUMNS:
                    sort_column = self._SORT_COLUMNS[sort_by]
                    cursor_value = getattr(cursor_record, sort_by)

                    query = query.where(
                        op(sort_column, cursor_value)
                        | (
                            (sort_column == cursor_value)
                            & op(ModelArtifactOrm.id, cursor)
                        )
                    )
                else:
                    query = query.where(op(ModelArtifactOrm.id, cursor))

            sort_func = desc if order == "desc" else asc

            if not sort_by or sort_by == "created_at":
                query = query.order_by(sort_func(ModelArtifactOrm.id))
            else:
                sort_column = self._SORT_COLUMNS.get(
                    sort_by, ModelArtifactOrm.created_at
                )
                query = query.order_by(
                    sort_func(sort_column),
                    sort_func(ModelArtifactOrm.id),
                )

            query = query.limit(limit)

            result = await session.execute(query)
            return [model.to_model_artifact() for model in result.scalars().all()]

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
