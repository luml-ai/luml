from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from .. import LumlAPIError
from .._types import Orbit, is_uuid
from .._utils import find_by_value

if TYPE_CHECKING:
    from .._client import AsyncLumlClient, LumlClient


class OrbitResourceBase(ABC):
    """Abstract Resource for managing Orbits."""

    @abstractmethod
    def get(
        self, orbit_value: str | None = None
    ) -> Orbit | None | Coroutine[Any, Any, Orbit | None]:
        raise NotImplementedError()

    @abstractmethod
    def _get_by_id(self, orbit_id: str) -> Orbit | Coroutine[Any, Any, Orbit]:
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
        self, name: str, bucket_secret_id: str
    ) -> Orbit | Coroutine[Any, Any, Orbit]:
        raise NotImplementedError()

    @abstractmethod
    def update(
        self, name: str | None = None, bucket_secret_id: str | None = None
    ) -> Orbit | Coroutine[Any, Any, Orbit]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, orbit_id: str) -> None | Coroutine[Any, Any, None]:
        raise NotImplementedError()


class OrbitResource(OrbitResourceBase):
    """Resource for managing Orbits."""

    def __init__(self, client: "LumlClient") -> None:
        self._client = client

    def get(self, orbit_value: str | None = None) -> Orbit | None:
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
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        orbit_by_name = luml.orbits.get("Default Orbit")
        orbit_by_id = luml.orbits.get("0199c455-21ed-7aba-9fe5-5231611220de")
        ```

        Example response:
        ```python
        Orbit(
            id="0199c455-21ed-7aba-9fe5-5231611220de",
            name="Default Orbit",
            organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
            total_members=2,
            total_collections=9,
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at='2025-08-13T22:44:58.035731Z'
        )
        ```
        """
        if orbit_value is None:
            orbit_value = self._client.orbit
        if is_uuid(orbit_value):
            return self._get_by_id(orbit_value)
        return self._get_by_name(orbit_value)

    def _get_by_id(self, orbit_id: str) -> Orbit:
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits/{orbit_id}"
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
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        orgs = luml.orbits.list()
        ```

        Example response:
        ```python
        [
            Orbit(
                id="0199c455-21ed-7aba-9fe5-5231611220de",
                name="Default Orbit",
                organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
                bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
                total_members=2,
                total_collections=9,
                created_at='2025-05-21T19:35:17.340408Z',
                updated_at='2025-08-13T22:44:58.035731Z'
            )
        ]
        ```
        """
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits"
        )
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    def create(self, name: str, bucket_secret_id: str) -> Orbit:
        """Create new orbit in the default organization.

        Args:
            name: Name of the orbit.
            bucket_secret_id: ID of the bucket secret.
                The bucket secret must exist before orbit creation.

        Returns:
            Orbit: Newly created orbit object with generated ID and timestamps.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        orbit = luml.orbits.create(
            name="ML Models",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
        )
        ```

        Response object:
        ```python
        Orbit(
            id="0199c455-21ed-7aba-9fe5-5231611220de",
            name="Default Orbit",
            organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
            total_members=2,
            total_collections=9,
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at='2025-08-13T22:44:58.035731Z'
        )
        ```
        """
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    def update(
        self, name: str | None = None, bucket_secret_id: str | None = None
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
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        orbit = luml.orbits.update(name="New Orbit Name")

        orbit = luml.orbits.update(
            name="New Orbit Name",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
        )
        ```

        Response object:
        ```python
        Orbit(
            id="0199c455-21ed-7aba-9fe5-5231611220de",
            name="Default Orbit",
            organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
            total_members=2,
            total_collections=9,
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at='2025-08-13T22:44:58.035731Z'
        )
        ```

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

    def delete(self, orbit_id: str) -> None:
        """
        Delete orbit by ID.

        Permanently removes the orbit and all its associated data including
        collections, models, and configurations. This action cannot be undone.

        Returns:
            None: No return value on successful deletion.

        Raises:
            LumlAPIError: If try to delete default orbit.

        Example:
        ```python
        luml = LumlClient(
            api_key="luml_your_key",
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        luml.orbits.delete("0199c455-21ed-7aba-9fe5-5231611220de")
        ```

        Warning:
            This operation is irreversible. All collections, models, and data
            within the orbit will be permanently lost. Consider backing up
            important data before deletion.

        """
        if self._client.orbit and orbit_id == self._client.orbit:
            raise LumlAPIError("Default orbit cant be deleted.")

        return self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{orbit_id}"
        )


class AsyncOrbitResource(OrbitResourceBase):
    """Resource for managing Orbits for async client."""

    def __init__(self, client: "AsyncLumlClient") -> None:
        self._client = client

    async def get(self, orbit_value: str | None = None) -> Orbit | None:
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
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        async def main():
            orbit_by_name = await luml.orbits.get("Default Orbit")
            orbit_by_id = await luml.orbits.get(
                "0199c455-21ed-7aba-9fe5-5231611220de"
            )
        ```

        Example response:
        ```python
        Orbit(
            id="0199c455-21ed-7aba-9fe5-5231611220de",
            name="Default Orbit",
            organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
            total_members=2,
            total_collections=9,
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at='2025-08-13T22:44:58.035731Z'
        )
        ```
        """
        if orbit_value is None:
            orbit_value = self._client.orbit
        if is_uuid(orbit_value):
            return await self._get_by_id(orbit_value)
        return await self._get_by_name(orbit_value)

    async def _get_by_id(self, orbit_id: str) -> Orbit:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits/{orbit_id}"
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
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        async def main():
            orgs = await luml.orbits.list()
        ```

        Example response:
        ```python
        [
            Orbit(
                id="0199c455-21ed-7aba-9fe5-5231611220de",
                name="Default Orbit",
                organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
                bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
                total_members=2,
                total_collections=9,
                created_at='2025-05-21T19:35:17.340408Z',
                updated_at='2025-08-13T22:44:58.035731Z'
            )
        ]
        ```
        """
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits"
        )
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    async def create(self, name: str, bucket_secret_id: str) -> Orbit:
        """Create new orbit in the default organization.

        Args:
            name: Name of the orbit.
            bucket_secret_id: ID of the bucket secret.
                The bucket secret must exist before orbit creation.

        Returns:
            Orbit: Newly created orbit object with generated ID and timestamps.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        async def main():
            orbit = await luml.orbits.create(
                name="ML Models",
                bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
            )
        ```

        Response object:
        ```python
        Orbit(
            id="0199c455-21ed-7aba-9fe5-5231611220de",
            name="Default Orbit",
            organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
            total_members=2,
            total_collections=9,
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at='2025-08-13T22:44:58.035731Z'
        )
        ```
        """
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    async def update(
        self, name: str | None = None, bucket_secret_id: str | None = None
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
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        async def main():
            orbit = await luml.orbits.update(name="New Orbit Name")

            orbit = await luml.orbits.update(
                name="New Orbit Name",
                bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de"
            )
        ```

        Response object:
        ```python
        Orbit(
            id="0199c455-21ed-7aba-9fe5-5231611220de",
            name="Default Orbit",
            organization_id="0199c455-21ec-7c74-8efe-41470e29bae5",
            bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
            total_members=2,
            total_collections=9,
            created_at='2025-05-21T19:35:17.340408Z',
            updated_at='2025-08-13T22:44:58.035731Z'
        )
        ```

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

    async def delete(self, orbit_id: str) -> None:
        """
        Delete orbit by ID.

        Permanently removes the orbit and all its associated data including
        collections, models, and configurations. This action cannot be undone.

        Returns:
            None: No return value on successful deletion.

        Raises:
            LumlAPIError: If try to delete default orbit.

        Example:
        ```python
        luml = AsyncLumlClient(
            api_key="luml_your_key",
        )
        luml.setup_config(
            organization="0199c455-21ec-7c74-8efe-41470e29bae5",
            orbit="0199c455-21ed-7aba-9fe5-5231611220de",
            collection="0199c455-21ee-74c6-b747-19a82f1a1e75"
        )
        async def main():
            await luml.orbits.delete("0199c475-8339-70ec-b032-7b3f5d59fdc1")
        ```

        Warning:
            This operation is irreversible. All collections, models, and data
            within the orbit will be permanently lost. Consider backing up
            important data before deletion.

        """
        if self._client.orbit and orbit_id == self._client.orbit:
            raise LumlAPIError("Default orbit cant be deleted.")

        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{orbit_id}"
        )
