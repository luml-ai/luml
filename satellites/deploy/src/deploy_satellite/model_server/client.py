"""Client for communicating with model server containers."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

import httpx
from typing_extensions import Self

from deploy_satellite.settings import settings

logger = logging.getLogger(__name__)


class ModelServerClient:
    """Async HTTP client for model server containers."""

    def __init__(self, timeout: float = 45.0) -> None:
        """Initialize the model server client.

        Args:
            timeout: Request timeout in seconds.
        """
        self._timeout: float | httpx.Timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._headers = {
            "Content-Type": "application/json",
        }

    async def __aenter__(self) -> Self:
        self._session = httpx.AsyncClient(timeout=self._timeout, headers=self._headers)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    @staticmethod
    def _url(deployment_id: str) -> str:
        """Build the base URL for a deployment's model server."""
        return f"http://sat-{deployment_id}:{settings.model_server_port}"

    async def compute(
        self,
        deployment_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a compute request to the model server.

        Args:
            deployment_id: The deployment ID.
            body: The compute request body.

        Returns:
            The compute response.
        """
        assert self._session is not None
        url = f"{self._url(deployment_id)}/compute"
        response = await self._session.post(url, json=body)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    async def is_healthy(self, deployment_id: str, timeout: int = 120) -> bool:
        """Check if a model server is healthy.

        Args:
            deployment_id: The deployment ID.
            timeout: Number of attempts to wait for health.

        Returns:
            True if the model server is healthy.
        """
        assert self._session is not None
        logger.info(f"Starting health check for {deployment_id}...")

        for _ in range(timeout):
            with suppress(Exception):
                response = await self._session.get(
                    f"{self._url(deployment_id)}/healthz", timeout=5.0
                )
                if response.status_code == 200:
                    return True
            await asyncio.sleep(1)

        logger.error(f"Failed after {timeout} attempts for {deployment_id}")
        return False

    async def get_openapi_schema(self, deployment_id: str) -> dict[str, Any] | None:
        """Get the OpenAPI schema from a model server.

        Args:
            deployment_id: The deployment ID.

        Returns:
            The OpenAPI schema or None if unavailable.
        """
        assert self._session is not None
        with suppress(Exception):
            response = await self._session.get(
                f"{self._url(deployment_id)}/openapi.json"
            )
            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result

        return None

    async def get_manifest(self, deployment_id: str) -> dict[str, Any] | None:
        """Get the manifest from a model server.

        Args:
            deployment_id: The deployment ID.

        Returns:
            The manifest or None if unavailable.
        """
        assert self._session is not None
        try:
            response = await self._session.get(f"{self._url(deployment_id)}/manifest")
            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result
        except Exception as error:
            logger.info(f"Error getting manifest {error}.")
        return None
