import builtins
from typing import TYPE_CHECKING

from .._types import Collection, CollectionType
from .._utils import find_by_name
from ._validators import (
    validate_organization_orbit,
    validate_organization_orbit_collection,
)

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class CollectionResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    @validate_organization_orbit
    def get_by_name(
        self, organization_id: int | None, orbit_id: int | None, name: str
    ) -> Collection | None:
        return find_by_name(self.list(organization_id, orbit_id), name)

    @validate_organization_orbit
    def list(
        self, organization_id: int | None, orbit_id: int | None
    ) -> list[Collection]:
        response = self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections"
        )
        if response is None:
            return []

        return [Collection.model_validate(collection) for collection in response]

    @validate_organization_orbit
    def create(
        self,
        organization_id: int,
        orbit_id: int,
        description: str,
        name: str,
        collection_type: CollectionType,
        tags: builtins.list[str] | None = None,
    ) -> Collection:
        response = self._client.post(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
            json={
                "description": description,
                "name": name,
                "collection_type": collection_type,
                "tags": tags,
            },
        )
        return Collection.model_validate(response)

    @validate_organization_orbit_collection
    def update(
        self,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        description: str | None = None,
        name: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> Collection:
        response = self._client.patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
            json=self._client.filter_none(
                {
                    "description": description,
                    "name": name,
                    "tags": tags,
                }
            ),
        )
        return Collection.model_validate(response)

    @validate_organization_orbit_collection
    def delete(self, organization_id: int, orbit_id: int, collection_id: int) -> None:
        return self._client.delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}"
        )


class AsyncCollectionResource:
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    @validate_organization_orbit
    async def get_by_name(
        self, organization_id: int | None, orbit_id: int | None, name: str
    ) -> Collection | None:
        return find_by_name(await self.list(organization_id, orbit_id), name)

    @validate_organization_orbit
    async def list(
        self, organization_id: int | None, orbit_id: int | None
    ) -> list[Collection]:
        response = await self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections"
        )
        if response is None:
            return []

        return [Collection.model_validate(collection) for collection in response]

    @validate_organization_orbit
    async def create(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        description: str,
        name: str,
        collection_type: CollectionType,
        tags: builtins.list[str] | None = None,
    ) -> Collection:
        response = await self._client.post(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
            json={
                "description": description,
                "name": name,
                "collection_type": collection_type,
                "tags": tags,
            },
        )
        return Collection.model_validate(response)

    @validate_organization_orbit_collection
    async def update(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
        description: str | None = None,
        name: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> Collection:
        response = await self._client.patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
            json=self._client.filter_none(
                {
                    "description": description,
                    "name": name,
                    "tags": tags,
                }
            ),
        )
        return Collection.model_validate(response)

    @validate_organization_orbit_collection
    async def delete(
        self,
        organization_id: int | None,
        orbit_id: int | None,
        collection_id: int | None,
    ) -> None:
        return await self._client.delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}"
        )
