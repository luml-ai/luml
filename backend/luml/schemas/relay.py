import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
)

from luml.schemas.base import BaseOrmConfig
from luml.schemas.live_session import SessionTokenKind
from luml.schemas.satellite import CapabilityValidationError, CapabilityVersion

RELAY_ONLINE_WINDOW = timedelta(minutes=5)

SESSIONS_CAPABILITY = "sessions"
RESERVED_RELAY_CAPABILITIES = frozenset({SESSIONS_CAPABILITY})
SUPPORTED_RELAY_CAPABILITY_DECLARATION_VERSIONS: dict[str, frozenset[int]] = {
    SESSIONS_CAPABILITY: frozenset({1}),
}
SUPPORTED_RELAY_CAPABILITY_API_VERSIONS: dict[str, frozenset[int]] = {
    SESSIONS_CAPABILITY: frozenset({1}),
}

_CUSTOM_RELAY_CAPABILITY = re.compile(r"custom\.[a-z0-9_]+")

_HOSTNAME_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOSTNAME = re.compile(rf"{_HOSTNAME_LABEL}(?:\.{_HOSTNAME_LABEL})*")
_MAX_HOSTNAME_LENGTH = 253


class RelayStatus(StrEnum):
    ENABLED = "enabled"
    DRAINING = "draining"


class RelayKind(StrEnum):
    MANAGED = "managed"
    OWN = "own"


def normalize_base_domain(value: str) -> str:
    if "://" in value:
        raise ValueError("Base domain must not include a scheme")
    if "/" in value:
        raise ValueError("Base domain must not include a path")
    if ":" in value:
        raise ValueError("Base domain must not include a port")
    if value.endswith("."):
        raise ValueError("Base domain must not end with a dot")
    domain = value.lower()
    if len(domain) > _MAX_HOSTNAME_LENGTH or not _HOSTNAME.fullmatch(domain):
        raise ValueError("Base domain must be a bare hostname such as sessions.example")
    return domain


def validate_agent_url(value: str) -> str:
    address = urlsplit(value)
    if address.scheme not in ("ws", "wss") or not address.hostname:
        raise ValueError("Connection address must be a ws or wss address")
    try:
        # urlsplit checks the port only when it is read.
        address.port  # noqa: B018
    except ValueError as error:
        raise ValueError("Connection address has an invalid port") from error
    return value


class RelayCapabilityEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: CapabilityVersion
    api_versions: list[CapabilityVersion] = Field(default_factory=list)


class SessionsCapabilityV1(BaseModel):
    """Serving sessions: HTTP and WebSocket forwarding with browser access."""

    model_config = ConfigDict(extra="allow")

    version: Literal[1]
    api_versions: list[CapabilityVersion] = Field(default_factory=lambda: [1])


_RELAY_CAPABILITY_MODELS: dict[str, dict[int, type[BaseModel]]] = {
    SESSIONS_CAPABILITY: {1: SessionsCapabilityV1},
}


def _capability_error(capability: str, error: ValidationError) -> str:
    detail = error.errors(include_url=False)[0]
    location = ".".join(str(part) for part in detail["loc"])
    return f"Invalid capability '{capability}' field '{location}': {detail['msg']}"


def normalize_relay_capabilities(
    capabilities: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Validate declared capabilities; unknown versions and custom ones are kept as
    declared, so a relay may announce what this LUML cannot use yet."""
    normalized: dict[str, dict[str, Any]] = {}
    for capability, declaration in capabilities.items():
        if capability not in RESERVED_RELAY_CAPABILITIES and not (
            _CUSTOM_RELAY_CAPABILITY.fullmatch(capability)
        ):
            raise CapabilityValidationError(f"Invalid capability '{capability}'")
        try:
            envelope = RelayCapabilityEnvelope.model_validate(declaration)
            model = _RELAY_CAPABILITY_MODELS.get(capability, {}).get(envelope.version)
            normalized[capability] = (
                model.model_validate(declaration).model_dump(mode="json")
                if model
                else declaration.copy()
            )
        except ValidationError as error:
            raise CapabilityValidationError(
                _capability_error(capability, error)
            ) from error
    return normalized


def get_present_relay_capabilities(
    capabilities: dict[str, dict[str, Any]],
) -> list[str]:
    present: list[str] = []
    for capability, declaration in capabilities.items():
        if capability not in RESERVED_RELAY_CAPABILITIES:
            present.append(capability)
            continue
        version = declaration.get("version")
        api_versions = declaration.get("api_versions")
        if version not in SUPPORTED_RELAY_CAPABILITY_DECLARATION_VERSIONS[capability]:
            continue
        if isinstance(api_versions, list) and (
            SUPPORTED_RELAY_CAPABILITY_API_VERSIONS[capability] & set(api_versions)
        ):
            present.append(capability)
    return present


class RelayCreateIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    base_domain: str
    agent_url: str

    @field_validator("base_domain")
    @classmethod
    def _base_domain(cls, value: str) -> str:
        return normalize_base_domain(value)

    @field_validator("agent_url")
    @classmethod
    def _agent_url(cls, value: str) -> str:
        return validate_agent_url(value)


class RelayCreate(RelayCreateIn):
    organization_id: UUID | None = None
    token_hash: str


class RelayUpdateIn(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    base_domain: str | None = None
    agent_url: str | None = None
    status: RelayStatus | None = None

    @field_validator("base_domain")
    @classmethod
    def _base_domain(cls, value: str | None) -> str | None:
        return None if value is None else normalize_base_domain(value)

    @field_validator("agent_url")
    @classmethod
    def _agent_url(cls, value: str | None) -> str | None:
        return None if value is None else validate_agent_url(value)


class Relay(BaseModel, BaseOrmConfig):
    id: UUID
    organization_id: UUID | None = None
    label: str
    base_domain: str
    agent_url: str
    status: RelayStatus
    last_seen_at: datetime | None = None
    connected_agents: int = 0
    capabilities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def present_capabilities(self) -> list[str]:
        return get_present_relay_capabilities(self.capabilities)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kind(self) -> RelayKind:
        return RelayKind.MANAGED if self.organization_id is None else RelayKind.OWN

    @computed_field  # type: ignore[prop-decorator]
    @property
    def online(self) -> bool:
        if self.last_seen_at is None:
            return False
        return datetime.now(UTC) - self.last_seen_at < RELAY_ONLINE_WINDOW


class RelayTokenOut(BaseModel):
    relay: Relay
    token: str


class RelayDescription(BaseModel):
    id: UUID
    label: str
    base_domain: str
    agent_url: str
    status: RelayStatus
    app_origins: list[str]
    app_url: str


class SessionTokenValidateIn(BaseModel):
    token: str
    launch: bool = False


class SessionTokenVerdict(BaseModel):
    active: bool
    kind: SessionTokenKind | None = None
    session_id: str | None = None
    user_id: UUID | None = None
    expires_at: datetime | None = None
    grant_id: UUID | None = None
    destination: str | None = None


class ViewerGrantCheckIn(BaseModel):
    grant_id: UUID


class ViewerGrantVerdict(BaseModel):
    active: bool
    session_id: str | None = None
    user_id: UUID | None = None
    expires_at: datetime | None = None


class RelayReportIn(BaseModel):
    connected_agents: int = Field(ge=0)
    capabilities: dict[str, dict[str, Any]]

    @field_validator("capabilities")
    @classmethod
    def _capabilities(
        cls, value: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        return normalize_relay_capabilities(value)
