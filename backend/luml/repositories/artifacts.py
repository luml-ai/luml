from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from luml.infra.exceptions import (
    ArtifactDeployedError,
    ArtifactTrackedError,
    CollectionNotFoundError,
    DatabaseConstraintError,
    InvalidSortingError,
)
from luml.models import (
    ArtifactOrm,
    CollectionOrm,
    DeploymentOrm,
    OrbitOrm,
    TrackArtifactOrm,
)
from luml.repositories.base import (
    CrudMixin,
    RepositoryBase,
    is_foreign_key_violation,
)
from luml.repositories.limits import OrganizationResource, reserve_organization_slot
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactDetails,
    ArtifactListed,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
)
from luml.schemas.deployment import DeploymentStatus
from luml.schemas.general import Cursor, PaginationParams


class ArtifactRepository(RepositoryBase, CrudMixin):
    async def create_artifact(self, artifact: ArtifactCreate) -> Artifact:
        async with self._get_session() as session:
            organization_id = await session.scalar(
                select(OrbitOrm.organization_id)
                .join(CollectionOrm, CollectionOrm.orbit_id == OrbitOrm.id)
                .where(CollectionOrm.id == artifact.collection_id)
            )
            if organization_id is None:
                raise CollectionNotFoundError()
            await reserve_organization_slot(
                session, organization_id, OrganizationResource.ARTIFACTS
            )
            try:
                db_artifact = await self.create_model(session, ArtifactOrm, artifact)
            except IntegrityError as error:
                if is_foreign_key_violation(error):
                    raise CollectionNotFoundError() from error
                raise DatabaseConstraintError("Cannot create artifact.") from error
            return db_artifact.to_artifact()

    async def request_deletion(
        self, artifact_id: UUID, collection_id: UUID
    ) -> Artifact | None:
        """Move the artifact to ``pending_deletion``, or refuse.

        The row is locked while deployments and track links are checked, so a
        deployment created concurrently is either seen here or waits and then
        finds the artifact already in ``pending_deletion``. Raises
        ``ArtifactDeployedError`` / ``ArtifactTrackedError`` (409) when the
        artifact is referenced; returns ``None`` when it does not exist in the
        collection.
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(ArtifactOrm)
                .where(
                    ArtifactOrm.id == artifact_id,
                    ArtifactOrm.collection_id == collection_id,
                )
                .options(
                    noload(ArtifactOrm.collection),
                    noload(ArtifactOrm.deployments),
                )
                .with_for_update()
            )
            artifact = result.scalar_one_or_none()
            if artifact is None:
                return None

            deployments = await session.scalar(
                select(func.count())
                .select_from(DeploymentOrm)
                .where(DeploymentOrm.artifact_id == artifact_id)
            )
            if deployments:
                raise ArtifactDeployedError()

            track_links = await session.scalar(
                select(func.count())
                .select_from(TrackArtifactOrm)
                .where(TrackArtifactOrm.artifact_id == artifact_id)
            )
            if track_links:
                raise ArtifactTrackedError()

            artifact.status = ArtifactStatus.PENDING_DELETION.value
            record = artifact.to_artifact()
            await session.commit()
            return record

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

    async def delete_artifact(
        self, artifact_id: UUID, session: AsyncSession | None = None
    ) -> None:
        try:
            if session is not None:
                artifact = await session.get(ArtifactOrm, artifact_id)
                if artifact is not None:
                    await session.delete(artifact)
                    await session.flush()
                return
            async with self._get_session() as owned_session:
                await self.delete_model(owned_session, ArtifactOrm, artifact_id)
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

    async def get_batch_collection_artifacts_extra_values(
        self, collection_ids: list[UUID]
    ) -> list[str]:
        async with self._get_session() as session:
            query = select(
                func.jsonb_each(ArtifactOrm.extra_values).scalar_table_valued("key")
            ).where(
                ArtifactOrm.collection_id.in_(collection_ids),
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

    async def _is_extra_values_sort(
        self, collection_ids: list[UUID], sort_by: str
    ) -> bool:
        if sort_by == "extra_values":
            raise InvalidSortingError("Cannot sort by 'metrics'. Pass a metric key")

        if hasattr(ArtifactOrm, sort_by):
            return False

        metrics = await self.get_batch_collection_artifacts_extra_values(collection_ids)

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
        orbit_id: UUID,
        pagination: PaginationParams,
        collection_ids: list[UUID] | None = None,
        artifact_types: list[ArtifactType] | None = None,
        search: str | None = None,
        excluded_tracks: list[UUID] | None = None,
    ) -> tuple[list[ArtifactListed], Cursor | None]:
        async with self._get_session() as session:
            sort_by = pagination.sort_by
            is_extra_values = False

            if collection_ids and len(collection_ids) > 0:
                is_extra_values = await self._is_extra_values_sort(
                    collection_ids, sort_by
                )

                if is_extra_values:
                    pagination.extra_sort_field = sort_by
                    pagination.sort_by = "extra_values"

            conditions: list[Any] = [
                ArtifactOrm.collection_id.in_(
                    select(CollectionOrm.id).where(CollectionOrm.orbit_id == orbit_id)
                ),
            ]

            if artifact_types:
                conditions.append(
                    or_(*[ArtifactOrm.type == t.value for t in artifact_types])
                )

            if collection_ids:
                conditions.append(ArtifactOrm.collection_id.in_(collection_ids))

            if excluded_tracks:
                conditions.append(
                    ArtifactOrm.id.not_in(
                        select(TrackArtifactOrm.artifact_id).where(
                            TrackArtifactOrm.track_id.in_(excluded_tracks)
                        )
                    )
                )

            if search:
                conditions.append(ArtifactOrm.name.ilike(f"%{search}%"))

            result = await self.get_models_with_pagination(
                session,
                ArtifactOrm,
                *conditions,
                pagination=pagination,
                options=[
                    selectinload(ArtifactOrm.collection).load_only(
                        CollectionOrm.id,
                        CollectionOrm.name,
                    ),
                    selectinload(
                        ArtifactOrm.deployments.and_(
                            DeploymentOrm.status == DeploymentStatus.ACTIVE.value
                        )
                    ).load_only(
                        DeploymentOrm.id,
                        DeploymentOrm.name,
                        DeploymentOrm.status,
                        DeploymentOrm.orbit_id,
                        DeploymentOrm.artifact_id,
                    ),
                ],
            )
            db_models = result.items

            cursor = (
                None
                if not result.has_more
                else self._get_cursor_from_record(
                    db_models[-1], pagination, is_extra_values
                )
            )

            artifacts = [
                orm_artifact.to_listed_artifact() for orm_artifact in db_models
            ]

            return artifacts, cursor

    async def get_artifact(self, artifact_id: UUID) -> Artifact | None:
        async with self._get_session() as session:
            db_artifact = await self.get_model(session, ArtifactOrm, artifact_id)
            return db_artifact.to_artifact() if db_artifact else None

    async def get_artifacts_by_ids_in_orbit(
        self,
        orbit_id: UUID,
        artifact_ids: list[UUID],
        session: AsyncSession | None = None,
    ) -> list[ArtifactListed]:
        if not artifact_ids:
            return []
        if session is None:
            async with self._get_session() as owned_session:
                return await self.get_artifacts_by_ids_in_orbit(
                    orbit_id, artifact_ids, owned_session
                )

        result = await session.scalars(
            select(ArtifactOrm)
            .join(CollectionOrm, ArtifactOrm.collection_id == CollectionOrm.id)
            .where(
                CollectionOrm.orbit_id == orbit_id,
                ArtifactOrm.id.in_(artifact_ids),
            )
            .options(
                selectinload(ArtifactOrm.collection).load_only(
                    CollectionOrm.id,
                    CollectionOrm.name,
                ),
                selectinload(
                    ArtifactOrm.deployments.and_(
                        DeploymentOrm.status == DeploymentStatus.ACTIVE.value
                    )
                ).load_only(
                    DeploymentOrm.id,
                    DeploymentOrm.name,
                    DeploymentOrm.status,
                    DeploymentOrm.orbit_id,
                    DeploymentOrm.artifact_id,
                ),
            )
        )
        return [artifact.to_listed_artifact() for artifact in result.all()]

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
