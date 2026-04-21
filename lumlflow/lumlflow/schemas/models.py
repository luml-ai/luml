from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from lumlflow.schemas.base import BaseOrmConfig


class Model(BaseModel, BaseOrmConfig):
    id: str
    name: str
    created_at: datetime
    tags: list[str] | None = None
    path: str | None = None
    size: int | None = None


class UpdateModel(BaseModel):
    name: str | None = None
    tags: list[str] | None = None


class ModelDetails(Model):
    static_params: dict[str, Any] | None = None
    dynamic_params: dict[str, Any] | None = None
    experiments: list[dict] = Field(default_factory=list)


class ModelExperiment(BaseModel, BaseOrmConfig):
    id = str
    name: str
    input: dict = Field(default_factory=dict)
