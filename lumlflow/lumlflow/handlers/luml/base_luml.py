import httpx
from luml.experiments.tracker import ExperimentTracker
from luml_api._client import LumlClient
from luml_api._exceptions import LumlAPIError, ResourceNotFoundError

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
            # The client validates its defaults against the API as it is
            # built, so a LUML that is not answering fails right here.
            return LumlClient(
                base_url=config.LUML_BASE_URL,
                api_key=creds.api_key,
                organization=organization_id,
                orbit=orbit_id,
                collection=collection_id,
            )
        except ResourceNotFoundError as e:
            raise ApplicationError(str(e), status_code=422) from e
        except httpx.TransportError as e:
            raise unreachable_luml(e) from e
        except LumlAPIError as e:
            raise luml_refused(e) from e


def luml_refused(failure: LumlAPIError) -> ApplicationError:
    """LUML answered, but not as an API: a wrong host (an HTML page where
    JSON was due), a rejected key, a server fault. The message keeps the
    address, which is the first thing to check."""
    return ApplicationError(
        f"LUML at {config.LUML_BASE_URL} did not answer as expected: "
        f"{failure.message if hasattr(failure, 'message') else failure}",
        status_code=502,
    )


def unreachable_luml(failure: httpx.TransportError) -> ApplicationError:
    """A LUML that cannot be reached is a configuration or network fact, not
    a server fault: name the address so the reader can check the setting."""
    reason = str(failure) or type(failure).__name__
    return ApplicationError(
        f"LUML at {config.LUML_BASE_URL} is not reachable ({reason}). "
        "Check LUML_BASE_URL or start the LUML backend.",
        status_code=503,
    )
