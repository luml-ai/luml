from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from dataforce_studio.schemas.base import BaseOrmConfig


class BucketType(StrEnum):
    S3 = "s3"
    AZURE = "azure"


class BucketSecretUrls(BaseModel, BaseOrmConfig):
    presigned_url: str
    download_url: str
    delete_url: str


class _S3BucketSecretBase(BaseModel):
    type: Literal[BucketType.S3] = BucketType.S3
    endpoint: str
    bucket_name: str
    access_key: str | None = None
    secret_key: str | None = None
    session_token: str | None = None
    secure: bool | None = None
    region: str
    cert_check: bool | None = None

    @field_validator("endpoint")
    @classmethod
    def strip_http_protocol(cls, v: str) -> str:
        if v:
            v = v.removeprefix("http://").removeprefix("https://")
        return v


class S3BucketSecretCreateIn(_S3BucketSecretBase): ...


class S3BucketSecretCreate(S3BucketSecretCreateIn):
    organization_id: UUID


class S3BucketSecret(_S3BucketSecretBase, BaseOrmConfig):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class S3BucketSecretOut(BaseModel, BaseOrmConfig):
    id: UUID
    type: Literal[BucketType.S3] = BucketType.S3
    endpoint: str
    bucket_name: str
    secure: bool | None = None
    region: str
    cert_check: bool | None = None
    organization_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class S3BucketSecretUpdateIn(BaseModel):
    type: Literal[BucketType.S3] = Field(default=BucketType.S3, frozen=True)
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


class S3BucketSecretUpdate(S3BucketSecretUpdateIn):
    id: UUID


class _AzureBucketSecretBase(BaseModel):
    type: Literal[BucketType.AZURE] = BucketType.AZURE
    endpoint: str
    bucket_name: str


class AzureBucketSecretCreateIn(_AzureBucketSecretBase): ...


class AzureBucketSecretCreate(AzureBucketSecretCreateIn):
    organization_id: UUID


class AzureBucketSecret(_AzureBucketSecretBase, BaseOrmConfig):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class AzureBucketSecretOut(BaseModel, BaseOrmConfig):
    id: UUID
    type: Literal[BucketType.AZURE] = BucketType.AZURE
    endpoint: str
    bucket_name: str
    organization_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class AzureBucketSecretUpdateIn(BaseModel):
    type: Literal[BucketType.AZURE] = Field(default=BucketType.AZURE, frozen=True)
    endpoint: str | None = None
    bucket_name: str | None = None


class AzureBucketSecretUpdate(AzureBucketSecretUpdateIn):
    id: UUID


BucketSecretCreateIn = Annotated[
    S3BucketSecretCreateIn | AzureBucketSecretCreateIn, Field(discriminator="type")
]
BucketSecretCreate = Annotated[
    S3BucketSecretCreate | AzureBucketSecretCreate, Field(discriminator="type")
]
BucketSecret = Annotated[
    S3BucketSecret | AzureBucketSecret, Field(discriminator="type")
]
BucketSecretUpdateIn = Annotated[
    S3BucketSecretUpdateIn | AzureBucketSecretUpdateIn, Field(discriminator="type")
]
BucketSecretUpdate = Annotated[
    S3BucketSecretUpdate | AzureBucketSecretUpdate, Field(discriminator="type")
]
BucketSecretOut = Annotated[
    S3BucketSecretOut | AzureBucketSecretOut, Field(discriminator="type")
]


_BucketSecretAdapter: TypeAdapter[S3BucketSecret | AzureBucketSecret] = TypeAdapter(
    BucketSecret
)
_BucketSecretOutAdapter: TypeAdapter[S3BucketSecretOut | AzureBucketSecretOut] = (
    TypeAdapter(BucketSecretOut)
)
_BucketSecretCreateAdapter: TypeAdapter[
    S3BucketSecretCreate | AzureBucketSecretCreate
] = TypeAdapter(BucketSecretCreate)


def validate_bucket_secret(obj: Any) -> S3BucketSecret | AzureBucketSecret:  # noqa: ANN401
    return _BucketSecretAdapter.validate_python(obj, from_attributes=True)


def validate_bucket_secret_out(obj: Any) -> S3BucketSecretOut | AzureBucketSecretOut:  # noqa: ANN401
    return _BucketSecretOutAdapter.validate_python(obj, from_attributes=True)


def validate_bucket_secret_create(
    obj: Any,  # noqa: ANN401
) -> S3BucketSecretCreate | AzureBucketSecretCreate:
    return _BucketSecretCreateAdapter.validate_python(obj, from_attributes=True)
