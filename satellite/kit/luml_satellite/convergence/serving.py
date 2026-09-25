from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from luml_satellite.wire import Deployment
from luml_satellite.workload import ProfileStatus


@dataclass(frozen=True)
class ModelDescription:
    manifest: Mapping[str, Any] | None = None
    schema: Mapping[str, Any] | None = None
    reference_profile: Mapping[str, Any] | None = None
    profile_status: ProfileStatus = ProfileStatus.ABSENT


class ServingPlacement(Protocol):
    @property
    def router(self) -> object | None: ...

    async def describe(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> ModelDescription: ...

    async def register(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
        description: ModelDescription,
    ) -> None: ...

    async def unregister(self, deployment_id: str) -> None: ...

    def address(self, deployment: Deployment, *, upstream_url: str | None) -> str | None: ...

    async def check_health(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> bool: ...

    def note_platform_record(self, deployment_id: str, record: Deployment) -> None: ...

    def is_registered(self, deployment_id: str) -> bool: ...


class NoServingPlacement:
    def __init__(self) -> None:
        self._registered: set[str] = set()

    @property
    def router(self) -> None:
        return None

    async def describe(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> ModelDescription:
        return ModelDescription()

    async def register(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
        description: ModelDescription,
    ) -> None:
        self._registered.add(str(deployment.id))

    async def unregister(self, deployment_id: str) -> None:
        self._registered.discard(deployment_id)

    def address(self, deployment: Deployment, *, upstream_url: str | None) -> str | None:
        return upstream_url

    async def check_health(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> bool:
        return True

    def note_platform_record(self, deployment_id: str, record: Deployment) -> None:
        return None

    def is_registered(self, deployment_id: str) -> bool:
        return deployment_id in self._registered
