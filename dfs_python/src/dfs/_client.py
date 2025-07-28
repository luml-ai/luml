import os
import httpx

from ._base_client import BaseClient
from ._exceptions import DataForceAPIError
from .resources.bucket_secrets import BucketSecretResource
from .resources.organizations import OrganizationResource
from .resources.orbits import OrbitResource
from .resources.collections import CollectionResource
from .resources.ml_models import MLModelResource


class DataForceClient(BaseClient):
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        if api_key is None:
            api_key = os.environ.get("DFS_API_KEY")
        if api_key is None:
            raise DataForceAPIError(
                "The api_key client option must be set either by passing api_key to the client or "
                "by setting the DFS_API_KEY environment variable"
            )
        self._api_key = api_key

        if base_url is None:
            base_url = os.environ.get("DFS_BASE_URL")
        if base_url is None:
            base_url = f"https://api.dataforce.studio"

        super().__init__(base_url=base_url)

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    # @cached_property
    @property
    def organization(self) -> OrganizationResource:
        from .resources.organizations import OrganizationResource

        return OrganizationResource(self)

    @property
    def bucket_secret(self) -> BucketSecretResource:
        from .resources.bucket_secrets import BucketSecretResource

        return BucketSecretResource(self)

    @property
    def orbit(self) -> OrbitResource:
        from .resources.orbits import OrbitResource

        return OrbitResource(self)

    @property
    def collection(self) -> CollectionResource:
        from .resources.collections import CollectionResource

        return CollectionResource(self)

    @property
    def ml_model(self) -> MLModelResource:
        from .resources.ml_models import MLModelResource

        return MLModelResource(self)

    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ):
        pass
