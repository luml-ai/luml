from pydantic import BaseModel


class ApiKeyCredentials(BaseModel):
    api_key: str | None


class HasApiKey(BaseModel):
    has_key: bool
