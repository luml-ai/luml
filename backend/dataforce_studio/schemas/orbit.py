from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.user import UserOut


class OrbitRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    # VIEWER = "viewer"


class Orbit(BaseModel, BaseOrmConfig):
    id: int
    name: str
    organization_id: int
    bucket_secret_id: int
    total_members: int | None = None
    total_collections: int | None = None
    role: OrbitRole | None = None
    created_at: datetime
    updated_at: datetime | None = None
    permissions: dict[str, Any] | None = None


class OrbitDetails(Orbit):
    members: list["OrbitMember"] | None = None


class OrbitUpdate(BaseModel, BaseOrmConfig):
    id: int | None = None
    name: str | None = None
    bucket_secret_id: int | None = None


class OrbitCreateIn(BaseModel, BaseOrmConfig):
    name: str
    bucket_secret_id: int
    members: list["OrbitMemberCreateSimple"] | None = None
    notify_by_email: bool = False


class OrbitCreate(BaseModel, BaseOrmConfig):
    name: str
    bucket_secret_id: int
    organization_id: int | None = None


class OrbitMemberCreateSimple(BaseModel):
    user_id: int
    role: OrbitRole


class OrbitMemberCreate(OrbitMemberCreateSimple):
    orbit_id: int


class UpdateOrbitMember(BaseModel):
    id: int
    role: OrbitRole


class OrbitMember(BaseModel, BaseOrmConfig):
    id: int
    orbit_id: int
    role: OrbitRole
    user: UserOut
    created_at: datetime
    updated_at: datetime | None = None
