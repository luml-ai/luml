import asyncio
from typing import Self

import httpx

from agent.settings import config


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
    def _url(deployment_id: int) -> str:
        return f"http://sat-{deployment_id}:{config.CONTAINER_PORT}"

    async def compute(
        self,
        deployment_id: int,
        body: dict,
    ) -> dict:
        assert self._session is not None
        response = await self._session.post(f"{self._url(deployment_id)}/compute", json=body)
        response.raise_for_status()
        return response.json()

    async def is_healthy(self, deployment_id: int, timeout: int = 45) -> bool:
        assert self._session is not None
        for _ in range(timeout):
            try:
                response = await self._session.get(f"{self._url(deployment_id)}/healthz")
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def get_openapi_schema(self, deployment_id: int) -> dict | None:
        assert self._session is not None
        try:
            response = await self._session.get(f"{self._url(deployment_id)}/openapi.json")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    async def get_manifest(self, deployment_id: int) -> dict | None:
        assert self._session is not None
        try:
            response = await self._session.get(f"{self._url(deployment_id)}/manifest")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None
