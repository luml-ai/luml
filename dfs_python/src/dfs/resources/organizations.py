from .._resource import APIResource
from .._types import Organization


class OrganizationResource(APIResource):
    async def list(self) -> list[Organization]:
        response = await self._get("/users/me/organizations")
        if response is None:
            return []
        return [Organization(**org) for org in response]

    # async def create(self, name: str, logo: str | None = None) -> Organization:
    #     response = await self._post("/organizations", json={"name": name, "logo": logo})
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
