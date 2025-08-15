import builtins
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import Collection, CollectionType
from .._utils import find_by_name
from ._validators import validate_collection

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class CollectionResourceBase(ABC):
    @abstractmethod
    def get(
        self, collection_value: str
    ) -> Collection | None | Coroutine[Any, Any, Collection | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, name: str
    ) -> Collection | None | Coroutine[Any, Any, Collection | None]:
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> list[Collection] | Coroutine[Any, Any, list[Collection]]:
        raise NotImplementedError()

    @abstractmethod
    def create(
        self,
        description: str,
        name: str,
        collection_type: CollectionType,
        tags: builtins.list[str] | None = None,
    ) -> Collection | Coroutine[Any, Any, Collection]:
        raise NotImplementedError()

    @abstractmethod
    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: int,
    ) -> Collection | Coroutine[Any, Any, Collection]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, collection_id: int) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class CollectionResource(CollectionResourceBase):
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, collection_value: str) -> Collection | None:
        return self._get_by_name(collection_value)

    def _get_by_name(self, name: str) -> Collection | None:
        return find_by_name(self.list(), name)

    def list(self) -> list[Collection]:
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections"
        )
        if response is None:
            return []

        return [Collection.model_validate(collection) for collection in response]

    def create(
        self,
        description: str,
        name: str,
        collection_type: CollectionType,
        tags: builtins.list[str] | None = None,
    ) -> Collection:
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections",
            json={
                "description": description,
                "name": name,
                "collection_type": collection_type,
                "tags": tags,
            },
        )
        return Collection.model_validate(response)

    @validate_collection
    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: int,
    ) -> Collection:
        response = self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}",
            json=self._client.filter_none(
                {
                    "description": description,
                    "name": name,
                    "tags": tags,
                }
            ),
        )
        return Collection.model_validate(response)

    @validate_collection
    def delete(self, collection_id: int) -> None:
        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}"
        )


class AsyncCollectionResource(CollectionResourceBase):
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, collection_value: str) -> Collection | None:
        return await self._get_by_name(collection_value)

    async def _get_by_name(self, name: str) -> Collection | None:
        return find_by_name(await self.list(), name)

    async def list(self) -> list[Collection]:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections"
        )
        if response is None:
            return []

        return [Collection.model_validate(collection) for collection in response]

    async def create(
        self,
        description: str,
        name: str,
        collection_type: CollectionType,
        tags: builtins.list[str] | None = None,
    ) -> Collection:
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections",
            json={
                "description": description,
                "name": name,
                "collection_type": collection_type,
                "tags": tags,
            },
        )
        return Collection.model_validate(response)

    @validate_collection
    async def update(
        self,
        name: str | None = None,
        description: str | None = None,
        tags: builtins.list[str] | None = None,
        *,
        collection_id: int | None,
    ) -> Collection:
        response = await self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}",
            json=self._client.filter_none(
                {
                    "description": description,
                    "name": name,
                    "tags": tags,
                }
            ),
        )
        return Collection.model_validate(response)

    @validate_collection
    async def delete(self, collection_id: int | None) -> None:
        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}"
        )
