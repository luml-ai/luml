from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class RecordingPolicy:
    sample_rate: float = 1.0
    body_max_bytes: int = 65_536
    keep_inputs: bool = True
    keep_outputs: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.sample_rate <= 1:
            raise ValueError("sample_rate must be between 0 and 1")
        if self.body_max_bytes <= 0:
            raise ValueError("body_max_bytes must be greater than zero")

    def captures_bodies(self, random_value: float) -> bool:
        if not 0 <= random_value < 1:
            raise ValueError("random_value must be between 0 inclusive and 1 exclusive")
        return random_value < self.sample_rate and (self.keep_inputs or self.keep_outputs)


class ProfileStatus(StrEnum):
    READY = "ready"
    PLACEHOLDER = "placeholder"
    ABSENT = "absent"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class InferenceOutcome:
    status_code: int
    latency_ms: float
    output: object | None = None
    error: str | None = None
    bodies_sampled: bool = False


class RecordingSession(Protocol):
    @property
    def event_id(self) -> str | None: ...

    @property
    def upstream_headers(self) -> Mapping[str, str]: ...

    async def complete(self, outcome: InferenceOutcome) -> None: ...


class Recorder(Protocol):
    async def start(
        self,
        deployment_id: str,
        inputs: object | None,
        policy: RecordingPolicy,
    ) -> RecordingSession: ...


class NoOpRecordingSession:
    @property
    def event_id(self) -> None:
        return None

    @property
    def upstream_headers(self) -> Mapping[str, str]:
        return {}

    async def complete(self, outcome: InferenceOutcome) -> None:
        return None


class NoOpRecorder:
    async def start(
        self,
        deployment_id: str,
        inputs: object | None,
        policy: RecordingPolicy,
    ) -> RecordingSession:
        return NoOpRecordingSession()


class DeploymentMetadata(BaseModel):
    name: str | None = None
    status: str | None = None
    model_name: str | None = None
    environment: str | None = None
    satellite: str | None = None
    inference_url: str | None = None

    @classmethod
    def from_platform(cls, record: Mapping[str, Any] | None) -> DeploymentMetadata:
        if not record:
            return cls()
        return cls(
            name=record.get("name"),
            status=record.get("status"),
            model_name=record.get("artifact_name") or record.get("model_artifact_name"),
            environment=record.get("orbit_name"),
            satellite=record.get("satellite_name"),
            inference_url=record.get("inference_url"),
        )


@dataclass
class LocalDeployment:
    deployment_id: str
    dynamic_attributes_secrets: dict[str, str] = field(default_factory=dict)
    manifest: dict[str, Any] | None = None
    openapi_schema: dict[str, Any] | None = None
    reference_profile: dict[str, Any] | None = None
    profile_status: ProfileStatus = ProfileStatus.ABSENT
    monitoring_enabled: bool = False
    metadata: DeploymentMetadata = field(default_factory=DeploymentMetadata)
    upstream_url: str | None = None
    recording_policy: RecordingPolicy = field(default_factory=RecordingPolicy)
