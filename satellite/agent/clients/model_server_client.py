import asyncio
import logging
from contextlib import suppress
from typing import Self

import httpx

from agent.schemas.deployments import Schemas
from agent.settings import config as config_settings

logger = logging.getLogger(__name__)


class ModelServerClient:
    def __init__(self, timeout: float = 45.0) -> None:
        self._timeout: float | httpx.Timeout = timeout
        self._session: httpx.AsyncClient | None = None
        self._headers = {
            "Content-Type": "application/json",
        }

    async def __aenter__(self) -> Self:
        self._session = httpx.AsyncClient(timeout=self._timeout, headers=self._headers)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    @staticmethod
    def _url(deployment_id: str) -> str:
        return f"http://sat-{deployment_id}:{config_settings.MODEL_SERVER_PORT}"

    async def compute(
        self,
        deployment_id: str,
        body: dict,
    ) -> dict:
        assert self._session is not None
        url = f"{self._url(deployment_id)}/compute"
        response = await self._session.post(url, json=body)
        response.raise_for_status()
        return response.json()

    async def is_healthy(self, deployment_id: str, timeout: int = 120) -> bool:
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

    async def get_openapi_schema(self, deployment_id: str) -> dict | None:
        assert self._session is not None
        with suppress(Exception):
            response = await self._session.get(f"{self._url(deployment_id)}/openapi.json")
            if response.status_code == 200:
                return response.json()

        return None

    async def get_manifest(self, deployment_id: str) -> dict | None:
        assert self._session is not None
        try:
            response = await self._session.get(f"{self._url(deployment_id)}/manifest")
            if response.status_code == 200:
                return response.json()
        except Exception as error:
            logger.info(f"Error getting manifest {error}.")
        return None

    async def get_schemas(self, deployment_id: str) -> Schemas | None:
        assert self._session is not None
        try:
            response = await self._session.get(f"{self._url(deployment_id)}/schemas")
            if response.status_code == 200:
                return Schemas.model_validate(response.json())
        except Exception as error:
            logger.info(f"Error getting schemas {error}.")
        return None
