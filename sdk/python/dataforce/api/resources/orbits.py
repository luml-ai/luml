from typing import TYPE_CHECKING

from .._types import Orbit
from .._utils import find_by_name

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class OrbitResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, orbit_value: int | str | None = None) -> Orbit | None:
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

    def _get_by_name(self, name: str) -> Orbit:
        return find_by_name(self.list(), name)

    def list(self) -> list[Orbit]:
        response = self._client.get(
            f"/organizations/{self._client.organization}/orbits"
        )
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    def create(self, name: str, bucket_secret_id: int) -> Orbit:
        response = self._client.post(
            f"/organizations/{self._client.organization}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    def update(
        self, name: str | None = None, bucket_secret_id: int | None = None
    ) -> Orbit:
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

    def delete(self, organization_id: int, orbit_id: int) -> None:
        return self._client.delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}"
        )


class AsyncOrbitResource:
    def __init__(self, client: "AsyncDataForceClient") -> None:
        self._client = client

    async def get(self, orbit_value: int | str | None = None) -> Orbit | None:
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

    async def _get_by_name(self, name: str) -> Orbit:
        return find_by_name(await self.list(), name)

    async def list(self) -> list[Orbit]:
        response = await self._client.get(
            f"/organizations/{self._client.organization}/orbits"
        )
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    async def create(self, name: str, bucket_secret_id: int) -> Orbit:
        response = await self._client.post(
            f"/organizations/{self._client.organization}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    async def update(
        self, name: str | None = None, bucket_secret_id: int | None = None
    ) -> Orbit:
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

    async def delete(self) -> None:
        return await self._client.delete(
            f"/organizations/{self._client.organization}/orbits/{self._client.orbit}"
        )
