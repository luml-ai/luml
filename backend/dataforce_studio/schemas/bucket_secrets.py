from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from dataforce_studio.schemas.base import BaseOrmConfig


class _BucketSecretBase(BaseModel):
    endpoint: str
    bucket_name: str
    access_key: str | None = None
    secret_key: str | None = None
    session_token: str | None = None
    secure: bool | None = None
    region: str | None = None
    cert_check: bool | None = None

    @field_validator("endpoint")
    @classmethod
    def strip_http_protocol(cls, v: str) -> str:
        if v:
            v = v.removeprefix("http://").removeprefix("https://")
        return v


class BucketSecretCreateIn(_BucketSecretBase): ...


class BucketSecretCreate(_BucketSecretBase):
    organization_id: UUID


class BucketSecret(_BucketSecretBase, BaseOrmConfig):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime | None = None

    def update_from_partial(self, update_data: BucketSecretUpdateIn) -> BucketSecret:
        return self.model_copy(update=update_data.model_dump(exclude_unset=True))


class BucketSecretOut(BaseModel, BaseOrmConfig):
    id: UUID
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str | None = None
    cert_check: bool | None = None
    organization_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class BucketSecretUpdateIn(BaseModel):
    endpoint: str | None = None
    bucket_name: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    session_token: str | None = None
    secure: bool | None = None
    region: str | None = None
    cert_check: bool | None = None

    @field_validator("endpoint")
    @classmethod
    def strip_http_protocol(cls, v: str | None) -> str | None:
        if v:
            v = v.removeprefix("http://").removeprefix("https://")
        return v


class BucketSecretUpdate(BucketSecretUpdateIn):
    id: UUID


class BucketSecretUrls(BaseModel, BaseOrmConfig):
    presigned_url: str
    download_url: str
    delete_url: str
