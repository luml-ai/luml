from luml.api._client import LumlClient
from luml.api._exceptions import ResourceNotFoundError
from luml.experiments.tracker import ExperimentTracker

from lumlflow.handlers.auth import AuthHandler
from lumlflow.infra.exceptions import ApplicationError
from lumlflow.settings import config, get_tracker


class BaseLumlHandler:
    __auth = AuthHandler()

    def __init__(self, tracker: ExperimentTracker | None = None) -> None:
        self.tracker = tracker or get_tracker()

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
