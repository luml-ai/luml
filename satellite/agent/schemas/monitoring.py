from uuid import UUID

from pydantic import BaseModel

MONITORING_READ_SCOPE = "monitoring:read"
# Reserved for the day the Platform mints a scope that allows dashboard writes; until then
# acknowledging rides on the read session (see require_monitoring_write).
MONITORING_WRITE_SCOPE = "monitoring:write"


class MonitoringTokenClaims(BaseModel):
    deployment_id: UUID
    satellite_id: UUID
    user_id: UUID
    scope: str
    jti: UUID
    exp: int


class MonitoringIntrospection(BaseModel):
    active: bool
    claims: MonitoringTokenClaims | None = None


class MonitoringSessionInfo(BaseModel):
    deployment_id: UUID
    scope: str
