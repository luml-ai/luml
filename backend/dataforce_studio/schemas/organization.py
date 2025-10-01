from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from dataforce_studio.schemas.base import BaseOrmConfig, ShortUUID
from dataforce_studio.schemas.orbit import Orbit
from dataforce_studio.schemas.user import UserOut


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrganizationCreateIn(BaseModel):
    name: str
    logo: HttpUrl | None = None


class OrganizationCreate(BaseModel):
    name: str
    logo: str | None = None


class OrganizationUpdate(BaseModel):
    id: ShortUUID | None = None
    name: str | None = None
    logo: HttpUrl | str | None = None


class Organization(BaseModel, BaseOrmConfig):
    id: ShortUUID
    name: str
    logo: HttpUrl | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrganizationSwitcher(Organization):
    role: OrgRole | None = None
    permissions: dict[str, Any] | None = None


class CreateOrganizationInviteIn(BaseModel):
    email: EmailStr
    role: OrgRole
    organization_id: ShortUUID

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value == OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


class CreateOrganizationInvite(BaseModel):
    email: EmailStr
    role: OrgRole
    organization_id: ShortUUID
    invited_by: ShortUUID


class OrganizationInvite(BaseModel, BaseOrmConfig):
    id: ShortUUID
    email: EmailStr
    role: OrgRole
    organization_id: ShortUUID
    invited_by_user: UserOut | None = None
    organization: Organization | None = None
    created_at: datetime


class OrganizationInviteSimple(BaseModel, BaseOrmConfig):
    id: ShortUUID
    email: EmailStr
    role: OrgRole
    organization_id: ShortUUID
    created_at: datetime


class UserInvite(OrganizationInvite):
    organization: Organization | None = None


class UpdateOrganizationMember(BaseModel):
    id: ShortUUID | None = None
    role: OrgRole

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value == OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


class OrganizationMember(BaseModel, BaseOrmConfig):
    id: ShortUUID
    organization_id: ShortUUID
    role: OrgRole
    user: UserOut


class OrganizationMemberCreate(BaseModel):
    user_id: ShortUUID
    organization_id: ShortUUID
    role: OrgRole

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value == OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


class OrganizationOwnerCreate(BaseModel):
    user_id: ShortUUID
    organization_id: ShortUUID
    role: OrgRole

    @field_validator("role")
    @classmethod
    def forbid_owner(cls, value: OrgRole) -> OrgRole:
        if value != OrgRole.OWNER:
            raise ValueError("Role 'OWNER' cant be assigned")
        return value


class OrganizationDetails(Organization):
    invites: list[OrganizationInvite]
    members: list[OrganizationMember]
    orbits: list[Orbit]
    members_limit: int = 0
    orbits_limit: int = 0
    total_orbits: int = 0
    total_members: int = 0
    members_by_role: dict[str, int] = Field(default_factory=dict)
    permissions: dict[str, Any] | None = None
