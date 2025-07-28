from .._resource import APIResource
from .._types import Orbit


class OrbitResource(APIResource):
    async def get(self, organization_id: int, orbit_id: int) -> Orbit:
        response = await self._get(
            f"/organizations/{organization_id}/orbits/{orbit_id}"
        )
        return Orbit(**response)

    async def list(self, organization_id: int) -> list[Orbit]:
        response = await self._get(f"/organizations/{organization_id}/orbits")
        if response is None:
            return []
        return [Orbit(**orbit) for orbit in response]

    async def create(
        self, organization_id: int, name: str, bucket_secret_id: int
    ) -> Orbit:
        response = await self._post(
            f"/organizations/{organization_id}/orbits",
            json={"name": name, "bucket_secret_id": bucket_secret_id},
        )

        return Orbit(**response)

    async def update(
        self,
        organization_id: int,
        orbit_id: int,
        name: str | None = None,
        bucket_secret_id: int | None = None,
    ) -> Orbit:
        data = self._filter_none(
            {
                "name": name,
                "bucket_secret_id": bucket_secret_id,
            }
        )
        response = await self._patch(
            f"/organizations/{organization_id}/orbits/{orbit_id}",
            json=data,
        )
        return Orbit(**response)

    async def delete(self, organization_id: int, orbit_id: int) -> None:
        return await self._delete(f"/organizations/{organization_id}/orbits/{orbit_id}")
