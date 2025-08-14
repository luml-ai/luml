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
        DataForceClientBase.__init__(self, base_url=base_url, api_key=api_key)
        AsyncBaseClient.__init__(self, base_url=self._base_url)

    async def setup_config(
        self,
        organization: int | None = None,
        orbit: int | None = None,
        collection: int | None = None,
    ) -> None:
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
        if not self._organization and orbit_value:
            raise ConfigurationError(
                "Default organization must be set before setting default orbit."
            )
        all_orbits = await self.orbits.list()
        return self._validate_default_resource(
            orbit_value, all_orbits, OrbitResourceNotFoundError
        )

    async def _validate_collection(
        self, collection_value: int | str | None
    ) -> int | None:
        if not collection_value and (not self._organization or not self._orbit):
            return None
        if (not self._organization or not self._orbit) and collection_value:
            raise ConfigurationError(
                "Default organization and orbit must be "
                "set before setting default collection."
            )
        all_collections = await self.collections.list()
        return self._validate_default_resource(
            collection_value, all_collections, CollectionResourceNotFoundError
        )

    @cached_property
    def organizations(self) -> "AsyncOrganizationResource":
        from .resources.organizations import AsyncOrganizationResource

        return AsyncOrganizationResource(self)

    @cached_property
    def bucket_secrets(self) -> "AsyncBucketSecretResource":
        from .resources.bucket_secrets import AsyncBucketSecretResource

        return AsyncBucketSecretResource(self)

    @cached_property
    def orbits(self) -> "AsyncOrbitResource":
        from .resources.orbits import AsyncOrbitResource

        return AsyncOrbitResource(self)

    @cached_property
    def collections(self) -> "AsyncCollectionResource":
        from .resources.collections import AsyncCollectionResource

        return AsyncCollectionResource(self)

    @cached_property
    def model_artifacts(self) -> "AsyncModelArtifactResource":
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
        if not self._organization and orbit_value:
            raise ConfigurationError(
                "Default organization must be set before setting default orbit."
            )
        all_orbits = self.orbits.list()
        return self._validate_default_resource(
            orbit_value, all_orbits, OrbitResourceNotFoundError
        )

    def _validate_collection(self, collection_value: int | str | None) -> int | None:
        if not collection_value and (not self._organization or not self._orbit):
            return None
        if (not self._organization or not self._orbit) and collection_value:
            raise ConfigurationError(
                "Default organization and orbit must be "
                "set before setting default collection."
            )
        all_collections = self.collections.list()
        return self._validate_default_resource(
            collection_value, all_collections, CollectionResourceNotFoundError
        )

    @cached_property
    def organizations(self) -> "OrganizationResource":
        from .resources.organizations import OrganizationResource

        return OrganizationResource(self)

    @cached_property
    def bucket_secrets(self) -> "BucketSecretResource":
        from .resources.bucket_secrets import BucketSecretResource

        return BucketSecretResource(self)

    @cached_property
    def orbits(self) -> "OrbitResource":
        from .resources.orbits import OrbitResource

        return OrbitResource(self)

    @cached_property
    def collections(self) -> "CollectionResource":
        from .resources.collections import CollectionResource

        return CollectionResource(self)

    @cached_property
    def model_artifacts(self) -> "ModelArtifactResource":
        from .resources.model_artifacts import ModelArtifactResource

        return ModelArtifactResource(self)
