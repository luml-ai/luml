import os
from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING

from httpx import URL

from luml.api._base_client import AsyncBaseClient, SyncBaseClient
from luml.api._exceptions import (
    CollectionResourceNotFoundError,
    ConfigurationError,
    LumlAPIError,
    OrbitResourceNotFoundError,
    OrganizationResourceNotFoundError,
)
from luml.api._types import is_uuid

if TYPE_CHECKING:
    from luml.api.resources.artifacts import (
        ArtifactResource,
        AsyncArtifactResource,
    )
    from luml.api.resources.bucket_secrets import (
        AsyncBucketSecretResource,
        BucketSecretResource,
    )
    from luml.api.resources.collections import (
        AsyncCollectionResource,
        CollectionResource,
    )
    from luml.api.resources.orbits import AsyncOrbitResource, OrbitResource
    from luml.api.resources.organizations import (
        AsyncOrganizationResource,
        OrganizationResource,
    )


class LumlClientBase(ABC):
    """Base class for Luml API clients."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        if base_url is None:
            base_url = os.environ.get("LUML_BASE_URL")
        if base_url is None:
            base_url = "https://api.luml.ai"

        self._base_url: URL = URL(base_url)

        if api_key is None:
            api_key = os.environ.get("LUML_API_KEY")
        if api_key is None:
            raise LumlAPIError(
                "The api_key client option must be set either by "
                "passing api_key to the client or "
                "by setting the LUML_API_KEY environment variable"
            )
        self._api_key = api_key

        self._organization: str | None = None
        self._orbit: str | None = None
        self._collection: str | None = None

    @staticmethod
    def _validate_default_resource(
        entity_value: str | None,
        entities: list,
        exception_class: type[Exception],
    ) -> str | None:
        if not entity_value:
            entities_list = (
                list(entities) if not isinstance(entities, list) else entities
            )
            return entities_list[0].id if len(entities_list) == 1 else None

        entities_iter = (
            iter(entities) if not isinstance(entities, list) else iter(entities)
        )

        if is_uuid(entity_value):
            entity = next((e for e in entities_iter if e.id == entity_value), None)
        elif isinstance(entity_value, str):
            entity = next((e for e in entities_iter if e.name == entity_value), None)
        else:
            entity = None

        if not entity:
            entities_list = (
                list(entities) if not isinstance(entities, list) else entities
            )
            raise exception_class(entity_value, entities_list)
        return entity.id

    @abstractmethod
    def _validate_organization(self, org_value: str | None) -> str | None:
        raise NotImplementedError()

    @abstractmethod
    def _validate_orbit(self, orbit_value: str | None) -> str | None:
        raise NotImplementedError()

    @abstractmethod
    def _validate_collection(self, collection_value: str | None) -> str | None:
        raise NotImplementedError()

    @property
    def organization(self) -> str | None:
        return self._organization

    @organization.setter
    def organization(self, organization: str | None) -> None:
        self._organization = organization

    @property
    def orbit(self) -> str | None:
        return self._orbit

    @orbit.setter
    def orbit(self, orbit: str | None) -> None:
        self._orbit = orbit

    @property
    def collection(self) -> str | None:
        return self._collection

    @collection.setter
    def collection(self, collection: str | None) -> None:
        self._collection = collection

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    @cached_property
    @abstractmethod
    def organizations(self) -> "OrganizationResource | AsyncOrganizationResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def bucket_secrets(self) -> "BucketSecretResource | AsyncBucketSecretResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def orbits(self) -> "OrbitResource | AsyncOrbitResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def collections(self) -> "CollectionResource | AsyncCollectionResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def artifacts(self) -> "ArtifactResource | AsyncArtifactResource":
        raise NotImplementedError()


class AsyncLumlClient(LumlClientBase, AsyncBaseClient):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Async client for interacting with the Luml platform API.

        Parameters:
            base_url: Base URL of the Luml API.
                Defaults to production Luml Api URL: https://api.luml.ai.
                Can also be set in env with name LUML_BASE_URL
            api_key: Your Luml API key for authentication.
                Can also be set in env with name LUML_API_KEY

        Attributes:
            organizations: Interface for managing experiments.
            orbits: Interface for managing orbits.
            collections: Interface for managing collections.
            bucket_secrets: Interface for managing bucket secrets.
            artifacts: Interface for managing Artifacts.

        Raises:
            AuthenticationError: If API key is invalid or missing.
            ConfigurationError: If required configuration is missing.
            OrganizationResourceNotFoundError: If organization not found
                by ID or name passed for client configuration.
            OrbitResourceNotFoundError: If orbit not found by ID or name
                passed for client configuration
            CollectionResourceNotFoundError: If collection not found by ID or
                name passed for client configuration

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_api_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de"
        )

        luml = LumlClient(
            api_key="luml_your_api_key",
            organization="My Personal Organization",
            orbit="Default Orbit"
        )
        ```

        Note:
            Default resource configuration is optional. If no values are provided during
            client initialization and you have only one organization, orbit,
            or collection, the appropriate resource will be automatically set as default

            Hierarchy constraints:

            - Cannot set default orbit without setting default organization first
            - Cannot set default collection without setting default orbit first
            - Default orbit must belong to the default organization
            - Default collection must belong to the default orbit

            You can change default resource after client inizialization
            ``luml.organization=4``.
        """

        LumlClientBase.__init__(self, base_url=base_url, api_key=api_key)
        AsyncBaseClient.__init__(self, base_url=self._base_url)

    async def setup_config(
        self,
        *,
        organization: str | None = None,
        orbit: str | None = None,
        collection: str | None = None,
    ) -> None:
        """
        Method for setting default values for AsyncLumlClient

        Args:
            organization: Default organization to use for operations.
                Can be set by organization ID or name.
            orbit: Default orbit to use for operations.
                Can be set by organization ID or name.
            collection: Default collection to use for operations.
                Can be set by organization ID or name.

        Example:
        ```python
        luml = AsyncLumlClient(api_key="luml_api_key")
        async def main():
            await luml.setup_config(
                "0199c455-21ec-7c74-8efe-41470e29bae5",
                "0199c455-21ed-7aba-9fe5-5231611220de",
                "0199c455-21ee-74c6-b747-19a82f1a1e75"
            )
        ```
        """
        self._organization = await self._validate_organization(organization)
        self._orbit = await self._validate_orbit(orbit)
        self._collection = await self._validate_collection(collection)

    async def _validate_organization(self, org_value: str | None) -> str | None:  # type: ignore[override]
        all_organizations = await self.organizations.list()
        return self._validate_default_resource(
            org_value, all_organizations, OrganizationResourceNotFoundError
        )

    async def _validate_orbit(self, orbit_value: str | None) -> str | None:  # type: ignore[override]
        if not orbit_value and not self._organization:
            return None

        all_orbits = await self.orbits.list()

        if not self._organization and orbit_value:
            raise ConfigurationError(
                "Orbit",
                "Default organization must be set before setting default orbit.",
                all_values=all_orbits,
            )
        return self._validate_default_resource(
            orbit_value, all_orbits, OrbitResourceNotFoundError
        )

    async def _validate_collection_by_name(self, collection_value: str) -> str | None:
        collections_result = await self.collections.list(search=collection_value)
        if len(collections_result.items) == 1:
            return collections_result.items[0].id
        if len(collections_result.items) > 1:
            exact_matches = [
                collection
                async for collection in self.collections.list_all(
                    search=collection_value
                )
                if collection.name == collection_value
            ]
            if len(exact_matches) == 1:
                return exact_matches[0].id
            if len(exact_matches) > 1:
                raise CollectionResourceNotFoundError(
                    f"'{collection_value}' "
                    f"(multiple collections with this name found, use collection ID)",
                    all_values=exact_matches,
                    has_more=False,
                )
        return None

    async def _validate_collection(self, collection_value: str | None) -> str | None:  # type: ignore[override]
        if not collection_value and (not self._organization or not self._orbit):
            return None

        if (not self._organization or not self._orbit) and collection_value:
            collections_result = await self.collections.list()
            raise ConfigurationError(
                "Collection",
                "Default organization and orbit must be "
                "set before setting default collection.",
                all_values=collections_result.items,
                has_more=collections_result.cursor is not None,
            )

        if not collection_value:
            collections_result = await self.collections.list(limit=2)
            if len(collections_result.items) == 0:
                return None
            if len(collections_result.items) == 1 and collections_result.cursor is None:
                return collections_result.items[0].id

            all_collections = await self.collections.list()
            raise ConfigurationError(
                "Collection",
                "Multiple collections found. Please specify a collection ID or name.",
                all_values=all_collections.items,
                has_more=collections_result.cursor is not None,
            )

        if is_uuid(collection_value):
            async for collection in self.collections.list_all():
                if collection.id == collection_value:
                    return collection.id
        else:
            return await self._validate_collection_by_name(collection_value)

        collections_result = await self.collections.list()
        raise CollectionResourceNotFoundError(
            collection_value,
            all_values=collections_result.items,
            has_more=collections_result.cursor is not None,
        )

    @cached_property
    def organizations(self) -> "AsyncOrganizationResource":
        """Organizations interface."""
        from luml.api.resources.organizations import AsyncOrganizationResource

        return AsyncOrganizationResource(self)

    @cached_property
    def bucket_secrets(self) -> "AsyncBucketSecretResource":
        """Bucket Secrets interface."""
        from luml.api.resources.bucket_secrets import AsyncBucketSecretResource

        return AsyncBucketSecretResource(self)

    @cached_property
    def orbits(self) -> "AsyncOrbitResource":
        """Orbits interface."""
        from luml.api.resources.orbits import AsyncOrbitResource

        return AsyncOrbitResource(self)

    @cached_property
    def collections(self) -> "AsyncCollectionResource":
        """Collections interface."""
        from luml.api.resources.collections import AsyncCollectionResource

        return AsyncCollectionResource(self)

    @cached_property
    def artifacts(self) -> "AsyncArtifactResource":
        """Artifacts interface."""
        from luml.api.resources.artifacts import AsyncArtifactResource

        return AsyncArtifactResource(self)


class LumlClient(LumlClientBase, SyncBaseClient):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        organization: str | None = None,
        orbit: str | None = None,
        collection: str | None = None,
    ) -> None:
        """
        Client for interacting with the Luml platform API.

        Parameters:
            base_url: Base URL of the Luml API.
                Defaults to production Luml Api URL: https://api.luml.ai.
                Can also be set in env with name LUML_BASE_URL
            api_key: Your Luml API key for authentication.
                Can also be set in env with name LUML_API_KEY
            organization: Default organization to use for operations.
                Can be set by organization ID or name.
            orbit: Default orbit to use for operations.
                Can be set by organization ID or name.
            collection: Default collection to use for operations.
                Can be set by organization ID or name.

        Attributes:
            organizations: Interface for managing experiments.
            orbits: Interface for managing orbits.
            collections: Interface for managing collections.
            bucket_secrets: Interface for managing bucket secrets.
            artifacts: Interface for managing Artifacts.

        Raises:
            AuthenticationError: If API key is invalid or missing.
            ConfigurationError: If required configuration is missing.
            OrganizationResourceNotFoundError: If organization not found by ID
                or name passed for client configuration
            OrbitResourceNotFoundError: If orbit not found by ID
                or name passed for client configuration
            CollectionResourceNotFoundError: If collection not found
                by ID or name passed for client configuration

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_api_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de"
        )

        luml = LumlClient(
            api_key="luml_your_api_key",
            organization="My Personal Organization",
            orbit="Default Orbit"
        )
        ```

        Note:
            For long-running operations, consider using the async version:
                AsyncLumlClient.

            Default resource configuration is optional. If no values are provided during
            client initialization and you have only one organization, orbit,
            or collection, the appropriate resource will be automatically set as default

            Hierarchy constraints:

            - Cannot set default orbit without setting default organization first
            - Cannot set default collection without setting default orbit first
            - Default orbit must belong to the default organization
            - Default collection must belong to the default orbit

            You can change default resource after client inizialization
                ``luml.organization="0199c455-21ec-7c74-8efe-41470e29bae5"``.
        """

        LumlClientBase.__init__(self, base_url=base_url, api_key=api_key)
        SyncBaseClient.__init__(self, base_url=self._base_url)

        validated_org = self._validate_organization(organization)
        self._organization = validated_org

        validated_orbit = self._validate_orbit(orbit)
        self._orbit = validated_orbit

        validated_collection = self._validate_collection(collection)
        self._collection = validated_collection

    def _validate_organization(self, org_value: str | None) -> str | None:
        all_organizations = self.organizations.list()
        return self._validate_default_resource(
            org_value, all_organizations, OrganizationResourceNotFoundError
        )

    def _validate_orbit(self, orbit_value: str | None) -> str | None:
        if not orbit_value and not self._organization:
            return None

        all_orbits = self.orbits.list()

        if not self._organization and orbit_value:
            raise ConfigurationError(
                "Orbit",
                "Default organization must be set before setting default orbit.",
                all_values=all_orbits,
            )
        return self._validate_default_resource(
            orbit_value, all_orbits, OrbitResourceNotFoundError
        )

    def _validate_collection_by_name(self, collection_value: str) -> str | None:
        collections_result = self.collections.list(search=collection_value)
        if len(collections_result.items) == 1:
            return collections_result.items[0].id
        if len(collections_result.items) > 1:
            exact_matches = [
                collection
                for collection in self.collections.list_all(search=collection_value)
                if collection.name == collection_value
            ]
            if len(exact_matches) == 1:
                return exact_matches[0].id
            if len(exact_matches) > 1:
                raise CollectionResourceNotFoundError(
                    f"'{collection_value}' "
                    f"(multiple collections with this name found, use collection ID)",
                    all_values=exact_matches,
                    has_more=False,
                )
        return None

    def _validate_collection(self, collection_value: str | None) -> str | None:
        if not collection_value and (not self._organization or not self._orbit):
            return None

        if (not self._organization or not self._orbit) and collection_value:
            collections_result = self.collections.list()
            raise ConfigurationError(
                "Collection",
                "Default organization and orbit must be "
                "set before setting default collection.",
                all_values=collections_result.items,
                has_more=collections_result.cursor is not None,
            )

        if not collection_value:
            collections_result = self.collections.list(limit=2)
            if len(collections_result.items) == 0:
                return None
            if len(collections_result.items) == 1 and collections_result.cursor is None:
                return collections_result.items[0].id
            all_collections = self.collections.list()
            raise ConfigurationError(
                "Collection",
                "Multiple collections found. Please specify a collection ID or name.",
                all_values=all_collections.items,
                has_more=collections_result.cursor is not None,
            )

        if is_uuid(collection_value):
            for collection in self.collections.list_all():
                if collection.id == collection_value:
                    return collection.id
        else:
            return self._validate_collection_by_name(collection_value)

        collections_result = self.collections.list()
        raise CollectionResourceNotFoundError(
            collection_value,
            all_values=collections_result.items,
            has_more=collections_result.cursor is not None,
        )

    @cached_property
    def organizations(self) -> "OrganizationResource":
        """Organizations interface."""
        from luml.api.resources.organizations import OrganizationResource

        return OrganizationResource(self)

    @cached_property
    def bucket_secrets(self) -> "BucketSecretResource":
        """Bucket Secrets interface."""
        from luml.api.resources.bucket_secrets import BucketSecretResource

        return BucketSecretResource(self)

    @cached_property
    def orbits(self) -> "OrbitResource":
        """Orbits interface."""
        from luml.api.resources.orbits import OrbitResource

        return OrbitResource(self)

    @cached_property
    def collections(self) -> "CollectionResource":
        """Collections interface."""
        from luml.api.resources.collections import CollectionResource

        return CollectionResource(self)

    @cached_property
    def artifacts(self) -> "ArtifactResource":
        """Artifacts interface."""
        from luml.api.resources.artifacts import ArtifactResource

        return ArtifactResource(self)
