from uuid import UUID

from luml_satellite.wire._base import PlatformModel

MONITORING_READ_SCOPE = "monitoring:read"
MONITORING_WRITE_SCOPE = "monitoring:write"


class MonitoringTokenClaims(PlatformModel):
    deployment_id: UUID
    satellite_id: UUID
    user_id: UUID
    scope: str
    jti: UUID
    exp: int


class MonitoringIntrospection(PlatformModel):
    active: bool
    claims: MonitoringTokenClaims | None = None


class MonitoringSessionInfo(PlatformModel):
    deployment_id: UUID
    scope: str
