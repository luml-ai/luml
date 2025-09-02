from datetime import datetime

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig


class _OrbitSecretBase(BaseModel):
    name: str
    value: str


class OrbitSecretCreateIn(_OrbitSecretBase): ...


class OrbitSecretCreate(_OrbitSecretBase):
    orbit_id: int


class OrbitSecret(_OrbitSecretBase, BaseOrmConfig):
    id: int
    orbit_id: int
    created_at: datetime
    updated_at: datetime | None = None


class OrbitSecretOut(BaseModel, BaseOrmConfig):
    id: int
    name: str
    value: str
    orbit_id: int
    created_at: datetime
    updated_at: datetime | None = None


class OrbitSecretUpdate(BaseModel):
    name: str | None = None
    value: str | None = None
