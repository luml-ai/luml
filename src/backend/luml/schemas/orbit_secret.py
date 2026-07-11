from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from luml.schemas.base import BaseOrmConfig

TagList = Annotated[list[Annotated[str, Field(max_length=64)]], Field(max_length=50)]


class _OrbitSecretBase(BaseModel):
    name: str
    value: str
    tags: list[str] | None = None


class OrbitSecretCreateIn(_OrbitSecretBase):
    name: str = Field(max_length=255)
    value: str = Field(max_length=8192)
    tags: TagList | None = None


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
    name: str | None = Field(default=None, max_length=255)
    value: str | None = Field(default=None, max_length=8192)
    tags: TagList | None = None
