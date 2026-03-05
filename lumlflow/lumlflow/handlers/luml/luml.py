from lumlflow.handlers.luml.base_luml import BaseLumlHandler
from lumlflow.infra.exceptions import ApplicationError
from lumlflow.schemas.luml import (
    Orbit,
    Organization,
    PaginatedCollections,
)
from lumlflow.settings import config


class LumlHandler(BaseLumlHandler):
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        super().__init__(db_path)

    def get_luml_organizations(self) -> list[Organization]:
        luml = self._get_luml_client()
        try:
            return luml.organizations.list()
        except Exception as e:
            raise ApplicationError(f"Failed to get luml organizations: {str(e)}") from e

    def get_luml_orbits(self, organization_id: str) -> list[Orbit]:
        luml = self._get_luml_client(organization_id)
        try:
            return luml.orbits.list()
        except Exception as e:
            raise ApplicationError(f"Failed to get luml orbits: {str(e)}") from e

    def get_luml_collections(
        self,
        organization_id: str,
        orbit_id: str,
        start_after: str | None = None,
        limit: int = 50,
        search: str | None = None,
    ) -> PaginatedCollections:
        luml = self._get_luml_client(organization_id, orbit_id)
        try:
            result = luml.collections.list(
                start_after=start_after, limit=limit, search=search
            )
        except Exception as e:
            raise ApplicationError(f"Failed to get luml collections: {str(e)}") from e
        return PaginatedCollections.model_validate(result.model_dump())
