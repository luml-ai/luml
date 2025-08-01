from typing import TYPE_CHECKING

from .._types import Orbit
from .._utils import find_by_name

if TYPE_CHECKING:
    from .._client import AsyncDataForceClient, DataForceClient


class OrbitResource:
    def __init__(self, client: "DataForceClient") -> None:
        self._client = client

    def get(self, organization_id: int, orbit_id: int) -> Orbit:
        response = self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}"
        )
        return Orbit.model_validate(response)

    def get_by_name(self, organization_id: int, name: str) -> Orbit:
        return find_by_name(self.list(organization_id), name)

    def list(self, organization_id: int) -> list[Orbit]:
        response = self._client.get(f"/organizations/{organization_id}/orbits")
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    def create(self, organization_id: int, name: str, bucket_secret_id: int) -> Orbit:
        response = self._client.post(
            f"/organizations/{organization_id}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    def update(
        self,
        organization_id: int,
        orbit_id: int,
        name: str | None = None,
        bucket_secret_id: int | None = None,
    ) -> Orbit:
        response = self._client.patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}",
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

    async def get(self, organization_id: int, orbit_id: int) -> Orbit:
        response = await self._client.get(
            f"/organizations/{organization_id}/orbits/{orbit_id}"
        )
        return Orbit.model_validate(response)

    async def get_by_name(self, organization_id: int, name: str) -> Orbit:
        return find_by_name(await self.list(organization_id), name)

    async def list(self, organization_id: int) -> list[Orbit]:
        response = await self._client.get(f"/organizations/{organization_id}/orbits")
        if response is None:
            return []
        return [Orbit.model_validate(orbit) for orbit in response]

    async def create(
        self, organization_id: int, name: str, bucket_secret_id: int
    ) -> Orbit:
        response = await self._client.post(
            f"/organizations/{organization_id}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit.model_validate(response)

    async def update(
        self,
        organization_id: int,
        orbit_id: int,
        name: str | None = None,
        bucket_secret_id: int | None = None,
    ) -> Orbit:
        response = await self._client.patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}",
            json=self._client.filter_none(
                {
                    "name": name,
                    "bucket_secret_id": bucket_secret_id,
                }
            ),
        )
        return Orbit.model_validate(response)

    async def delete(self, organization_id: int, orbit_id: int) -> None:
        return await self._client.delete(
            f"/organizations/{organization_id}/orbits/{orbit_id}"
        )
