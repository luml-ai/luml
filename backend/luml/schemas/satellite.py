import json
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    computed_field,
    field_validator,
)

from luml.schemas.base import BaseOrmConfig

DEPLOY_CAPABILITY = "deploy"
MONITORING_CAPABILITY = "monitoring"
SATELLITE_API_VERSION = 1
MAX_OPENAPI_DOCUMENT_SIZE_BYTES = 2 * 1024 * 1024
RESERVED_CAPABILITIES = frozenset({DEPLOY_CAPABILITY, MONITORING_CAPABILITY})
SUPPORTED_CAPABILITY_DECLARATION_VERSIONS: dict[str, frozenset[int]] = {
    DEPLOY_CAPABILITY: frozenset({1}),
    MONITORING_CAPABILITY: frozenset({1}),
}
SUPPORTED_CAPABILITY_API_VERSIONS: dict[str, frozenset[int]] = {
    DEPLOY_CAPABILITY: frozenset({1}),
    MONITORING_CAPABILITY: frozenset({1}),
}

DEPLOY_FACETS = ["satellite", "deployment"]
MONITORING_FACETS = ["deployment:monitoring"]

_CUSTOM_CAPABILITY_PATTERN = re.compile(r"custom\.[a-z0-9_]+")
_FACET_LEVELS = frozenset({"satellite", "deployment"})
_RESERVED_FACETS: dict[str, frozenset[str]] = {
    DEPLOY_CAPABILITY: frozenset(DEPLOY_FACETS),
    MONITORING_CAPABILITY: frozenset(MONITORING_FACETS),
}

CapabilityVersion = Annotated[int, Field(strict=True, gt=0)]


class MonitoringFeature(StrEnum):
    RUNTIME = "runtime"
    TRACES = "traces"
    ALERTS = "alerts"
    DATA_QUALITY = "data_quality"
    FEATURE_DRIFT = "feature_drift"
    OUTPUT_DRIFT = "output_drift"
    MULTIVARIATE_DRIFT = "multivariate_drift"


MONITORING_FEATURES = [feature.value for feature in MonitoringFeature]


class CapabilityEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: CapabilityVersion
    api_versions: list[CapabilityVersion] = Field(default_factory=list)
    facets: list[str] = Field(default_factory=list)


class DeployCapabilityV1(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: Literal[1]
    api_versions: list[CapabilityVersion] = Field(default_factory=lambda: [1])
    facets: list[str] = Field(default_factory=lambda: DEPLOY_FACETS.copy())
    supported_variants: list[str] = Field(default_factory=list)
    supported_tags_combinations: list[list[str]] | None = None
    extra_fields_form_spec: list[dict[str, Any]] = Field(default_factory=list)


class MonitoringCapabilityV1(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: Literal[1]
    api_versions: list[CapabilityVersion] = Field(default_factory=lambda: [1])
    facets: list[str] = Field(default_factory=lambda: MONITORING_FACETS.copy())
    features: list[MonitoringFeature] = Field(
        default_factory=lambda: list(MonitoringFeature)
    )


_CAPABILITY_MODELS: dict[str, dict[int, type[BaseModel]]] = {
    DEPLOY_CAPABILITY: {1: DeployCapabilityV1},
    MONITORING_CAPABILITY: {1: MonitoringCapabilityV1},
}


class CapabilityValidationError(ValueError):
    pass


def _validation_error_message(capability: str, error: ValidationError) -> str:
    detail = error.errors(include_url=False)[0]
    location = ".".join(str(part) for part in detail["loc"])
    return f"Invalid capability '{capability}' field '{location}': {detail['msg']}"


def _validate_capability_name(capability: str) -> None:
    if capability in RESERVED_CAPABILITIES:
        return
    if _CUSTOM_CAPABILITY_PATTERN.fullmatch(capability):
        return
    raise CapabilityValidationError(f"Invalid capability '{capability}'")


def _validate_facets(
    capability: str,
    facets: list[str],
    *,
    known_reserved_version: bool = False,
) -> None:
    is_custom = capability not in RESERVED_CAPABILITIES
    for facet in facets:
        level, separator, name = facet.partition(":")
        if level not in _FACET_LEVELS or (separator and (not name or ":" in name)):
            raise CapabilityValidationError(
                f"Invalid facet '{facet}' for capability '{capability}'"
            )

        if is_custom:
            if not separator or name != capability:
                raise CapabilityValidationError(
                    f"Invalid facet '{facet}' for capability '{capability}'"
                )
        elif name.startswith("custom.") or (
            known_reserved_version and facet not in _RESERVED_FACETS[capability]
        ):
            raise CapabilityValidationError(
                f"Invalid facet '{facet}' for capability '{capability}'"
            )


def normalize_capabilities(
    capabilities: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for capability, declaration in capabilities.items():
        _validate_capability_name(capability)
        try:
            envelope = CapabilityEnvelope.model_validate(declaration)
        except ValidationError as error:
            raise CapabilityValidationError(
                _validation_error_message(capability, error)
            ) from error

        capability_model = _CAPABILITY_MODELS.get(capability, {}).get(envelope.version)
        if capability_model is None:
            _validate_facets(capability, envelope.facets)
            normalized[capability] = declaration.copy()
            continue

        try:
            typed_declaration = capability_model.model_validate(declaration)
        except ValidationError as error:
            raise CapabilityValidationError(
                _validation_error_message(capability, error)
            ) from error

        normalized_declaration = typed_declaration.model_dump(mode="json")
        _validate_facets(
            capability,
            normalized_declaration["facets"],
            known_reserved_version=True,
        )
        normalized[capability] = normalized_declaration

    return normalized


def get_present_capabilities(
    capabilities: dict[str, dict[str, Any]],
) -> list[str]:
    present: list[str] = []
    for capability, declaration in capabilities.items():
        if capability not in RESERVED_CAPABILITIES:
            present.append(capability)
            continue

        version = declaration.get("version")
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version not in SUPPORTED_CAPABILITY_DECLARATION_VERSIONS[capability]
        ):
            continue
        api_versions = declaration.get("api_versions", [])
        if not isinstance(api_versions, list):
            continue
        if any(
            isinstance(api_version, int)
            and not isinstance(api_version, bool)
            and api_version in SUPPORTED_CAPABILITY_API_VERSIONS[capability]
            for api_version in api_versions
        ):
            present.append(capability)
    return present


class SatelliteTaskType(StrEnum):
    DEPLOY = "deploy"
    UNDEPLOY = "undeploy"
    RECONCILE = "reconcile"


class SatelliteTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SatelliteStatus(StrEnum):
    ACTIVE = "active"  # green
    INACTIVE = "inactive"  # red
    ERROR = "error"  # orange


class KitInfo(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=255)
    kind: str = Field(min_length=1, max_length=255)
    api_version: int = Field(strict=True, ge=1)


class Satellite(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    name: str
    description: str | None = None
    base_url: str | None = None
    paired: bool
    capabilities: dict[str, dict[str, Any]]
    slug: str | None = None
    kit_info: KitInfo | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def present_capabilities(self) -> list[str]:
        return get_present_capabilities(self.capabilities)

    @computed_field
    def status(self) -> SatelliteStatus:
        if not self.paired or self.last_seen_at is None:
            return SatelliteStatus.INACTIVE

        if self.last_seen_at is None:
            return SatelliteStatus.ERROR

        time_diff = datetime.now(UTC) - self.last_seen_at
        if time_diff > timedelta(minutes=20):
            return SatelliteStatus.ERROR

        return SatelliteStatus.ACTIVE


class SatelliteCreateIn(BaseModel, BaseOrmConfig):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class SatelliteCreate(BaseModel, BaseOrmConfig):
    orbit_id: UUID
    api_key_hash: str
    name: str
    description: str | None = None


class SatellitePairIn(BaseModel):
    base_url: HttpUrl | None = None
    capabilities: dict[str, dict[str, Any]]
    slug: str | None = None
    openapi: dict[str, Any] | None = None
    kit: KitInfo | None = None

    @field_validator("openapi")
    @classmethod
    def validate_openapi_size(
        cls, openapi: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if openapi is None:
            return None

        try:
            encoded = json.dumps(
                openapi,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        except (TypeError, ValueError) as error:
            raise ValueError("OpenAPI document must be a JSON object") from error

        if len(encoded) > MAX_OPENAPI_DOCUMENT_SIZE_BYTES:
            raise ValueError("OpenAPI document must not exceed 2 MB")
        return openapi


class SatellitePair(BaseModel, BaseOrmConfig):
    id: UUID
    base_url: str | None
    capabilities: dict[str, dict[str, Any]]
    slug: str | None = None
    openapi: dict[str, Any] | None = None
    kit_info: KitInfo | None = None
    paired: bool = True
    last_seen_at: datetime


class SatelliteContract(BaseModel):
    api_version: Literal[1] = 1
    openapi: dict[str, Any]


class SatelliteUpdateIn(BaseModel, BaseOrmConfig):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name", mode="before")
    @classmethod
    def reject_null_name(cls, value: Any) -> Any:  # noqa: ANN401
        if value is None:
            raise ValueError("name cannot be null; omit it instead")
        return value


class SatelliteUpdate(BaseModel, BaseOrmConfig):
    id: UUID
    name: str | None = None
    description: str | None = None


class SatelliteRegenerateApiKey(BaseModel, BaseOrmConfig):
    id: UUID
    api_key_hash: str


class SatelliteQueueTask(BaseModel, BaseOrmConfig):
    id: UUID
    satellite_id: UUID
    orbit_id: UUID
    type: SatelliteTaskType
    payload: dict[str, Any]
    status: SatelliteTaskStatus
    scheduled_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SatelliteCreateOut(BaseModel, BaseOrmConfig):
    satellite: Satellite
    api_key: str


class SatelliteTaskUpdateIn(BaseModel):
    status: SatelliteTaskStatus
    result: dict[str, Any] | None = None
