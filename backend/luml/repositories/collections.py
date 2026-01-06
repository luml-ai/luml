from uuid import UUID

from sqlalchemy import String, cast, or_

from luml.models import CollectionOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.general import CursorType, SortOrder
from luml.schemas.model_artifacts import (
    Collection,
    CollectionCreate,
    CollectionSortBy,
    CollectionUpdate,
)


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

    async def get_orbit_collections(
        self,
        orbit_id: UUID,
        limit: int,
        cursor_id: UUID | None = None,
        cursor_value: CursorType | None = None,
        sort_by: CollectionSortBy = CollectionSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> list[Collection]:
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

            db_collections = await self.get_models_with_pagination(
                session,
                CollectionOrm,
                *conditions,
                cursor_id=cursor_id,
                cursor_value=cursor_value,
                sort_by=sort_by,
                order=order,
                limit=limit,
            )
            return [mc.to_collection() for mc in db_collections]

    async def update_collection(
        self, collection_id: UUID, collection: CollectionUpdate
    ) -> Collection | None:
        collection.id = collection_id
        async with self._get_session() as session:
            db_collection = await self.update_model(
                session=session, orm_class=CollectionOrm, data=collection
            )
            return db_collection.to_collection() if db_collection else None

    async def delete_collection(self, collection_id: UUID) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, CollectionOrm, collection_id)
