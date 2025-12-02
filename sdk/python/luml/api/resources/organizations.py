from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .._types import Organization, is_uuid
from .._utils import find_by_value

if TYPE_CHECKING:
    from .._client import AsyncLumlClient, LumlClient


class OrganizationResourceBase(ABC):
    """Abstract Resource for managing Organizations."""

    @abstractmethod
    def get(
        self, organization_value: str | None = None
    ) -> Organization | None | Coroutine[Any, Any, Organization | None]:
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
    """Resource for managing organizations."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def get(self, organization_value: str | None = None) -> Organization | None:
        """
        Get organization by name or ID.

        Retrieves organization details by its name or ID.
        Search by name is case-sensitive and matches exact organization names.

        Args:
            organization_value: The exact name or ID of the organization to retrieve.

        Returns:
            Organization object if found, None if organization
                with the specified name or ID is not found.

        Raises:
            MultipleResourcesFoundError: if there are several Organizations
                with that name.

        Example:
        ```python
        luml = LumlClient(api_key="luml_your_key")
        org_by_name = luml.organizations.get("My Personal Company")
        org_by_id = luml.organizations.get(
            "0199c455-21ec-7c74-8efe-41470e29bae5"
        )
        ```

        Example response:
        ```python
        Organization(
            id="0199c455-21ec-7c74-8efe-41470e29bae5",
            name="My Personal Company",
            logo='https://example.com/',
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at=None
        )
        ```
        """
        if organization_value is None:
            if self._client.organization:
                return self._get_by_id(self._client.organization)
            return None
        if is_uuid(organization_value):
            return self._get_by_id(organization_value)
        return self._get_by_name(organization_value)

    def list(self) -> list[Organization]:
        """
        List all organizations.

        Retrieves all organizations available for user.

        Returns:
            List of Organization objects.

        Example:
        ```python
        luml = LumlClient(api_key="luml_your_key")
        orgs = luml.organizations.list()
        ```

        Example response:
        ```python
        [
            Organization(
                id="0199c455-21ec-7c74-8efe-41470e29bae5",
                name="My Personal Company",
                logo='https://example.com/',
                created_at='2025-05-21T19:35:17.340408Z',
                updated_at=None
            )
        ]
        ```
        """
        response = self._client.get("/users/me/organizations")
        if response is None:
            return []
        return [Organization.model_validate(org) for org in response]

    def _get_by_name(self, name: str) -> Organization | None:
        return find_by_value(self.list(), name)

    def _get_by_id(self, organization_id: str) -> Organization | None:
        return find_by_value(
            self.list(), organization_id, lambda c: c.id == organization_id
        )


class AsyncOrganizationResource(OrganizationResourceBase):
    """Resource for managing organizations for async client."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    async def get(self, organization_value: str | None = None) -> Organization | None:
        """
        Get organization by name or ID.

        Retrieves organization details by its name or ID.
        Search by name is case-sensitive and matches exact organization names.

        Args:
            organization_value: The exact name or ID of the organization to retrieve.

        Returns:
            Organization object if found, None if organization
                with the specified name or ID is not found.

        Raises:
            MultipleResourcesFoundError: if there are several Organizations
                with that name.

        Example:
        ```python
        luml = AsyncLumlClient(api_key="luml_your_key")
        async def main():
            org_by_name = await luml.organizations.get("my-company")
            org_by_id = await luml.organizations.get(
                "0199c455-21ec-7c74-8efe-41470e29ba45"
            )
        ```

        Example response:
        ```python
        Organization(
            id="0199c455-21ec-7c74-8efe-41470e29bae5",
            name="My Personal Company",
            logo='https://example.com/',
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at=None
        )
        ```
        """
        if organization_value is None:
            if self._client.organization:
                return await self._get_by_id(self._client.organization)
            return None
        if is_uuid(organization_value):
            return await self._get_by_id(organization_value)
        return await self._get_by_name(organization_value)

    async def list(self) -> list[Organization]:
        """
        List all organizations.

        Retrieves all organizations available for user.

        Returns:
            List of Organization objects.

        Example:
        ```python
        luml = AsyncLumlClient(api_key="luml_your_key")
        async def main():
            orgs = await luml.organizations.list()
        ```

        Example response:
        ```python
        [
            Organization(
                id="0199c455-21ec-7c74-8efe-41470e29bae5",
                name="My Personal Company",
                logo='https://example.com/',
                created_at='2025-05-21T19:35:17.340408Z',
                updated_at=None
            )
        ]
        ```
        """
        response = await self._client.get("/users/me/organizations")
        if response is None:
            return []
        return [Organization.model_validate(org) for org in response]

    async def _get_by_name(self, name: str) -> Organization | None:
        return find_by_value(await self.list(), name)

    async def _get_by_id(self, organization_id: str) -> Organization | None:
        return find_by_value(
            await self.list(), organization_id, lambda c: c.id == organization_id
        )
