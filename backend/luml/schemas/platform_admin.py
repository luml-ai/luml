from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from luml.schemas.base import BaseOrmConfig
from luml.schemas.organization import OrgRole
from luml.schemas.user import AuthProvider

PKCE_PATTERN = r"^[A-Za-z0-9\-._~]{43,128}$"
CODE_CHALLENGE_PATTERN = r"^[A-Za-z0-9\-_]{43}$"


class PlatformAdminAuthMethod(StrEnum):
    GOOGLE = "GOOGLE"
    EMAIL = "EMAIL"


class PasswordGrant(BaseModel):
    grant_type: Literal["password"]
    email: EmailStr = Field(max_length=254)
    password: str = Field(max_length=128)


class GoogleCodeGrant(BaseModel):
    grant_type: Literal["google_code"]
    code: str = Field(max_length=4096)
    code_verifier: str = Field(pattern=PKCE_PATTERN)


PlatformAdminTokenRequest = Annotated[
    PasswordGrant | GoogleCodeGrant, Field(discriminator="grant_type")
]


class PlatformAdminToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class PlatformAdmin(BaseModel):
    email: EmailStr
    auth_method: PlatformAdminAuthMethod
    expires_at: datetime


class PlatformStats(BaseModel):
    users: int
    disabled_users: int
    users_created_last_30_days: int
    organizations: int
    orbits: int
    satellites: int
    artifacts: int


class PlatformAdminUser(BaseModel, BaseOrmConfig):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    disabled: bool
    email_verified: bool
    auth_method: AuthProvider
    created_at: datetime
    organizations_count: int = 0
    organizations_limit: int


class PlatformAdminUserMembership(BaseModel):
    organization_id: UUID
    organization_name: str
    role: OrgRole


class PlatformAdminUserDetails(PlatformAdminUser):
    has_api_key: bool
    memberships: list[PlatformAdminUserMembership]


class PlatformAdminUsersPage(BaseModel):
    items: list[PlatformAdminUser]
    total: int


class PlatformAdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disabled: bool | None = None
    organizations_limit: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_any_field(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one field must be provided")
        return self


class OrganizationLimits(BaseModel, BaseOrmConfig):
    members_limit: int
    orbits_limit: int
    satellites_limit: int
    artifacts_limit: int


class OrganizationUsage(BaseModel):
    members: int
    orbits: int
    satellites: int
    artifacts: int


class OrganizationLimitsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    members_limit: int | None = Field(default=None, ge=0)
    orbits_limit: int | None = Field(default=None, ge=0)
    satellites_limit: int | None = Field(default=None, ge=0)
    artifacts_limit: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_any_limit(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one limit must be provided")
        return self


class PlatformAdminOrganization(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    limits: OrganizationLimits
    usage: OrganizationUsage


class PlatformAdminOrganizationMember(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str | None = None
    role: OrgRole


class PlatformAdminOrganizationDetails(PlatformAdminOrganization):
    members: list[PlatformAdminOrganizationMember]


class PlatformAdminOrganizationsPage(BaseModel):
    items: list[PlatformAdminOrganization]
    total: int
