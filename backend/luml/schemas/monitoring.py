from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

MONITORING_READ_SCOPE = "monitoring:read"


class MonitoringIneligibilityReason(StrEnum):
    MONITORING_OFF = "monitoring_off"
    CAPABILITY_MISSING = "capability_missing"


class MonitoringEligibility(BaseModel):
    eligible: bool
    satellite_base_url: str | None = None
    reason: MonitoringIneligibilityReason | None = None


class MonitoringLaunchToken(BaseModel):
    token: str
    satellite_base_url: str
    expires_at: int


class MonitoringTokenClaims(BaseModel):
    deployment_id: UUID
    satellite_id: UUID
    user_id: UUID
    scope: str
    jti: UUID
    exp: int


class MonitoringTokenIntrospectIn(BaseModel):
    token: str = Field(max_length=4096)


class MonitoringTokenIntrospectOut(BaseModel):
    active: bool
    claims: MonitoringTokenClaims | None = None
