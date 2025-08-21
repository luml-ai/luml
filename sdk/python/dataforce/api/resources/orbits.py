from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .. import DataForceAPIError
from .._types import Orbit
from .._utils import find_by_value

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class OrbitResourceBase(ABC):
    """Abstract Resource for managing Orbits."""

    @abstractmethod
    def get(
        self, orbit_value: int | str | None = None
    ) -> Orbit | None | Coroutine[Any, Any, Orbit | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(self) -> Orbit | Coroutine[Any, Any, Orbit]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_name(
        self, name: str
    ) -> Orbit | None | Coroutine[Any, Any, Orbit | None]:
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> list[Orbit] | Coroutine[Any, Any, list[Orbit]]:
        raise NotImplementedError()

    @abstractmethod
    def create(
        self, name: str, bucket_secret_id: int
    ) -> Orbit | Coroutine[Any, Any, Orbit]:
        raise NotImplementedError()

    @abstractmethod
    def update(
        self, name: str | None = None, bucket_secret_id: int | None = None
    ) -> Orbit | Coroutine[Any, Any, Orbit]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, orbit_id: int) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class OrbitResource(OrbitResourceBase):
    """Resource for managing Orbits."""

    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, orbit_value: int | str | None = None) -> Orbit | None:
        """
        Get orbit by ID or name.

        Retrieves orbit details by its ID or name.
        Search by name is case-sensitive and matches exact orbit name.

        Args:
            orbit_value: The ID or exact name of the orbit to retrieve.

        Returns:
            Orbit object.

            Returns None if orbit with the specified id or name is not found.

        Raises:
            MultipleResourcesFoundError: if there are several
                Orbits with that name.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            ... orbit_by_name = dfs.orbits.get("Default Orbit")
            ... orbit_by_id = dfs.orbits.get(1215)

        Example response:
            >>> Orbit(
            ...    id=1215,
            ...    name="Default Orbit",
            ...    organization_id=1,
            ...    bucket_secret_id=1292,
            ...    total_members=2,
            ...    total_collections=9,
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at='2025-08-13T22:44:58.035731Z'
            ...)
        """
        if isinstance(orbit_value, int) or orbit_value is None:
            return self._get_by_id()
        if isinstance(orbit_value, str):
            return self._get_by_name(orbit_value)
        return None

    def _get_by_id(self) -> Orbit:
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}"
        )
        return Orbit.model_validate(response)

    def _get_by_name(self, name: str) -> Orbit | None:
        return find_by_value(self.list(), name)

    def list(self) -> list[Orbit]:
        """
        List all orbits related to default organization.

        Returns:
            List of Orbits objects.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> orgs = dfs.orbits.list()

        Example response:
            >>> [
            ...     Orbit(
            ...         id=1215,
            ...         name="Default Orbit",
            ...         organization_id=1,
            ...         bucket_secret_id=1292,
            ...         total_members=2,
            ...         total_collections=9,
            ...         created_at='2025-05-21T19:35:17.340408Z',
            ...         updated_at='2025-08-13T22:44:58.035731Z'
            ...     )
            ...]
        """
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits"
        )
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    def create(self, name: str, bucket_secret_id: int) -> Orbit:
        """Create new orbit in the default organization.

        Args:
            name: Name of the orbit.
            bucket_secret_id: ID of the bucket secret.
                The bucket secret must exist before orbit creation.

        Returns:
            Orbit: Newly created orbit object with generated ID and timestamps.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> orbit = dfs.orbits.create(
            ...     name="ML Models",
            ...     bucket_secret_id=123
            ... )

        Response object:
            >>> Orbit(
            ...    id=1215,
            ...    name="Default Orbit",
            ...    organization_id=1,
            ...    bucket_secret_id=1292,
            ...    total_members=2,
            ...    total_collections=9,
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at='2025-08-13T22:44:58.035731Z'
            ...)
        """
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    def update(
        self, name: str | None = None, bucket_secret_id: int | None = None
    ) -> Orbit:
        """
        Update default orbit configuration.

        Updates current orbit's name, bucket secret. Only provided
        parameters will be updated, others remain unchanged.

        Args:
            name: New name for the orbit. If None, name remains unchanged.
            bucket_secret_id: New bucket secret for storage configuration.
                The bucket secret must exist. If None, bucket secret remains unchanged.

        Returns:
            Orbit: Updated orbit object.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> orbit = dfs.orbits.update(name="New Orbit Name")

            >>> orbit = dfs.orbits.update(
            ...     name="New Orbit Name",
            ...     bucket_secret_id=456
            ... )

            Response object:
                >>> Orbit(
                ...    id=1215,
                ...    name="Default Orbit",
                ...    organization_id=1,
                ...    bucket_secret_id=1292,
                ...    total_members=2,
                ...    total_collections=9,
                ...    created_at='2025-05-21T19:35:17.340408Z',
                ...    updated_at='2025-08-13T22:44:58.035731Z'
                ...)

        Note:
            This method updates the orbit set as default in the client.
        """
        response = self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}",
            json=self._client.filter_none(
                {
                    "name": name,
                    "bucket_secret_id": bucket_secret_id,
                }
            ),
        )
        return Orbit.model_validate(response)

    def delete(self, orbit_id: int) -> None:
        """
        Delete orbit by ID.

        Permanently removes the orbit and all its associated data including
        collections, models, and configurations. This action cannot be undone.

        Returns:
            None: No return value on successful deletion.

        Raises:
            DataForceAPIError: If try to delete default orbit.

        Example:
            >>> dfs = DataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1, collection=1
            ... )
            ... dfs.orbits.delete(3)

        Warning:
            This operation is irreversible. All collections, models, and data
            within the orbit will be permanently lost. Consider backing up
            important data before deletion.

        """
        if self._client.orbit and orbit_id == self._client.orbit:
            raise DataForceAPIError("Default orbit cant be deleted.")

        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{orbit_id}"
        )


class AsyncOrbitResource(OrbitResourceBase):
    """Resource for managing Orbits for async client."""

    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, orbit_value: int | str | None = None) -> Orbit | None:
        """
        Get orbit by ID or name.

        Retrieves orbit details by its ID or name.
        Search by name is case-sensitive and matches exact orbit name.

        Args:
            orbit_value: The ID or exact name of the orbit to retrieve.

        Returns:
            Orbit object.

            Returns None if orbit with the specified id or name is not found.

        Raises:
            MultipleResourcesFoundError: if there are several
                Orbits with that name.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> async def main():
            ...     orbit_by_name = await dfs.orbits.get("Default Orbit")
            ...     orbit_by_id = await dfs.orbits.get(1215)

        Example response:
            >>> Orbit(
            ...    id=1215,
            ...    name="Default Orbit",
            ...    organization_id=1,
            ...    bucket_secret_id=1292,
            ...    total_members=2,
            ...    total_collections=9,
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at='2025-08-13T22:44:58.035731Z'
            ...)
        """
        if isinstance(orbit_value, int) or orbit_value is None:
            return await self._get_by_id()
        if isinstance(orbit_value, str):
            return await self._get_by_name(orbit_value)
        return None

    async def _get_by_id(self) -> Orbit:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}"
        )
        return Orbit.model_validate(response)

    async def _get_by_name(self, name: str) -> Orbit | None:
        return find_by_value(await self.list(), name)

    async def list(self) -> list[Orbit]:
        """
        List all orbits related to default organization.

        Returns:
            List of Orbits objects.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> async def main():
            ...     orgs = await dfs.orbits.list()

        Example response:
            >>> [
            ...     Orbit(
            ...         id=1215,
            ...         name="Default Orbit",
            ...         organization_id=1,
            ...         bucket_secret_id=1292,
            ...         total_members=2,
            ...         total_collections=9,
            ...         created_at='2025-05-21T19:35:17.340408Z',
            ...         updated_at='2025-08-13T22:44:58.035731Z'
            ...     )
            ...]
        """
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits"
        )
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    async def create(self, name: str, bucket_secret_id: int) -> Orbit:
        """Create new orbit in the default organization.

        Args:
            name: Name of the orbit.
            bucket_secret_id: ID of the bucket secret.
                The bucket secret must exist before orbit creation.

        Returns:
            Orbit: Newly created orbit object with generated ID and timestamps.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> async def main():
            ...     orbit = await dfs.orbits.create(
            ...         name="ML Models",
            ...         bucket_secret_id=123
            ...     )

        Response object:
            >>> Orbit(
            ...    id=1215,
            ...    name="Default Orbit",
            ...    organization_id=1,
            ...    bucket_secret_id=1292,
            ...    total_members=2,
            ...    total_collections=9,
            ...    created_at='2025-05-21T19:35:17.340408Z',
            ...    updated_at='2025-08-13T22:44:58.035731Z'
            ...)
        """
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    async def update(
        self, name: str | None = None, bucket_secret_id: int | None = None
    ) -> Orbit:
        """
        Update default orbit configuration.

        Updates current orbit's name, bucket secret. Only provided
        parameters will be updated, others remain unchanged.

        Args:
            name: New name for the orbit. If None, name remains unchanged.
            bucket_secret_id: New bucket secret for storage configuration.
                The bucket secret must exist. If None, bucket secret remains unchanged.

        Returns:
            Orbit: Updated orbit object.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> async def main():
            ...     orbit = await dfs.orbits.update(name="New Orbit Name")
            ...
            ...     orbit = await dfs.orbits.update(
            ...         name="New Orbit Name",
            ...         bucket_secret_id=456
            ...     )

            Response object:
                >>> Orbit(
                ...    id=1215,
                ...    name="Default Orbit",
                ...    organization_id=1,
                ...    bucket_secret_id=1292,
                ...    total_members=2,
                ...    total_collections=9,
                ...    created_at='2025-05-21T19:35:17.340408Z',
                ...    updated_at='2025-08-13T22:44:58.035731Z'
                ...)

        Note:
            This method updates the orbit set as default in the client.
        """
        response = await self._client.patch(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}",
            json=self._client.filter_none(
                {
                    "name": name,
                    "bucket_secret_id": bucket_secret_id,
                }
            ),
        )
        return Orbit.model_validate(response)

    async def delete(self, orbit_id: int) -> None:
        """
        Delete orbit by ID.

        Permanently removes the orbit and all its associated data including
        collections, models, and configurations. This action cannot be undone.

        Returns:
            None: No return value on successful deletion.

        Raises:
            DataForceAPIError: If try to delete default orbit.

        Example:
            >>> dfs = AsyncDataForceClient(
            ...     api_key="dfs_your_key", organization=1, orbit=1215, collection=1
            ... )
            >>> async def main():
            ...     await dfs.orbits.delete(3)

        Warning:
            This operation is irreversible. All collections, models, and data
            within the orbit will be permanently lost. Consider backing up
            important data before deletion.

        """
        if self._client.orbit and orbit_id == self._client.orbit:
            raise DataForceAPIError("Default orbit cant be deleted.")

        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{orbit_id}"
        )
