from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import Organization
from .._utils import find_by_name

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class OrganizationResourceBase(ABC):
    @abstractmethod
    def get(
        self, organization_value: str
    ) -> Organization | None | Coroutine[Any, Any, Organization]:
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> list[Organization] | Coroutine[Any, Any, list[Organization]]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, name: str
    ) -> Organization | None | Coroutine[Any, Any, Organization | None]:
        raise NotImplementedError()


class OrganizationResource(OrganizationResourceBase):
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, organization_value: str) -> Organization | None:
        return self._get_by_name(organization_value)

    def list(self) -> list[Organization]:
        response = self._client.get("/users/me/organizations")
        if response is None:
            return []
        return [Organization.model_validate(org) for org in response]

    def _get_by_name(self, name: str) -> Organization | None:
        return find_by_name(self.list(), name)


class AsyncOrganizationResource(OrganizationResourceBase):
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, organization_value: str) -> Organization | None:  # type: ignore[override]
        return await self._get_by_name(organization_value)

    async def list(self) -> list[Organization]:  # type: ignore[override]
        response = await self._client.get("/users/me/organizations")
        if response is None:
            return []
        return [Organization.model_validate(org) for org in response]

    async def _get_by_name(self, name: str) -> Organization | None:  # type: ignore[override]
        return find_by_name(await self.list(), name)

    # async def create(self, name: str, logo: str | None = None) -> Organization:
    #     response = await self._post(
    #         "/organizations",
    #         json={"name": name, "logo": logo}
    #     )
    #     return Organization(**response)
    #
    # async def update(
    #     self, organization_id: int, name: str | None = None, logo: str | None = None
    # ) -> Organization:
    #     response = await self._patch(
    #         f"/organizations/{organization_id}",
    #         json={"id": organization_id, "name": name, "logo": logo},
    #     )
    #     return Organization(**response)
