from datetime import datetime

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig, ShortUUID


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
    organization_id: ShortUUID


class BucketSecret(_BucketSecretBase, BaseOrmConfig):
    id: ShortUUID
    organization_id: ShortUUID
    created_at: datetime
    updated_at: datetime | None = None

    def update_from_partial(
        self, update_data: "BucketSecretUpdateIn"
    ) -> "BucketSecret":
        return self.model_copy(
            update=update_data.model_dump(exclude_unset=True, mode="python")
        )


class BucketSecretOut(BaseModel, BaseOrmConfig):
    id: ShortUUID
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str | None = None
    cert_check: bool | None = None
    organization_id: ShortUUID
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
    id: ShortUUID


class BucketSecretUrls(BaseModel, BaseOrmConfig):
    presigned_url: str
    download_url: str
    delete_url: str
