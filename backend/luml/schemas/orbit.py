from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from luml.schemas.base import BaseOrmConfig
from luml.schemas.user import UserOut


class OrbitRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
    # VIEWER = "viewer"


class Orbit(BaseModel, BaseOrmConfig):
    id: UUID
    name: str
    organization_id: UUID
    bucket_secret_id: UUID
    total_members: int | None = None
    total_collections: int | None = None
    total_satellites: int | None = None
    total_model_artifacts: int | None = None
    role: OrbitRole | None = None
    created_at: datetime
    updated_at: datetime | None = None
    permissions: dict[str, Any] | None = None


class OrbitDetails(Orbit):
    members: list[OrbitMember] | None = None
    collections_tags: list[str] | None = None


class OrbitUpdate(BaseModel, BaseOrmConfig):
    id: UUID | None = None
    name: str | None = None
    bucket_secret_id: UUID | None = None


class OrbitCreateIn(BaseModel, BaseOrmConfig):
    name: str
    bucket_secret_id: UUID
    members: list[OrbitMemberCreateSimple] | None = None
    notify: bool = False


class OrbitCreate(BaseModel, BaseOrmConfig):
    name: str
    bucket_secret_id: UUID
    organization_id: UUID | None = None


class OrbitMemberCreateSimple(BaseModel):
    user_id: UUID
    role: OrbitRole


class OrbitMemberCreate(OrbitMemberCreateSimple):
    orbit_id: UUID


class UpdateOrbitMember(BaseModel):
    id: UUID
    role: OrbitRole


class OrbitMember(BaseModel, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    role: OrbitRole
    user: UserOut
    created_at: datetime
    updated_at: datetime | None = None
