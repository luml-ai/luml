from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from luml.infra.exceptions import DatabaseConstraintError, InvalidSortingError
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
from luml.schemas.general import Cursor, PaginationParams


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

    async def _is_extra_values_sort(self, collection_id: UUID, sort_by: str) -> bool:
        if sort_by == "extra_values":
            raise InvalidSortingError("Cannot sort by 'metrics'. Pass a metric key")

        if hasattr(ArtifactOrm, sort_by):
            return False

        metrics = await self.get_collection_artifacts_extra_values(collection_id)

        if sort_by not in metrics:
            raise InvalidSortingError(f"Invalid sorting column: {sort_by}")
        return True

    @staticmethod
    def _get_cursor_from_record(  # type: ignore[override]
        cursor_rec: ArtifactOrm,
        pagination: PaginationParams,
        is_extra_value: bool = False,
    ) -> Cursor:
        if is_extra_value and pagination.extra_sort_field:
            value = cursor_rec.extra_values.get(pagination.extra_sort_field)
        else:
            value = getattr(cursor_rec, pagination.sort_by, None)
        return Cursor(
            id=cursor_rec.id,
            value=value,
            sort_by=pagination.sort_by,
            order=pagination.order,
            scope_id=pagination.scope_id,
        )

    async def get_collection_artifacts(
        self,
        collection_id: UUID,
        pagination: PaginationParams,
        artifact_types: list[ArtifactType] | None = None,
    ) -> tuple[list[Artifact], Cursor | None]:
        async with self._get_session() as session:
            sort_by = pagination.sort_by
            is_extra_values = await self._is_extra_values_sort(collection_id, sort_by)

            if is_extra_values:
                pagination.extra_sort_field = sort_by
                pagination.sort_by = "extra_values"

            conditions = [ArtifactOrm.collection_id == collection_id]
            if artifact_types:
                conditions.append(
                    or_(*[ArtifactOrm.type == t.value for t in artifact_types])
                )

            result = await self.get_models_with_pagination(
                session,
                ArtifactOrm,
                *conditions,
                pagination=pagination,
            )
            db_models = result.items

            cursor = (
                None
                if not result.has_more
                else self._get_cursor_from_record(
                    db_models[-1], pagination, is_extra_values
                )
            )

            return [artifact.to_artifact() for artifact in db_models], cursor

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
