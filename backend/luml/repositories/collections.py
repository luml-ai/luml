from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select

from luml.infra.exceptions import CollectionDeleteError
from luml.models import ArtifactOrm, CollectionOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.collections import (
    Collection,
    CollectionCreate,
    CollectionTypeFilter,
    CollectionUpdate,
)
from luml.schemas.general import Cursor, PaginationParams


class CollectionRepository(RepositoryBase, CrudMixin):
    async def create_collection(self, collection: CollectionCreate) -> Collection:
        async with self._get_session() as session:
            db_collection = await self.create_model(
                session,
                CollectionOrm,
                collection,
            )
            return db_collection.to_collection()

    async def get_collection(self, collection_id: UUID) -> Collection | None:
        async with self._get_session() as session:
            db_collection = await self.get_model(
                session,
                CollectionOrm,
                collection_id,
            )
            return db_collection.to_collection() if db_collection else None

    async def get_collections_by_ids(
        self, collection_ids: list[UUID], orbit_id: UUID | None = None
    ) -> list[Collection]:
        async with self._get_session() as session:
            conditions: list[Any] = [CollectionOrm.id.in_(collection_ids)]
            if orbit_id is not None:
                conditions.append(CollectionOrm.orbit_id == orbit_id)
            rows = await self.get_models_where(session, CollectionOrm, *conditions)
            return [r.to_collection() for r in rows]

    async def get_orbit_collections(
        self,
        orbit_id: UUID,
        pagination: PaginationParams,
        search: str | None = None,
        types: list[CollectionTypeFilter] | None = None,
        tags: list[str] | None = None,
    ) -> tuple[list[Collection], Cursor | None]:
        async with self._get_session() as session:
            conditions = [CollectionOrm.orbit_id == orbit_id]

            if search:
                search_pattern = f"%{search}%"
                conditions.append(
                    or_(
                        CollectionOrm.name.ilike(search_pattern),
                        cast(CollectionOrm.tags, String).ilike(search_pattern),
                    )
                )

            if types:
                conditions.append(or_(*[CollectionOrm.type == t.value for t in types]))

            if tags:
                conditions.append(
                    or_(*[CollectionOrm.tags.contains([tag]) for tag in tags])
                )

            result = await self.get_models_with_pagination(
                session,
                CollectionOrm,
                *conditions,
                pagination=pagination,
            )
            db_collections = result.items
            cursor = (
                None
                if not result.has_more
                else self._get_cursor_from_record(db_collections[-1], pagination)
            )
            return [mc.to_collection() for mc in db_collections], cursor

    async def get_orbit_collections_tags(self, orbit_id: UUID) -> list[str]:
        async with self._get_session() as session:
            tags_query = select(CollectionOrm.tags).where(
                CollectionOrm.orbit_id == orbit_id,
                CollectionOrm.tags.is_not(None),
            )
            tags_query_result = await session.execute(tags_query)
            return self.collect_unique_values_from_array_column(tags_query_result.all())

    async def update_collection(
        self, collection_id: UUID, orbit_id: UUID, collection: CollectionUpdate
    ) -> Collection | None:
        async with self._get_session() as session:
            db_collection = await self.update_model_where(
                session,
                CollectionOrm,
                collection,
                CollectionOrm.id == collection_id,
                CollectionOrm.orbit_id == orbit_id,
            )
            return db_collection.to_collection() if db_collection else None

    async def delete_collection(self, collection_id: UUID, orbit_id: UUID) -> bool:
        async with self._get_session() as session:
            result = await session.execute(
                select(CollectionOrm)
                .where(
                    CollectionOrm.id == collection_id,
                    CollectionOrm.orbit_id == orbit_id,
                )
                .with_for_update()
            )
            collection = result.scalar_one_or_none()
            if collection is None:
                return False

            artifacts = await session.scalar(
                select(func.count())
                .select_from(ArtifactOrm)
                .where(ArtifactOrm.collection_id == collection_id)
            )
            if artifacts:
                raise CollectionDeleteError(
                    "Collection has artifacts and cant be deleted"
                )

            await session.delete(collection)
            await session.commit()
            return True
