import os
import httpx

from ._base_client import BaseClient
from ._exceptions import DataForceAPIError
from .resources.organizations import Organization
# from .resources.bucket_secrets import BucketSecret
# from .resources.orbits import Orbit
# from .resources.collections import Collection
# from .resources.ml_models import MLModel


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
    def organization(self) -> Organization:
        from .resources.organizations import Organization

        return Organization(self)

    # # @cached_property
    # def bucket_secret(self) -> BucketSecret:
    #     from .resources.bucket_secrets import BucketSecret
    #
    #     return BucketSecret(self)
    #
    # # @cached_property
    # def orbit(self) -> Orbit:
    #     from .resources.orbits import Orbit
    #
    #     return Orbit(self)
    #
    # # @cached_property
    # def collection(self) -> Collection:
    #     from .resources.collections import Collection
    #
    #     return Collection(self)
    #
    # # @cached_property
    # def ml_model(self) -> MLModel:
    #     from .resources.ml_models import MLModel
    #
    #     return MLModel(self)

    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ):
        pass
