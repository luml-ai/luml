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
    upload_id: str | None
    parts: list[PartDetails]
    complete_url: str | None
