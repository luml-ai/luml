"""Base abstractions for LUML Platform client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

_T = TypeVar("_T", bound="BasePlatformClient")


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
    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """Get deployment details from the platform.

        Args:
            deployment_id: The unique identifier of the deployment.

        Returns:
            Deployment data dictionary.

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
