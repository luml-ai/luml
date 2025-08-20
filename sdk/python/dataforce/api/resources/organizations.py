from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import Organization
from .._utils import find_by_value

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class OrganizationResourceBase(ABC):
    """Abstract Resource for managing Organizations."""

    @abstractmethod
    def get(
        self, organization_value: str
    ) -> Organization | None | Coroutine[Any, Any, Organization | None]:
        """Abstract method for selecting Organization details"""
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> list[Organization] | Coroutine[Any, Any, list[Organization]]:
        """Abstract method for list all organizations available for user."""
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, name: str
    ) -> Organization | None | Coroutine[Any, Any, Organization | None]:
        """Abstract Method for search organization by name"""
        raise NotImplementedError()


class OrganizationResource(OrganizationResourceBase):
    """Resource for managing organizations."""

    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, organization_value: str) -> Organization | None:
        """
        Get organization by name.

        Retrieves organization details by its name.
        Search is case-sensitive and matches exact organization names.

        Args:
            organization_value: The exact name of the organization to retrieve.

        Returns:
            Organization object.

            Returns None if organization with the specified name is not found.

        Raises:
            MultipleResourcesFoundError: if there are several
                Organizations with that name.

        Example:
            >>> dfs = DataForceClient(api_key="dfs_your_key")
            >>> org = dfs.organizations.get("my-company")

        Example response:
            >>> Organization(
            ...    id=123,
            ...    name="My Personal Company",
            ...    logo='https://example.com/',
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at=None
            ...)
        """
        return self._get_by_name(organization_value)

    def list(self) -> list[Organization]:
        """
        List all organizations.

        Retrieves all organizations available for user.

        Returns:
            List of Organization objects.

        Example:
            >>> dfs = DataForceClient(api_key="dfs_your_key")
            >>> orgs = dfs.organizations.list()

        Example response:
            >>> [
            ...     Organization(
            ...         id=123,
            ...         name="My Personal Company",
            ...         logo='https://example.com/',
            ...         created_at='2025-05-21T19:35:17.340408Z',
            ...         updated_at=None
            ...     )
            ...]

        """
        response = self._client.get("/users/me/organizations")
        if response is None:
            return []
        return [Organization.model_validate(org) for org in response]

    def _get_by_name(self, name: str) -> Organization | None:
        """Private Method for search organization by name"""
        return find_by_value(self.list(), name)


class AsyncOrganizationResource(OrganizationResourceBase):
    """Resource for managing organizations for async client."""

    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, organization_value: str) -> Organization | None:
        """
        Get organization by name.

        Retrieves organization details by its name.
        Search is case-sensitive and matches exact organization names.

        Args:
            organization_value: The exact name of the organization to retrieve.

        Returns:
            Organization object.

            Returns None if organization with the specified name is not found.

        Raises:
            MultipleResourcesFoundError: if there are several
                Organizations with that name.

        Example:
            >>> dfs = AsyncDataForceClient(api_key="dfs_your_key")
            >>> async def main():
            ...     org = await dfs.organizations.get("my-company")

        Example response:
            >>> Organization(
            ...    id=123,
            ...    name="My Personal Company",
            ...    logo='https://example.com/',
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at=None
            ...)
        """
        return await self._get_by_name(organization_value)

    async def list(self) -> list[Organization]:
        """
        List all organizations.

        Retrieves all organizations available for user.

        Returns:
            List of Organization objects.

        Example:
            >>> dfs = AsyncDataForceClient(api_key="dfs_your_key")
            >>> async def main():
            ...     orgs = await dfs.organizations.list()

        Example response:
            >>> [
            ...     Organization(
            ...         id=123,
            ...         name="My Personal Company",
            ...         logo='https://example.com/',
            ...         created_at='2025-05-21T19:35:17.340408Z',
            ...         updated_at=None
            ...     )
            ...]
        """
        response = await self._client.get("/users/me/organizations")
        if response is None:
            return []
        return [Organization.model_validate(org) for org in response]

    async def _get_by_name(self, name: str) -> Organization | None:
        """Private Method for search organization by name"""
        return find_by_value(await self.list(), name)

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
