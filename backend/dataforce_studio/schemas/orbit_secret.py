from datetime import datetime

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig, ShortUUID


class _OrbitSecretBase(BaseModel):
    name: str
    value: str
    tags: list[str] | None = None


class OrbitSecretCreateIn(_OrbitSecretBase): ...


class OrbitSecretCreate(_OrbitSecretBase):
    orbit_id: ShortUUID


class OrbitSecret(_OrbitSecretBase, BaseOrmConfig):
    id: ShortUUID
    orbit_id: ShortUUID
    created_at: datetime
    updated_at: datetime | None = None


class OrbitSecretOut(BaseModel, BaseOrmConfig):
    id: ShortUUID
    name: str
    value: str
    orbit_id: ShortUUID
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OrbitSecretUpdate(BaseModel):
    name: str | None = None
    value: str | None = None
    tags: list[str] | None = None
