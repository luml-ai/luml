from luml.api._client import LumlClient
from luml.api._exceptions import ResourceNotFoundError
from luml.experiments.backends.sqlite import SQLiteBackend

from lumlflow.handlers.auth import AuthHandler
from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.infra.progress_store import progress_store
from lumlflow.schemas.luml import (
    Artifact,
    Orbit,
    Organization,
    PaginatedCollections,
    UploadArtifactInput,
)
from lumlflow.settings import config


class LumlHandler:
    __auth = AuthHandler()

    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        self.db = SQLiteBackend(db_path)

    def _get_luml_client(
        self,
        organization_id: str | None = None,
        orbit_id: str | None = None,
        collection_id: str | None = None,
    ) -> LumlClient:
        creds = self.__auth.get_stored_credentials()
        if not creds.api_key:
            raise ApplicationError(status_code=401, message="API key not configured")
        try:
            return LumlClient(
                base_url=config.LUML_BASE_URL,
                api_key=creds.api_key,
                organization=organization_id,
                orbit=orbit_id,
                collection=collection_id,
            )
        except ResourceNotFoundError as e:
            raise ApplicationError(str(e), status_code=422) from e

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

    def upload_model_artifact(
        self, artifact: UploadArtifactInput, job_id: str
    ) -> Artifact:
        model = self.db.get_model(artifact.model_id)

        if not model:
            raise NotFound("Model not found")
        if not model.path:
            raise ApplicationError("Model has no file path", status_code=422)

        luml = self._get_luml_client(artifact.organization_id, artifact.orbit_id)

        def on_progress(uploaded: int, total: int) -> None:
            progress_store.update_progress(job_id, uploaded, total)

        try:
            result = luml.artifacts.upload(
                file_path=str(self.db.base_path / model.path),
                name=artifact.name or model.name,
                description=artifact.description,
                tags=artifact.tags,
                collection_id=artifact.collection_id,
                on_progress=on_progress,
            )
        except Exception as e:
            progress_store.set_error(job_id, str(e))
            raise ApplicationError(f"Failed to upload artifact: {str(e)}") from e

        progress_store.set_complete(job_id, result.model_dump())
        return Artifact.model_validate(result.model_dump())
