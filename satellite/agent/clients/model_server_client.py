import asyncio
import json
import logging
from contextlib import suppress
from typing import Self

import httpx

from agent.settings import config as config_settings

logger = logging.getLogger(__name__)


class ModelServerError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


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
        if response.status_code >= 400:
            detail: str
            try:
                payload = response.json()
            except Exception:
                payload = None
            if isinstance(payload, dict) and "error" in payload:
                detail = str(payload["error"])
            elif payload is not None:
                detail = json.dumps(payload)
            else:
                detail = response.text or response.reason_phrase
            raise ModelServerError(response.status_code, detail)
        return response.json()

    async def is_healthy(self, deployment_id: str, timeout: int = 120) -> bool:
        assert self._session is not None
        logger.info(f"Starting health check for {deployment_id}...")

        last_error: Exception | None = None
        for _ in range(timeout):
            try:
                response = await self._session.get(
                    f"{self._url(deployment_id)}/healthz", timeout=5.0
                )
                if response.status_code == 200:
                    return True
            except Exception as e:
                last_error = e
            await asyncio.sleep(1)

        logger.error(
            f"Health check failed for {deployment_id} after {timeout}s. Last error: {last_error}"
        )
        return False

    async def check_health_once(self, deployment_id: str) -> bool:
        assert self._session is not None
        try:
            response = await self._session.get(f"{self._url(deployment_id)}/healthz", timeout=5.0)
            return response.status_code == 200
        except Exception:
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
            logger.warning(f"Error getting manifest for {deployment_id}: {error}")
        return None
