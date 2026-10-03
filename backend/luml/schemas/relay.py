import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_validator

from luml.schemas.base import BaseOrmConfig

RELAY_ONLINE_WINDOW = timedelta(minutes=5)

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
        raise ValueError("Base domain must be a bare hostname such as tunnel.example")
    return domain


def validate_agent_url(value: str) -> str:
    address = urlsplit(value)
    if address.scheme not in ("ws", "wss") or not address.hostname:
        raise ValueError("Agent address must be a ws or wss address")
    return value


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
    created_at: datetime
    updated_at: datetime | None = None

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
