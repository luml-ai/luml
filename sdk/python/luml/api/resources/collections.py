import builtins
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import Collection, CollectionType, is_uuid
from .._utils import find_by_value
from ._validators import validate_collection

if TYPE_CHECKING:
    from .._client import AsyncLumlClient, LumlClient


class CollectionResourceBase(ABC):
    """Abstract Resource for managing Collections."""

    @abstractmethod
    def get(
        self, collection_value: str | None
    ) -> Collection | None | Coroutine[Any, Any, Collection | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, name: str
    ) -> Collection | None | Coroutine[Any, Any, Collection | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(
        self, secret_id: str
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
        collection_id: str,
    ) -> Collection | Coroutine[Any, Any, Collection]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, collection_id: str) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class CollectionResource(CollectionResourceBase):
    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def get(self, collection_value: str | None = None) -> Collection | None:
        """
        Get collection by id or name.

        Retrieves collection details by its id or name.
            Collection is related to default orbit.
        Search by name is case-sensitive and matches exact collection name.

        Args:
            collection_value: The exact id or name of the collection to retrieve.

        Returns:
            Collection object.

            Returns None if collection with the specified name or id is not found.

        Raises:
            MultipleResourcesFoundError: If there are several collections
                with that name / id.

        Example:
        ```python
        luml = LumlClient(api_key="luml_your_key")
        collection_by_name = luml.collections.get("My Collection")
        collection_by_id = luml.collections.get(
            "0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        ```

        Example response:
        ```python
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="My Collection",
            description="Dataset for ML models",
            collection_type='model',
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            tags=["ml", "training"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        if collection_value is None:
            if self._client.collection:
                return self._get_by_id(self._client.collection)
            return None
        if is_uuid(collection_value):
            return self._get_by_id(collection_value)
        return self._get_by_name(collection_value)

    def _get_by_name(self, name: str) -> Collection | None:
        return find_by_value(self.list(), name)

    def _get_by_id(self, collection_id: str) -> Collection | None:
        return find_by_value(
            self.list(), collection_id, lambda c: c.id == collection_id
        )

    def list(self) -> list[Collection]:
        """
        List all collections in the default orbit.

        Returns:
            List of Collection objects.

        Example:
        ```python
        luml = LumlClient(api_key="luml_your_key")
        collections = luml.collections.list()
        ```

        Example response:
        ```python
        [
            Collection(
                id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                name="My Collection",
                description="Dataset for ML models",
                collection_type='model',
                orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
                tags=["ml", "training"],
                created_at='2025-01-15T10:30:00.123456Z',
                updated_at=None
            )
        ]
        ```
        """
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
        """
        Create new collection in the default orbit.

        Args:
            description: Description of the collection.
            name: Name of the collection.
            collection_type: Type of collection: "model", "dataset".
            tags: Optional list of tags for organizing collections.

        Returns:
            Collection: Created collection object.

        Example:
        ```python
        luml = LumlClient(api_key="luml_your_key")
        collection = luml.collections.create(
            name="Training Dataset",
            description="Dataset for model training",
            collection_type=CollectionType.DATASET,
            tags=["ml", "training"]
        )
        ```

        Response object:
        ```python
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="Training Dataset",
            description="Dataset for model training",
            collection_type='model',
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            tags=["ml", "training"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
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
        collection_id: str | None = None,
    ) -> Collection:
        """
        Update collection by ID or use default collection if collection_id not provided.

        Updates the collection's data. Only provided parameters will be
        updated, others remain unchanged. If collection_id is None,
        the default collection from client will be used.

        Args:
            name: New name for the collection.
            description: New description for the collection.
            tags: New list of tags.
            collection_id: ID of the collection to update. If not provided,
                uses the default collection set in the client.

        Returns:
            Collection: Updated collection object.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de"
        )
        collection = luml.collections.update(
            collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="Updated Dataset",
            tags=["ml", "updated"]
        )

        luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
        collection = luml.collections.update(
            name="Updated Dataset",
            description="Updated description"
        )
        ```

        Response object:
        ```python
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            description="Updated description",
            name="Updated Dataset",
            collection_type='model',
            tags=["ml", "updated"],
            total_models=43,
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at='2025-01-15T14:22:30.987654Z'
        )
        ```
        """
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
    def delete(self, collection_id: str | None = None) -> None:
        """
        Delete collection by ID or use default collection if collection_id not provided.

        Permanently removes the collection and all its models.
            This action cannot be undone.
        If collection_id is None, the default collection from client will be used.

        Args:
            collection_id: ID of the collection to delete. If not provided,
                uses the default collection set in the client.

        Returns:
            None: No return value on successful deletion.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de"
        )
        # Delete specific collection by ID
        luml.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")

        # Set default collection
        luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
        # Delete default collection (collection_id will be autofilled)
        luml.collections.delete()
        ```

        Warning:
            This operation is irreversible. All models, datasets, and data
            within the collection will be permanently lost. Consider backing up
            important data before deletion.
        """
        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}"
        )


class AsyncCollectionResource(CollectionResourceBase):
    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    async def get(self, collection_value: str | None = None) -> Collection | None:
        """
        Get collection by id or name.

        Retrieves collection details by its id or name.
            Collection is related to default orbit.
        Search by name is case-sensitive and matches exact collection name.

        Args:
            collection_value: The exact id or name of the collection to retrieve.

        Returns:
            Collection object.

            Returns None if collection with the specified name or id is not found.

        Raises:
            MultipleResourcesFoundError: If there are several collections
                with that name / id.

        Example:
        ```python
        luml = AsyncLumlClient(api_key="luml_your_key")
        async def main():
            collection_by_name = await luml.collections.get(
                "My Collection"
            )
            collection_by_id = await luml.collections.get(
                "0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
        ```

        Example response:
        ```python
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="My Collection",
            description="Dataset for ML models",
            collection_type='model',
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            tags=["ml", "training"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
        if collection_value is None:
            if self._client.collection:
                return await self._get_by_id(self._client.collection)
            return None
        if is_uuid(collection_value):
            return await self._get_by_id(collection_value)
        return await self._get_by_name(collection_value)

    async def _get_by_name(self, name: str) -> Collection | None:
        return find_by_value(await self.list(), name)

    async def _get_by_id(self, collection_id: str) -> Collection | None:
        return find_by_value(
            await self.list(), collection_id, lambda c: c.id == collection_id
        )

    async def list(self) -> list[Collection]:
        """
        List all collections in the default orbit.

        Returns:
            List of Collection objects.

        Example:
        ```python
        luml = AsyncLumlClient(api_key="luml_your_key")
        async def main():
            collections = await luml.collections.list()
        ```

        Example response:
        ```python
        [
            Collection(
                id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                name="My Collection",
                description="Dataset for ML models",
                collection_type='model',
                orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
                tags=["ml", "training"],
                created_at='2025-01-15T10:30:00.123456Z',
                updated_at=None
            )
        ]
        ```
        """
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
        """
        Create new collection in the default orbit.

        Args:
            description: Description of the collection.
            name: Name of the collection.
            collection_type: Type of collection: "model", "dataset".
            tags: Optional list of tags for organizing collections.

        Returns:
            Collection: Created collection object.

        Example:
        ```python
        luml = AsyncLumlClient(api_key="luml_your_key")
        async def main():
            collection = await luml.collections.create(
                name="Training Dataset",
                description="Dataset for model training",
                collection_type=CollectionType.DATASET,
                tags=["ml", "training"]
            )
        ```

        Response object:
        ```python
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            name="Training Dataset",
            description="Dataset for model training",
            collection_type='model',
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            tags=["ml", "training"],
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at=None
        )
        ```
        """
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
        collection_id: str | None = None,
    ) -> Collection:
        """
        Update collection by ID or use default collection if collection_id not provided.

        Updates the collection's data. Only provided parameters will be
        updated, others remain unchanged. If collection_id is None,
        the default collection from client will be used.

        Args:
            name: New name for the collection.
            description: New description for the collection.
            tags: New list of tags.
            collection_id: ID of the collection to update. If not provided,
                uses the default collection set in the client.

        Returns:
            Collection: Updated collection object.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        async def main():
            collection = await luml.collections.update(
                collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
                name="Updated Dataset",
                tags=["ml", "updated"]
            )

            luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"
            collection = await luml.collections.update(
                name="Updated Dataset",
                description="Updated description"
            )
        ```

        Response object:
        ```python
        Collection(
            id="0199c455-21ee-74c6-b747-19a82f1a1e75",
            orbit_id="0199c455-21ed-7aba-9fe5-5231611220de",
            description="Updated description",
            name="Updated Dataset",
            collection_type='model',
            tags=["ml", "updated"],
            total_models=43,
            created_at='2025-01-15T10:30:00.123456Z',
            updated_at='2025-01-15T14:22:30.987654Z'
        )
        ```
        """
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
    async def delete(self, collection_id: str | None = None) -> None:
        """
        Delete collection by ID or use default collection if collection_id not provided.

        Permanently removes the collection and all its models.
            This action cannot be undone.
        If collection_id is None, the default collection from client will be used.

        Args:
            collection_id: ID of the collection to delete. If not provided,
                uses the default collection set in the client.

        Returns:
            None: No return value on successful deletion.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
        )
        async def main():
            # Delete specific collection by ID
            await luml.collections.delete(
                "0199c455-21ee-74c6-b747-19a82f1a1e75"
            )

        # Set default collection
        luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e56"
        # Delete default collection
        await luml.collections.delete()
        ```

        Warning:
            This operation is irreversible. All models, datasets, and data
            within the collection will be permanently lost. Consider backing up
            important data before deletion.
        """
        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}/collections/{collection_id}"
        )
