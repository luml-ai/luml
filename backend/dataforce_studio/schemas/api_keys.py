from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig


class APIKeyCreate(BaseModel):
    user_id: int
    key: str


class APIKeyOut(BaseModel, BaseOrmConfig):
    id: int
    user_id: int


class APIKeyCreateOut(APIKeyOut):
    key: str
