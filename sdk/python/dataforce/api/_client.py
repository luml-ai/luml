import os
from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any

from httpx import URL

from ._base_client import AsyncBaseClient, SyncBaseClient
from ._exceptions import (
    CollectionResourceNotFoundError,
    ConfigurationError,
    DataForceAPIError,
    OrbitResourceNotFoundError,
    OrganizationResourceNotFoundError,
)

if TYPE_CHECKING:
    from .resources.bucket_secrets import (
        AsyncBucketSecretResource,
        BucketSecretResource,
    )
    from .resources.collections import AsyncCollectionResource, CollectionResource
    from .resources.model_artifacts import (
        AsyncModelArtifactResource,
        ModelArtifactResource,
    )
    from .resources.orbits import AsyncOrbitResource, OrbitResource
    from .resources.organizations import AsyncOrganizationResource, OrganizationResource


class DataForceClientBase(ABC):
    """Base class for DataForce API clients."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        if base_url is None:
            base_url = os.environ.get("DFS_BASE_URL")
        if base_url is None:
            base_url = "https://api.dataforce.studio"

        self._base_url: URL = URL(base_url)

        if api_key is None:
            api_key = os.environ.get("DFS_API_KEY")
        if api_key is None:
            raise DataForceAPIError(
                "The api_key client option must be set either by "
                "passing api_key to the client or "
                "by setting the DFS_API_KEY environment variable"
            )
        self._api_key = api_key

        self._organization: int | None = None
        self._orbit: int | None = None
        self._collection: int | None = None

    @staticmethod
    def _validate_default_resource(
        entity_value: int | str | None,
        entities: list,
        exception_class: type[Exception],
    ) -> int | None:
        if not entity_value:
            return entities[0].id if len(entities) == 1 else None

        if isinstance(entity_value, int):
            entity = next((e for e in entities if e.id == entity_value), None)
        elif isinstance(entity_value, str):
            entity = next((e for e in entities if e.name == entity_value), None)
        else:
            entity = None

        if not entity:
            raise exception_class(entity_value, entities)

        return entity.id

    @abstractmethod
    def _validate_organization(self, org_value: int | str | None) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    @abstractmethod
    def _validate_orbit(self, orbit_value: int | str | None) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    @abstractmethod
    def _validate_collection(self, collection_value: int | str | None) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    @property
    def organization(self) -> int | None:
        return self._organization

    @organization.setter
    def organization(self, organization: int | None) -> None:
        self._organization = organization

    @property
    def orbit(self) -> int | None:
        return self._orbit

    @orbit.setter
    def orbit(self, orbit: int | None) -> None:
        self._orbit = orbit

    @property
    def collection(self) -> int | None:
        return self._collection

    @collection.setter
    def collection(self, collection: int | None) -> None:
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
    def model_artifacts(self) -> "ModelArtifactResource | AsyncModelArtifactResource":
        raise NotImplementedError()


class AsyncDataForceClient(DataForceClientBase, AsyncBaseClient):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Async client for interacting with the DataForce platform API.

        Parameters:
            base_url: Base URL of the DataForce API.
                Defaults to production DataForce Api URL: https://api.dataforce.studio.
                Can also be set in env with name DFS_BASE_URL
            api_key: Your DataForce API key for authentication.
                Can also be set in env with name DFS_API_KEY

        Attributes:
            organizations: Interface for managing experiments.
            orbits: Interface for managing orbits.
            collections: Interface for managing collections.
            bucket_secrets: Interface for managing bucket secrets.
            model_artifacts: Interface for managing model artifacts.

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
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_api_key",
            ...     organization=123,
            ...     orbit=456
            ... )

            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_api_key",
            ...     organization="My Personal Organization",
            ...     orbit="Default Orbit"
            ... )

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
            ``dfs.organization=4``.
        """

        DataForceClientBase.__init__(self, base_url=base_url, api_key=api_key)
        AsyncBaseClient.__init__(self, base_url=self._base_url)

    async def setup_config(
        self,
        organization: int | str | None = None,
        orbit: int | str | None = None,
        collection: int | str | None = None,
    ) -> None:
        """
        Method for setting default values for AsyncDataForceClient

        Args:
            organization: Default organization to use for operations.
                Can be set by organization ID or name.
            orbit: Default orbit to use for operations.
                Can be set by organization ID or name.
            collection: Default collection to use for operations.
                Can be set by organization ID or name.

        Example:
            >>> dfs = AsyncDataForceClient(api_key="dfs_api_key")
            >>> async def main():
            ...     await dfs.setup_config(1, 1215, 15)

        """
        self._organization = await self._validate_organization(organization)
        self._orbit = await self._validate_orbit(orbit)
        self._collection = await self._validate_collection(collection)

    async def _validate_organization(self, org_value: int | str | None) -> int | None:
        all_organizations = await self.organizations.list()
        return self._validate_default_resource(
            org_value, all_organizations, OrganizationResourceNotFoundError
        )

    async def _validate_orbit(self, orbit_value: int | str | None) -> int | None:
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

    async def _validate_collection(
        self, collection_value: int | str | None
    ) -> int | None:
        if not collection_value and (not self._organization or not self._orbit):
            return None

        all_collections = await self.collections.list()
        if (not self._organization or not self._orbit) and collection_value:
            raise ConfigurationError(
                "Collection",
                "Default organization and orbit must be "
                "set before setting default collection.",
                all_values=all_collections,
            )
        return self._validate_default_resource(
            collection_value, all_collections, CollectionResourceNotFoundError
        )

    @cached_property
    def organizations(self) -> "AsyncOrganizationResource":
        """Organizations interface."""
        from .resources.organizations import AsyncOrganizationResource

        return AsyncOrganizationResource(self)

    @cached_property
    def bucket_secrets(self) -> "AsyncBucketSecretResource":
        """Bucket Secrets interface."""
        from .resources.bucket_secrets import AsyncBucketSecretResource

        return AsyncBucketSecretResource(self)

    @cached_property
    def orbits(self) -> "AsyncOrbitResource":
        """Orbits interface."""
        from .resources.orbits import AsyncOrbitResource

        return AsyncOrbitResource(self)

    @cached_property
    def collections(self) -> "AsyncCollectionResource":
        """Collections interface."""
        from .resources.collections import AsyncCollectionResource

        return AsyncCollectionResource(self)

    @cached_property
    def model_artifacts(self) -> "AsyncModelArtifactResource":
        """Model Artifacts interface."""
        from .resources.model_artifacts import AsyncModelArtifactResource

        return AsyncModelArtifactResource(self)


class DataForceClient(DataForceClientBase, SyncBaseClient):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        organization: int | str | None = None,
        orbit: int | str | None = None,
        collection: int | str | None = None,
    ) -> None:
        """Client for interacting with the DataForce platform API.

        Parameters:
            base_url: Base URL of the DataForce API.
                Defaults to production DataForce Api URL: https://api.dataforce.studio.
                Can also be set in env with name DFS_BASE_URL
            api_key: Your DataForce API key for authentication.
                Can also be set in env with name DFS_API_KEY
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
            model_artifacts: Interface for managing model artifacts.

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
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_api_key",
            ...     organization=123,
            ...     orbit=456
            ... )

            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_api_key",
            ...     organization="My Personal Organization",
            ...     orbit="Default Orbit"
            ... )

        Note:
            For long-running operations, consider using the async version:
                AsyncDataForceClient.

            Default resource configuration is optional. If no values are provided during
            client initialization and you have only one organization, orbit,
            or collection, the appropriate resource will be automatically set as default

            Hierarchy constraints:

            - Cannot set default orbit without setting default organization first
            - Cannot set default collection without setting default orbit first
            - Default orbit must belong to the default organization
            - Default collection must belong to the default orbit

            You can change default resource after client inizialization
                ``dfs.organization=4``.
        """

        DataForceClientBase.__init__(self, base_url=base_url, api_key=api_key)
        SyncBaseClient.__init__(self, base_url=self._base_url)

        validated_org = self._validate_organization(organization)
        self._organization = validated_org

        validated_orbit = self._validate_orbit(orbit)
        self._orbit = validated_orbit

        validated_collection = self._validate_collection(collection)
        self._collection = validated_collection

    def _validate_organization(self, org_value: int | str | None) -> int | None:
        all_organizations = self.organizations.list()
        return self._validate_default_resource(
            org_value, all_organizations, OrganizationResourceNotFoundError
        )

    def _validate_orbit(self, orbit_value: int | str | None) -> int | None:
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

    def _validate_collection(self, collection_value: int | str | None) -> int | None:
        if not collection_value and (not self._organization or not self._orbit):
            return None
        all_collections = self.collections.list()
        if (not self._organization or not self._orbit) and collection_value:
            raise ConfigurationError(
                "Collection",
                "Default organization and orbit must be "
                "set before setting default collection.",
                all_values=all_collections,
            )
        return self._validate_default_resource(
            collection_value, all_collections, CollectionResourceNotFoundError
        )

    @cached_property
    def organizations(self) -> "OrganizationResource":
        """Organizations interface."""
        from .resources.organizations import OrganizationResource

        return OrganizationResource(self)

    @cached_property
    def bucket_secrets(self) -> "BucketSecretResource":
        """Bucket Secrets interface."""
        from .resources.bucket_secrets import BucketSecretResource

        return BucketSecretResource(self)

    @cached_property
    def orbits(self) -> "OrbitResource":
        """Orbits interface."""
        from .resources.orbits import OrbitResource

        return OrbitResource(self)

    @cached_property
    def collections(self) -> "CollectionResource":
        """Collections interface."""
        from .resources.collections import CollectionResource

        return CollectionResource(self)

    @cached_property
    def model_artifacts(self) -> "ModelArtifactResource":
        """Model Artifacts interface."""
        from .resources.model_artifacts import ModelArtifactResource

        return ModelArtifactResource(self)
