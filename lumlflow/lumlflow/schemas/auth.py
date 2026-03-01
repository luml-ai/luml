from pydantic import BaseModel, Field


class ApiKeyCredentials(BaseModel):
    api_key: str | None = None


class SetApiKey(BaseModel):
    api_key: str


class HasApiKey(BaseModel):
    has_key: bool
