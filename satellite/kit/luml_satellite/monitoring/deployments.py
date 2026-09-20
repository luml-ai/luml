import asyncio
import logging
import time
from collections.abc import Callable, Iterable
from typing import Any, Protocol
from uuid import UUID

import httpx

from luml_satellite.monitoring.compute.models import (
    LocalDeployment,
    MonitoredDeployment,
    monitored_deployments,
)
from luml_satellite.monitoring.dashboard.profile import profile_status
from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import Deployment, PlatformClient
from luml_satellite.workload import DeploymentMetadata

logger = logging.getLogger("luml_satellite.monitoring")


class DeploymentSource(Protocol):
    async def deployments(self) -> list[MonitoredDeployment]: ...

    async def is_hosted(self, deployment_id: UUID) -> bool: ...

    async def local_deployment(self, deployment_id: UUID) -> LocalDeployment | None: ...


class ServedDeploymentSource:
    def __init__(self, provider: Callable[[], Iterable[LocalDeployment]]) -> None:
        self._provider = provider

    async def deployments(self) -> list[MonitoredDeployment]:
        return monitored_deployments(self._provider())

    async def is_hosted(self, deployment_id: UUID) -> bool:
        return await self.local_deployment(deployment_id) is not None

    async def local_deployment(self, deployment_id: UUID) -> LocalDeployment | None:
        expected = str(deployment_id)
        return next(
            (deployment for deployment in self._provider() if deployment.deployment_id == expected),
            None,
        )


class PlatformDeploymentSource:
    def __init__(
        self,
        platform: PlatformClient,
        sidecar_url_template: str,
        token_deriver: TokenDeriver,
        *,
        refresh_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if refresh_seconds <= 0:
            raise ValueError("refresh_seconds must be greater than zero")
        self._platform = platform
        self._sidecar_url_template = sidecar_url_template
        self._tokens = token_deriver
        self._refresh_seconds = refresh_seconds
        self._client = client
        self._owns_client = client is None
        self._clock = clock
        self._cached: list[MonitoredDeployment] | None = None
        self._local: dict[str, LocalDeployment] = {}
        self._hosted: set[str] = set()
        self._refresh_at = 0.0
        self._lock = asyncio.Lock()

    async def deployments(self) -> list[MonitoredDeployment]:
        if self._cached is not None and self._clock() < self._refresh_at:
            return list(self._cached)
        async with self._lock:
            if self._cached is not None and self._clock() < self._refresh_at:
                return list(self._cached)
            await self._refresh()
            return list(self._cached or [])

    async def is_hosted(self, deployment_id: UUID) -> bool:
        await self.deployments()
        return str(deployment_id) in self._hosted

    async def local_deployment(self, deployment_id: UUID) -> LocalDeployment | None:
        await self.deployments()
        return self._local.get(str(deployment_id))

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _refresh(self) -> None:
        try:
            records = await self._platform.list_deployments()
            deployments = [
                deployment
                for record in records
                if (deployment := _parse_deployment(record)) is not None
                and deployment.status == "active"
                and deployment.monitoring_mode.strip().lower() == "full"
            ]
            loaded = await asyncio.gather(
                *(self._load_deployment(deployment) for deployment in deployments)
            )
        except Exception:
            if self._cached is None:
                raise
            logger.warning("Failed to refresh monitoring deployments", exc_info=True)
            self._refresh_at = self._clock() + self._refresh_seconds
            return
        self._cached = [monitored for monitored, _local in loaded]
        self._local = {local.deployment_id: local for _monitored, local in loaded}
        self._hosted = set(self._local)
        self._refresh_at = self._clock() + self._refresh_seconds

    async def _load_deployment(
        self, deployment: Deployment
    ) -> tuple[MonitoredDeployment, LocalDeployment]:
        profile, manifest = await asyncio.gather(
            self._sidecar_json(deployment.id, "reference_profile"),
            self._sidecar_json(deployment.id, "manifest"),
        )
        status = profile_status(profile)
        monitored = MonitoredDeployment(
            deployment_id=deployment.id,
            profile=profile,
            profile_status=status,
        )
        local = LocalDeployment(
            deployment_id=deployment.id,
            manifest=manifest,
            reference_profile=profile,
            profile_status=status,
            monitoring_enabled=True,
            metadata=DeploymentMetadata.from_platform(deployment.model_dump()),
        )
        return monitored, local

    async def _sidecar_json(self, deployment_id: str, path: str) -> dict[str, Any] | None:
        base = self._sidecar_url_template.format(
            deployment_id=deployment_id,
            id=deployment_id,
        ).rstrip("/")
        token = self._tokens.companion_token(deployment_id)
        try:
            response = await self._get_client().get(
                f"{base}/{path}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError, ValueError:
            logger.warning("Failed to read sidecar %s for %s", path, deployment_id)
            return None
        if not isinstance(payload, dict):
            return None
        nested = payload.get(path)
        return nested if isinstance(nested, dict) else payload

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client


def _parse_deployment(record: object) -> Deployment | None:
    try:
        return Deployment.model_validate(record)
    except ValueError:
        logger.warning("Ignoring invalid deployment from the platform")
        return None
