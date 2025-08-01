from dataforce_studio.models import CollectionOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.model_artifacts import (
    Collection,
    CollectionCreate,
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

    async def get_collection(self, collection_id: int) -> Collection | None:
        async with self._get_session() as session:
            db_collection = await self.get_model(
                session,
                CollectionOrm,
                collection_id,
            )
            return db_collection.to_collection() if db_collection else None

    async def get_orbit_collections(self, orbit_id: int) -> list[Collection]:
        async with self._get_session() as session:
            db_collections = await self.get_models_where(
                session, CollectionOrm, CollectionOrm.orbit_id == orbit_id
            )
            return [mc.to_collection() for mc in db_collections]

    async def update_collection(
        self, collection_id: int, collection: CollectionUpdate
    ) -> Collection | None:
        collection.id = collection_id
        async with self._get_session() as session:
            db_collection = await self.update_model(
                session=session, orm_class=CollectionOrm, data=collection
            )
            return db_collection.to_collection() if db_collection else None

    async def delete_collection(self, collection_id: int) -> None:
        async with self._get_session() as session:
            await self.delete_model(session, CollectionOrm, collection_id)
