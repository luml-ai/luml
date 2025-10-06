from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from dataforce_studio.infra.exceptions import DatabaseConstraintError
from dataforce_studio.models import ModelArtifactOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.base import ShortUUID
from dataforce_studio.schemas.model_artifacts import (
    ModelArtifact,
    ModelArtifactCreate,
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
        self, model_artifact_id: ShortUUID, status: ModelArtifactStatus
    ) -> ModelArtifact | None:
        async with self._get_session() as session:
            db_model = await self.update_model_where(
                session,
                ModelArtifactOrm,
                ModelArtifactUpdate(id=model_artifact_id, status=status),
                ModelArtifactOrm.id == model_artifact_id.to_uuid(),
            )
            return db_model.to_model_artifact() if db_model else None

    async def delete_model_artifact(self, model_artifact_id: ShortUUID) -> None:
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

    async def get_collection_model_artifact(
        self, collection_id: ShortUUID
    ) -> list[ModelArtifact]:
        async with self._get_session() as session:
            result = await session.execute(
                select(ModelArtifactOrm).where(
                    ModelArtifactOrm.collection_id == collection_id.to_uuid()
                )
            )
            db_versions = result.scalars().all()
            return [v.to_model_artifact() for v in db_versions]

    async def get_model_artifact(
        self, model_artifact_id: ShortUUID
    ) -> ModelArtifact | None:
        async with self._get_session() as session:
            db_model = await self.get_model(
                session, ModelArtifactOrm, model_artifact_id
            )
            return db_model.to_model_artifact() if db_model else None

    async def update_model_artifact(
        self,
        model_artifact_id: ShortUUID,
        collection_id: ShortUUID,
        model_artifact: ModelArtifactUpdate,
    ) -> ModelArtifact | None:
        model_artifact.id = model_artifact_id
        async with self._get_session() as session:
            db_model = await self.update_model_where(
                session,
                ModelArtifactOrm,
                model_artifact,
                ModelArtifactOrm.id == model_artifact_id.to_uuid(),
                ModelArtifactOrm.collection_id == collection_id.to_uuid(),
            )
            return db_model.to_model_artifact() if db_model else None

    async def get_collection_model_artifacts_count(
        self, collection_id: ShortUUID
    ) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ModelArtifactOrm)
                .where(ModelArtifactOrm.collection_id == collection_id.to_uuid())
            )
            return result.scalar() or 0
