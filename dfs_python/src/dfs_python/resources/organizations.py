from .._resource import APIResource


class Organization(APIResource):
    async def create(self, name: str, logo: str | None = None):
        return self._post(
            "/organizations", json={"name": name, "logo": logo}
        )

    async def list(self):
        return self._get("/users/me/organizations")
