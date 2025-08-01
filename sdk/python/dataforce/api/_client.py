import os
from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING

from ._base_client import AsyncBaseClient, SyncBaseClient
from ._exceptions import DataForceAPIError

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
    def __init__(
            self,
            base_url: str | None = None,
            api_key: str | None = None,
            default_organization: int | None = None,
            default_orbit: int | None = None,
            default_collection: int | None = None,
    ) -> None:
        if base_url is None:
            base_url = os.environ.get("DFS_BASE_URL")
        if base_url is None:
            base_url = "https://api.dataforce.studio"

        super().__init__(base_url=base_url)

        if api_key is None:
            api_key = os.environ.get("DFS_API_KEY")
        if api_key is None:
            raise DataForceAPIError(
                "The api_key client option must be set either by "
                "passing api_key to the client or "
                "by setting the DFS_API_KEY environment variable"
            )
        self._api_key = api_key

        self._default_organization = default_organization
        self._default_orbit = default_orbit
        self._default_collection = default_collection

    @property
    def default_organization(self):
        return self._default_organization

    @default_organization.setter
    def default_organization(self, organization: int | None):
        self._default_organization = organization

    @property
    def default_orbit(self):
        return self._default_orbit

    @default_orbit.setter
    def default_orbit(self, orbit: int | None):
        self._default_orbit = orbit

    @property
    def default_collection(self):
        return self._default_collection

    @default_collection.setter
    def default_collection(self, collection: int | None):
        self._default_collection = collection

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    @cached_property
    @abstractmethod
    def organization(self) -> "OrganizationResource | AsyncOrganizationResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def bucket_secret(self) -> "BucketSecretResource | AsyncBucketSecretResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def orbit(self) -> "OrbitResource | AsyncOrbitResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def collection(self) -> "CollectionResource | AsyncCollectionResource":
        raise NotImplementedError()

    @cached_property
    @abstractmethod
    def model_artifact(self) -> "ModelArtifactResource | AsyncModelArtifactResource":
        raise NotImplementedError()


class AsyncDataForceClient(DataForceClientBase, AsyncBaseClient):
    @cached_property
    def organization(self) -> "AsyncOrganizationResource":
        from .resources.organizations import AsyncOrganizationResource

        return AsyncOrganizationResource(self)

    @cached_property
    def bucket_secret(self) -> "AsyncBucketSecretResource":
        from .resources.bucket_secrets import AsyncBucketSecretResource

        return AsyncBucketSecretResource(self)

    @cached_property
    def orbit(self) -> "AsyncOrbitResource":
        from .resources.orbits import AsyncOrbitResource

        return AsyncOrbitResource(self)

    @cached_property
    def collection(self) -> "AsyncCollectionResource":
        from .resources.collections import AsyncCollectionResource

        return AsyncCollectionResource(self)

    @cached_property
    def model_artifact(self) -> "AsyncModelArtifactResource":
        from .resources.model_artifacts import AsyncModelArtifactResource

        return AsyncModelArtifactResource(self)


class DataForceClient(DataForceClientBase, SyncBaseClient):
    @cached_property
    def organization(self) -> "OrganizationResource":
        from .resources.organizations import OrganizationResource

        return OrganizationResource(self)

    @cached_property
    def bucket_secret(self) -> "BucketSecretResource":
        from .resources.bucket_secrets import BucketSecretResource

        return BucketSecretResource(self)

    @cached_property
    def orbit(self) -> "OrbitResource":
        from .resources.orbits import OrbitResource

        return OrbitResource(self)

    @cached_property
    def collection(self) -> "CollectionResource":
        from .resources.collections import CollectionResource

        return CollectionResource(self)

    @cached_property
    def model_artifact(self) -> "ModelArtifactResource":
        from .resources.model_artifacts import ModelArtifactResource

        return ModelArtifactResource(self)
