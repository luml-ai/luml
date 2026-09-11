from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from luml.infra.exceptions import DatabaseConstraintError, InvalidSortingError
from luml.models import (
    ArtifactOrm,
    CollectionOrm,
    DeploymentOrm,
    TrackArtifactOrm,
    TrackOrm,
)
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactDeleteDeployment,
    ArtifactDeleteTrack,
    ArtifactDetails,
    ArtifactListed,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
)
from luml.schemas.deployment import DeploymentStatus
from luml.schemas.general import Cursor, PaginationParams


@dataclass(slots=True)
class ArtifactDeletionRecord:
    artifact: Artifact
    deployments: list[ArtifactDeleteDeployment]
    tracks: list[ArtifactDeleteTrack]


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

    async def delete_artifact(
        self, artifact_id: UUID, session: AsyncSession | None = None
    ) -> None:
        """Delete the artifact row.

        With a caller ``session`` the delete is only flushed: it is committed
        or rolled back together with the rest of the caller's transaction.
        """
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

    async def _load_deletion_records(
        self,
        session: AsyncSession,
        collection_id: UUID,
        artifact_ids: list[UUID],
        *,
        lock: bool,
    ) -> tuple[
        list[ArtifactOrm],
        dict[UUID, list[ArtifactDeleteDeployment]],
        dict[UUID, list[ArtifactDeleteTrack]],
    ]:
        artifact_query = (
            select(ArtifactOrm)
            .where(
                ArtifactOrm.collection_id == collection_id,
                ArtifactOrm.id.in_(artifact_ids),
            )
            .options(
                noload(ArtifactOrm.collection),
                noload(ArtifactOrm.deployments),
            )
        )
        if lock:
            artifact_query = artifact_query.with_for_update()

        artifact_result = await session.execute(artifact_query)
        artifacts_by_id = {
            artifact.id: artifact for artifact in artifact_result.scalars().all()
        }
        ordered_artifacts = [
            artifacts_by_id[artifact_id]
            for artifact_id in dict.fromkeys(artifact_ids)
            if artifact_id in artifacts_by_id
        ]
        found_ids = list(artifacts_by_id)

        deployment_result = await session.execute(
            select(
                DeploymentOrm.artifact_id,
                DeploymentOrm.id,
                DeploymentOrm.name,
                DeploymentOrm.status,
            ).where(DeploymentOrm.artifact_id.in_(found_ids))
        )
        deployments: defaultdict[UUID, list[ArtifactDeleteDeployment]] = defaultdict(
            list
        )
        for artifact_id, deployment_id, name, deployment_status in deployment_result:
            deployments[artifact_id].append(
                ArtifactDeleteDeployment(
                    id=deployment_id,
                    name=name,
                    status=DeploymentStatus(deployment_status),
                )
            )

        track_result = await session.execute(
            select(
                TrackArtifactOrm.artifact_id,
                TrackOrm.id,
                TrackOrm.name,
            )
            .join(TrackOrm, TrackOrm.id == TrackArtifactOrm.track_id)
            .where(TrackArtifactOrm.artifact_id.in_(found_ids))
        )
        tracks: defaultdict[UUID, list[ArtifactDeleteTrack]] = defaultdict(list)
        for artifact_id, track_id, name in track_result:
            tracks[artifact_id].append(ArtifactDeleteTrack(id=track_id, name=name))

        return ordered_artifacts, dict(deployments), dict(tracks)

    @staticmethod
    def _to_deletion_records(
        artifacts: list[ArtifactOrm],
        deployments: dict[UUID, list[ArtifactDeleteDeployment]],
        tracks: dict[UUID, list[ArtifactDeleteTrack]],
    ) -> list[ArtifactDeletionRecord]:
        return [
            ArtifactDeletionRecord(
                artifact=artifact.to_artifact(),
                deployments=deployments.get(artifact.id, []),
                tracks=tracks.get(artifact.id, []),
            )
            for artifact in artifacts
        ]

    async def request_batch_deletion(
        self, collection_id: UUID, artifact_ids: list[UUID]
    ) -> list[ArtifactDeletionRecord]:
        async with self._get_session() as session:
            artifacts, deployments, tracks = await self._load_deletion_records(
                session,
                collection_id,
                artifact_ids,
                lock=True,
            )
            for artifact in artifacts:
                if not deployments.get(artifact.id) and not tracks.get(artifact.id):
                    artifact.status = ArtifactStatus.PENDING_DELETION.value

            records = self._to_deletion_records(artifacts, deployments, tracks)
            await session.commit()
            return records

    async def get_batch_deletion_records(
        self, collection_id: UUID, artifact_ids: list[UUID]
    ) -> list[ArtifactDeletionRecord]:
        async with self._get_session() as session:
            artifacts, deployments, tracks = await self._load_deletion_records(
                session,
                collection_id,
                artifact_ids,
                lock=False,
            )
            return self._to_deletion_records(artifacts, deployments, tracks)

    async def mark_deletion_failed(
        self, collection_id: UUID, artifact_ids: list[UUID]
    ) -> None:
        if not artifact_ids:
            return

        async with self._get_session() as session:
            await session.execute(
                update(ArtifactOrm)
                .where(
                    ArtifactOrm.collection_id == collection_id,
                    ArtifactOrm.id.in_(artifact_ids),
                )
                .values(status=ArtifactStatus.DELETION_FAILED.value)
            )
            await session.commit()

    async def delete_artifact_record(
        self, artifact_id: UUID, collection_id: UUID
    ) -> bool:
        try:
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
                    return False

                await session.delete(artifact)
                await session.commit()
                return True
        except IntegrityError as error:
            raise DatabaseConstraintError(
                "Cannot delete artifact because it is referenced."
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
