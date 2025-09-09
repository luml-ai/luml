from datetime import datetime

from pydantic import BaseModel

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


class BucketSecretCreateIn(_BucketSecretBase): ...


class BucketSecretCreate(_BucketSecretBase):
    organization_id: int


class BucketSecret(_BucketSecretBase, BaseOrmConfig):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime | None = None

    def update_from_partial(
        self, update_data: "BucketSecretUpdateIn | BucketValidationUrls"
    ) -> "BucketSecret":
        return self.model_copy(
            update=update_data.model_dump(exclude_unset=True, exclude_none=True)
        )


class BucketSecretOut(BaseModel, BaseOrmConfig):
    id: int
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str | None = None
    cert_check: bool | None = None
    organization_id: int
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


class BucketSecretUpdate(BucketSecretUpdateIn):
    id: int


class BucketValidationUrls(BucketSecretUpdateIn):
    id: int
    organization_id: int
    user_id: int


class BucketSecretUrls(BaseModel, BaseOrmConfig):
    presigned_url: str
    download_url: str
    delete_url: str
