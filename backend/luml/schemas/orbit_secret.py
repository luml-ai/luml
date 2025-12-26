from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from luml.schemas.base import BaseOrmConfig


class _OrbitSecretBase(BaseModel):
    name: str
    value: str
    tags: list[str] | None = None


class OrbitSecretCreateIn(_OrbitSecretBase): ...


class OrbitSecretCreate(_OrbitSecretBase):
    orbit_id: UUID


class OrbitSecret(_OrbitSecretBase, BaseOrmConfig):
    id: UUID
    orbit_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class OrbitSecretOut(BaseModel, BaseOrmConfig):
    id: UUID
    name: str
    value: str
    orbit_id: UUID
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrbitSecretUpdate(BaseModel):
    name: str | None = None
    value: str | None = None
    tags: list[str] | None = None
