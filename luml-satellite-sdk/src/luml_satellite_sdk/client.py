"""Base abstractions and implementations for LUML Platform client."""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast
from uuid import UUID

import httpx
from cashews import cache

from luml_satellite_sdk.schemas import (
    Deployment,
    DeploymentUpdate,
    ErrorMessage,
    SatelliteTaskStatus,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

logger = logging.getLogger("satellite")

_T = TypeVar("_T", bound="BasePlatformClient")

cache.setup("mem://")

_AUTHORIZATION_CACHE_TTL_SECONDS = 60
_SECRETS_CACHE_TTL_SECONDS = 60


class BasePlatformClient(ABC):
    """Abstract base class for LUML platform API client implementations.

    The platform client handles all communication between the satellite
    and the LUML platform, including authentication, task management,
    and status updates.

    Implementations should handle HTTP communication, authentication,
    and error handling for platform API calls.
    """

    @abstractmethod
    async def __aenter__(self: _T) -> _T:
        """Enter async context manager.

        Initialize the HTTP client session and any required resources.

        Returns:
            Self for use in async with statements.
        """
        ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager.

        Clean up HTTP client session and resources.
        """
        ...

    @abstractmethod
    async def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """List tasks from the platform queue.

        Args:
            status: Optional filter for task status (e.g., "pending", "running").

        Returns:
            List of task dictionaries from the platform.

        Raises:
            Exception: If the API request fails.
        """
        ...

    @abstractmethod
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update the status of a task on the platform.

        Args:
            task_id: The unique identifier of the task.
            status: The new status (e.g., "running", "completed", "failed").
            result: Optional result data to include with the status update.

        Returns:
            The updated task data from the platform.

        Raises:
            Exception: If the API request fails.
        """
        ...

    @abstractmethod
    async def pair_satellite(
        self,
        base_url: str,
        capabilities: dict[str, Any],
        slug: str | None = None,
    ) -> dict[str, Any]:
        """Register/pair the satellite with the platform.

        Args:
            base_url: The base URL where this satellite can be reached.
            capabilities: Dictionary of capabilities this satellite supports.
            slug: Optional unique identifier/slug for this satellite.

        Returns:
            Pairing response data from the platform.

        Raises:
            Exception: If the pairing request fails.
        """
        ...

    @abstractmethod
    async def get_deployment(self, deployment_id: str) -> Deployment:
        """Get deployment details from the platform.

        Args:
            deployment_id: The unique identifier of the deployment.

        Returns:
            Deployment model instance.

        Raises:
            Exception: If the API request fails.
        """
        ...

    @abstractmethod
    async def update_deployment_status(
        self,
        deployment_id: str,
        status: str,
    ) -> dict[str, Any]:
        """Update the status of a deployment.

        Args:
            deployment_id: The unique identifier of the deployment.
            status: The new deployment status.

        Returns:
            The updated deployment data.

        Raises:
            Exception: If the API request fails.
        """
        ...


class PlatformClient(BasePlatformClient):
    """Concrete implementation of the LUML platform API client.

    This client handles all HTTP communication with the LUML platform,
    including authentication via bearer token, task polling, status updates,
    deployment management, and secrets retrieval.

    Usage:
        async with PlatformClient(base_url, token) as client:
            tasks = await client.list_tasks(status=SatelliteTaskStatus.PENDING)
    """

    def __init__(self, base_url: str, token: str, timeout_s: float = 30.0) -> None:
        """Initialize the platform client.

        Args:
            base_url: The base URL of the LUML platform API.
            token: Bearer token for authentication (API key).
            timeout_s: Request timeout in seconds (default: 30.0).
        """
        self.base_url = base_url.rstrip("/")
        self._timeout: float | httpx.Timeout = timeout_s
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._session: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        """Enter async context manager and create HTTP session."""
        self._session = httpx.AsyncClient(timeout=self._timeout, headers=self._headers)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager and close HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    def _url(self, path: str) -> str:
        """Build full URL from path."""
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    async def list_tasks(
        self, status: SatelliteTaskStatus | str | None = None
    ) -> list[dict[str, Any]]:
        """List tasks from the platform queue.

        Args:
            status: Optional filter for task status.

        Returns:
            List of task dictionaries from the platform.
        """
        assert self._session is not None
        status_value = (
            status.value if isinstance(status, SatelliteTaskStatus) else status
        )
        params = {"status": status_value if status_value else None}
        r = await self._session.get(self._url("/satellites/v1/tasks"), params=params)
        r.raise_for_status()
        return cast(list[dict[str, Any]], r.json())

    async def update_task_status(
        self,
        task_id: str,
        status: SatelliteTaskStatus | str,
        result: ErrorMessage | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update the status of a task on the platform.

        Args:
            task_id: The unique identifier of the task.
            status: The new status.
            result: Optional result data to include with the status update.

        Returns:
            The updated task data from the platform.
        """
        assert self._session is not None
        status_value = (
            status.value if isinstance(status, SatelliteTaskStatus) else status
        )
        body: dict[str, Any] = {"status": status_value}
        if result is not None:
            body["result"] = (
                result
                if isinstance(result, dict)
                else result.model_dump(exclude_unset=True)
            )
        r = await self._session.post(
            self._url(f"/satellites/v1/tasks/{task_id}/status"), json=body
        )
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def update_deployment_status(
        self,
        deployment_id: str,
        status: str,
    ) -> dict[str, Any]:
        """Update the status of a deployment.

        Args:
            deployment_id: The unique identifier of the deployment.
            status: The new deployment status.

        Returns:
            The updated deployment data.
        """
        assert self._session is not None
        r = await self._session.patch(
            self._url(f"/satellites/v1/deployments/{deployment_id}/status"),
            json={"status": status},
        )
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def delete_deployment(self, deployment_id: UUID) -> None:
        """Delete a deployment from the platform.

        Args:
            deployment_id: The unique identifier of the deployment.
        """
        assert self._session is not None
        r = await self._session.delete(
            self._url(f"/satellites/v1/deployments/{deployment_id}")
        )
        r.raise_for_status()

    async def pair_satellite(
        self, base_url: str, capabilities: dict[str, Any], slug: str | None = None
    ) -> dict[str, Any]:
        """Register/pair the satellite with the platform.

        Args:
            base_url: The base URL where this satellite can be reached.
            capabilities: Dictionary of capabilities this satellite supports.
            slug: Optional unique identifier/slug for this satellite.

        Returns:
            Pairing response data from the platform.
        """
        assert self._session is not None
        r = await self._session.post(
            self._url("/satellites/v1/pair"),
            json={"base_url": base_url, "capabilities": capabilities, "slug": slug},
        )
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def authorize_inference_access(self, api_key: str) -> bool:
        """Check if an API key has inference access.

        Args:
            api_key: The API key to validate.

        Returns:
            True if authorized, False otherwise.
        """
        assert self._session is not None
        r = await self._session.post(
            self._url("/satellites/v1/deployments/inference-access"),
            json={"api_key": api_key},
        )
        r.raise_for_status()
        data = r.json()
        return bool(data.get("authorized", False))

    async def get_model_artifact_download_url(self, model_artifact_id: UUID) -> str:
        """Get the download URL for a model artifact.

        Args:
            model_artifact_id: The unique identifier of the model artifact.

        Returns:
            The download URL for the model artifact.
        """
        assert self._session is not None
        r = await self._session.get(
            self._url(
                f"/satellites/v1/model_artifacts/{model_artifact_id}/download-url"
            )
        )
        r.raise_for_status()
        data = r.json()
        return str(data.get("url", ""))

    async def get_model_artifact(
        self, model_artifact_id: UUID
    ) -> tuple[dict[str, Any], str]:
        """Get model artifact details and download URL.

        Args:
            model_artifact_id: The unique identifier of the model artifact.

        Returns:
            Tuple of (model data dict, download URL).
        """
        assert self._session is not None
        r = await self._session.get(
            self._url(f"/satellites/v1/model_artifacts/{model_artifact_id}")
        )
        r.raise_for_status()
        data = r.json()
        return cast(dict[str, Any], data.get("model")), str(data.get("url", ""))

    async def get_orbit_secret(self, secret_id: UUID) -> dict[str, Any]:
        """Get a specific orbit secret by ID.

        Args:
            secret_id: The unique identifier of the secret.

        Returns:
            The secret data.
        """
        assert self._session is not None
        r = await self._session.get(self._url(f"/satellites/v1/secrets/{secret_id}"))
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def get_orbit_secrets(self) -> list[dict[str, Any]]:
        """Get all secrets for the orbit.

        Returns:
            List of secret data dictionaries.
        """
        assert self._session is not None
        r = await self._session.get(self._url("/satellites/v1/secrets"))
        r.raise_for_status()
        return cast(list[dict[str, Any]], r.json())

    async def list_deployments(self) -> list[dict[str, Any]]:
        """List all deployments for the satellite.

        Returns:
            List of deployment data dictionaries.
        """
        assert self._session is not None
        r = await self._session.get(self._url("/satellites/v1/deployments"))
        r.raise_for_status()
        return cast(list[dict[str, Any]], r.json())

    async def get_deployment(self, deployment_id: UUID | str) -> Deployment:
        """Get deployment details from the platform.

        Args:
            deployment_id: The unique identifier of the deployment.

        Returns:
            Deployment model instance.
        """
        assert self._session is not None
        r = await self._session.get(
            self._url(f"/satellites/v1/deployments/{deployment_id}")
        )
        r.raise_for_status()
        return Deployment.model_validate(r.json())

    async def update_deployment(
        self, deployment_id: str, deployment: DeploymentUpdate
    ) -> Deployment:
        """Update a deployment on the platform.

        Args:
            deployment_id: The unique identifier of the deployment.
            deployment: The deployment update data.

        Returns:
            The updated Deployment model instance.
        """
        assert self._session is not None
        r = await self._session.patch(
            self._url(f"/satellites/v1/deployments/{deployment_id}"),
            json=deployment.model_dump(exclude_unset=True),
        )
        r.raise_for_status()
        return Deployment.model_validate(r.json())
