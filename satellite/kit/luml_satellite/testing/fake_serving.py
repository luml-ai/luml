from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from luml_satellite.convergence import ModelDescription
from luml_satellite.wire import Deployment

type HealthStep = bool | Exception
type DescriptionStep = ModelDescription | Exception


@dataclass(frozen=True)
class ServingRegistration:
    deployment: Deployment
    upstream_url: str | None
    description: ModelDescription


class FakeServingPlacement:
    def __init__(self) -> None:
        self.describe_calls: list[tuple[str, str | None]] = []
        self.register_calls: list[ServingRegistration] = []
        self.unregister_calls: list[str] = []
        self.health_calls: list[tuple[str, str | None]] = []
        self.noted_records: list[tuple[str, Deployment]] = []
        self.registered: dict[str, ServingRegistration] = {}
        self.addresses: dict[str, str | None] = {}
        self.register_error: Exception | None = None
        self.unregister_error: Exception | None = None
        self.note_error: Exception | None = None
        self._health_steps: dict[str, deque[HealthStep]] = defaultdict(deque)
        self._description_steps: dict[str, deque[DescriptionStep]] = defaultdict(deque)

    @property
    def router(self) -> None:
        return None

    def script_health(self, deployment_id: str, *steps: HealthStep) -> None:
        self._health_steps[deployment_id].extend(steps)

    def script_description(self, deployment_id: str, *steps: DescriptionStep) -> None:
        self._description_steps[deployment_id].extend(steps)

    async def describe(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> ModelDescription:
        deployment_id = str(deployment.id)
        self.describe_calls.append((deployment_id, upstream_url))
        step = _next(self._description_steps[deployment_id])
        if isinstance(step, Exception):
            raise step
        return step or ModelDescription(
            manifest={"name": deployment.artifact_name},
            schema={"openapi": "3.1.0", "paths": {}},
            reference_profile=None,
        )

    async def register(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
        description: ModelDescription,
    ) -> None:
        if self.register_error is not None:
            raise self.register_error
        registration = ServingRegistration(deployment, upstream_url, description)
        deployment_id = str(deployment.id)
        self.register_calls.append(registration)
        self.registered[deployment_id] = registration

    async def unregister(self, deployment_id: str) -> None:
        self.unregister_calls.append(deployment_id)
        if self.unregister_error is not None:
            raise self.unregister_error
        self.registered.pop(deployment_id, None)

    def address(self, deployment: Deployment, *, upstream_url: str | None) -> str | None:
        deployment_id = str(deployment.id)
        return self.addresses.get(deployment_id, f"/deployments/{deployment_id}")

    async def check_health(
        self,
        deployment: Deployment,
        *,
        upstream_url: str | None,
    ) -> bool:
        deployment_id = str(deployment.id)
        self.health_calls.append((deployment_id, upstream_url))
        step = _next(self._health_steps[deployment_id])
        if isinstance(step, Exception):
            raise step
        return True if step is None else step

    def note_platform_record(self, deployment_id: str, record: Deployment) -> None:
        if self.note_error is not None:
            raise self.note_error
        self.noted_records.append((deployment_id, record))

    def is_registered(self, deployment_id: str) -> bool:
        return deployment_id in self.registered


def model_description(
    *,
    manifest: Mapping[str, Any] | None = None,
    schema: Mapping[str, Any] | None = None,
    reference_profile: Mapping[str, Any] | None = None,
) -> ModelDescription:
    return ModelDescription(
        manifest=manifest,
        schema=schema,
        reference_profile=reference_profile,
    )


def _next[Step](steps: deque[Step]) -> Step | None:
    return steps.popleft() if steps else None
