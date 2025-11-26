import uuid

from pydantic import BaseModel


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


class UploadDetails(BaseModel):
    url: str
    multipart: bool = False
    bucket_location: str
    bucket_secret_id: uuid.UUID


class MultiPartUploadDetails(BaseModel):
    upload_id: str
    parts: list[PartDetails]
    complete_url: str


class BucketMultipartUpload(BaseModel):
    bucket_id: uuid.UUID
    bucket_location: str
    size: int
    upload_id: str
