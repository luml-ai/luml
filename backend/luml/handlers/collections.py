from uuid import UUID

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import CollectionDeleteError, NotFoundError
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.collections import (
    Collection,
    CollectionCreate,
    CollectionCreateIn,
    CollectionDetails,
    CollectionsList,
    CollectionSortBy,
    CollectionTypeFilter,
    CollectionUpdate,
    CollectionUpdateIn,
)
from luml.schemas.general import PaginationParams, SortOrder
from luml.schemas.permissions import Action, Resource
from luml.utils.pagination import decode_cursor, get_cursor


class CollectionHandler:
    __repository = CollectionRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()
    __artifacts_repository = ArtifactRepository(engine)

    async def create_collection(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection: CollectionCreateIn,
    ) -> Collection:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.COLLECTION,
            Action.CREATE,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        collection_create = CollectionCreate(
            **collection.model_dump(), orbit_id=orbit_id
        )
        return await self.__repository.create_collection(collection_create)

    async def get_orbit_collections(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        cursor_str: str | None = None,
        limit: int = 100,
        sort_by: CollectionSortBy = CollectionSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        collection_type: CollectionTypeFilter | None = None,
    ) -> CollectionsList:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.COLLECTION,
            Action.LIST,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")

        cursor = decode_cursor(cursor_str)

        use_cursor = cursor if cursor and cursor.sort_by == sort_by.value else None

        pagination = PaginationParams(
            cursor=use_cursor,
            sort_by=str(sort_by.value),
            order=order,
            limit=limit,
        )

        items = await self.__repository.get_orbit_collections(
            orbit_id=orbit_id,
            pagination=pagination,
            search=search,
            collection_type=collection_type,
        )

        return CollectionsList(
            items=items[:limit],
            cursor=get_cursor(items, limit, str(sort_by.value)),
        )

    async def get_collection_details(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
    ) -> CollectionDetails:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.COLLECTION,
            Action.READ,
            orbit_id,
        )

        collection = await self.__repository.get_collection(collection_id)

        if not collection or collection.orbit_id != orbit_id:
            raise NotFoundError("Collection not found")

        extra_values = (
            await self.__artifacts_repository.get_collection_artifacts_extra_values(
                collection_id
            )
        )
        tags = await self.__artifacts_repository.get_collection_artifacts_tags(
            collection_id
        )
        return CollectionDetails(
            **collection.model_dump(),
            artifacts_extra_values=extra_values,
            artifacts_tags=tags,
        )

    async def update_collection(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        collection: CollectionUpdateIn,
    ) -> Collection:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.COLLECTION,
            Action.UPDATE,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        updated = await self.__repository.update_collection(
            collection_id,
            CollectionUpdate(
                id=collection_id,
                description=collection.description,
                name=collection.name,
                tags=collection.tags,
            ),
        )
        if not updated:
            raise NotFoundError("Collection not found")
        return updated

    async def delete_collection(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.COLLECTION,
            Action.DELETE,
            orbit_id,
        )
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise NotFoundError("Orbit not found")
        collection = await self.__repository.get_collection(collection_id)
        if not collection:
            raise NotFoundError("Collection not found")
        artifacts_count = (
            await self.__artifacts_repository.get_collection_artifacts_count(
                collection_id
            )
        )
        if artifacts_count:
            raise CollectionDeleteError("Collection has artifacts and cant be deleted")
        await self.__repository.delete_collection(collection_id)
