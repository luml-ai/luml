import uuid

from pydantic import BaseModel

from luml.schemas.bucket_secrets import BucketType


class MultipartUploadInfo(BaseModel):
    upload_id: str
    parts_count: int
    part_size: int


class PartDetails(BaseModel):
    part_number: int
    url: str
    start_byte: int
    end_byte: int
    part_size: int


class S3UploadDetails(BaseModel):
    type: BucketType = BucketType.S3
    url: str
    multipart: bool = False
    bucket_location: str
    bucket_secret_id: uuid.UUID


class AzureUploadDetails(BaseModel):
    type: BucketType = BucketType.AZURE
    url: str | None = None
    multipart: bool = False
    bucket_location: str
    bucket_secret_id: uuid.UUID


class S3MultiPartUploadDetails(BaseModel):
    type: BucketType = BucketType.S3
    upload_id: str
    parts: list[PartDetails]
    complete_url: str


class AzureMultiPartUploadDetails(BaseModel):
    type: BucketType = BucketType.AZURE
    parts: list[PartDetails]
    complete_url: str


class BucketMultipartUpload(BaseModel):
    bucket_id: uuid.UUID
    bucket_location: str
    size: int
    upload_id: str | None = None
