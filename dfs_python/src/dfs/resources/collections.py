from typing import List

from .._resource import APIResource
from .._types import Collection, CollectionType


class CollectionResource(APIResource):
    async def list(self, organization_id: int, orbit_id: int) -> list[Collection]:
        response = await self._get(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections"
        )
        if response is None:
            return []

        return [Collection(**collection) for collection in response]

    async def create(
        self,
        organization_id: int,
        orbit_id: int,
        description: str,
        name: str,
        collection_type: CollectionType,
        tags: List[str] | None = None,
    ):
        response = await self._post(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections",
            json={
                "description": description,
                "name": name,
                "collection_type": collection_type,
                "tags": tags,
            },
        )
        return Collection(**response)

    async def update(
        self,
        organization_id: int,
        orbit_id: int,
        collection_id: int,
        description: str | None = None,
        name: str | None = None,
        tags: List[str] | None = None,
    ):
        response = await self._patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}",
            json=self._filter_none(
                {
                    "description": description,
                    "name": name,
                    "tags": tags,
                }
            ),
        )
        return Collection(**response)

    async def delete(self, organization_id: int, orbit_id: int, collection_id: int):
        return await self._delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}/collections/{collection_id}"
        )
