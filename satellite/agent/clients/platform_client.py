import logging
from typing import Any, Self
from uuid import UUID

import httpx
from cashews import cache

from agent.schemas import Deployment, DeploymentUpdate, SatelliteTaskStatus

logger = logging.getLogger("satellite")


cache.setup("mem://")

_AUTHORIZATION_CACHE_TTL_SECONDS = 60
_SECRETS_CACHE_TTL_SECONDS = 60


class PlatformClient:
    def __init__(self, base_url: str, token: str, timeout_s: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout: float | httpx.Timeout = timeout_s
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._session: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._session = httpx.AsyncClient(timeout=self._timeout, headers=self._headers)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    async def list_tasks(self, status: SatelliteTaskStatus | None = None) -> list[dict[str, Any]]:
        assert self._session is not None
        params = {"status": status.value if status else None}
        r = await self._session.get(self._url("/satellites/v1/tasks"), params=params)
        r.raise_for_status()
        tasks = r.json()
        return tasks

    async def update_task_status(
        self,
        task_id: str,
        status: SatelliteTaskStatus,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self._session is not None
        body: dict[str, Any] = {"status": status.value}
        if result is not None:
            body["result"] = result
        r = await self._session.post(self._url(f"/satellites/v1/tasks/{task_id}/status"), json=body)
        r.raise_for_status()
        return r.json()

    async def update_deployment_status(
        self,
        deployment_id: str,
        status: str,
    ) -> dict[str, Any]:
        assert self._session is not None
        r = await self._session.patch(
            self._url(f"/satellites/v1/deployments/{deployment_id}/status"),
            json={"status": status},
        )
        r.raise_for_status()
        return r.json()

    async def delete_deployment(self, deployment_id: UUID) -> None:
        assert self._session is not None
        r = await self._session.delete(self._url(f"/satellites/v1/deployments/{deployment_id}"))
        r.raise_for_status()

    async def pair_satellite(
        self, base_url: str, capabilities: dict[str, Any], slug: str | None = None
    ) -> dict[str, Any]:
        assert self._session is not None
        r = await self._session.post(
            self._url("/satellites/v1/pair"),
            json={"base_url": base_url, "capabilities": capabilities, "slug": slug},
        )
        r.raise_for_status()
        return r.json()

    @cache(ttl=_AUTHORIZATION_CACHE_TTL_SECONDS, key="authorize_inference_access:{api_key}")
    async def authorize_inference_access(self, api_key: str) -> bool:
        assert self._session is not None
        r = await self._session.post(
            self._url("/satellites/v1/deployments/inference-access"),
            json={"api_key": api_key},
        )
        r.raise_for_status()
        data = r.json()
        return bool(data.get("authorized", False))

    async def get_model_artifact_download_url(self, model_artifact_id: UUID) -> str:
        assert self._session is not None
        r = await self._session.get(
            self._url(f"/satellites/v1/model_artifacts/{model_artifact_id}/download-url")
        )
        r.raise_for_status()
        data = r.json()
        return str(data.get("url", ""))

    async def get_model_artifact(self, model_artifact_id: UUID) -> tuple[dict, str]:
        assert self._session is not None
        r = await self._session.get(
            self._url(f"/satellites/v1/model_artifacts/{model_artifact_id}")
        )
        r.raise_for_status()
        data = r.json()
        return data.get("model"), str(data.get("url", ""))

    @cache(ttl=_SECRETS_CACHE_TTL_SECONDS, key="get_orbit_secret:{secret_id}")
    async def get_orbit_secret(self, secret_id: UUID) -> dict[str, Any]:
        assert self._session is not None
        r = await self._session.get(self._url(f"/satellites/v1/secrets/{secret_id}"))
        r.raise_for_status()
        return r.json()

    @cache(ttl=_SECRETS_CACHE_TTL_SECONDS, key="get_orbit_secrets")
    async def get_orbit_secrets(self) -> list[dict[str, Any]]:
        assert self._session is not None
        r = await self._session.get(self._url("/satellites/v1/secrets"))
        r.raise_for_status()
        return r.json()

    async def list_deployments(self) -> list[dict[str, Any]]:
        assert self._session is not None
        r = await self._session.get(self._url("/satellites/v1/deployments"))
        r.raise_for_status()
        return r.json()

    async def get_deployment(self, deployment_id: UUID) -> Deployment:
        assert self._session is not None
        r = await self._session.get(self._url(f"/satellites/v1/deployments/{deployment_id}"))
        r.raise_for_status()
        return Deployment.model_validate(r.json())

    async def update_deployment(
        self, deployment_id: str, deployment: DeploymentUpdate
    ) -> Deployment:
        r = await self._session.patch(
            self._url(f"/satellites/v1/deployments/{deployment_id}"),
            json=deployment.model_dump(exclude_unset=True),
        )
        r.raise_for_status()
        return Deployment.model_validate(r.json())
