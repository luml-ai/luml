from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


@dataclass
class PartInfo:
    etag: str
    size: int
    file: Path


@dataclass
class MultipartUpload:
    bucket: str
    key: str
    parts: dict[int, PartInfo] = field(default_factory=dict)
    created: datetime = field(default_factory=datetime.now(UTC))


@dataclass
class S3Request:
    bucket: str | None = None
    key: str | None = None
    query_params: dict[str, str] = field(default_factory=dict)

    @property
    def has_bucket_and_key(self) -> bool:
        return self.bucket is not None and self.key is not None


@dataclass
class AwsAuthInfo:
    access_key: str
    secret_key: str
    date_stamp: str
    region: str
    service: str
    signed_headers: str
    client_signature: str


@dataclass
class AwsCredentials:
    access_key: str
    date_stamp: str
    region: str
    service: str


class S3AuthError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass
class S3ErrorResponse:
    code: str
    message: str
    request_id: str

    def to_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Error>
    <Code>{xml_escape(self.code)}</Code>
    <Message>{xml_escape(self.message)}</Message>
    <RequestId>{xml_escape(self.request_id)}</RequestId>
</Error>"""


@dataclass
class InitiateMultipartUploadResponse:
    bucket: str
    key: str
    upload_id: str

    def to_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<InitiateMultipartUploadResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Bucket>{xml_escape(self.bucket)}</Bucket>
    <Key>{xml_escape(self.key)}</Key>
    <UploadId>{xml_escape(self.upload_id)}</UploadId>
</InitiateMultipartUploadResult>"""


@dataclass
class CompleteMultipartUploadResponse:
    location: str
    bucket: str
    key: str
    etag: str

    def to_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<CompleteMultipartUploadResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Location>{xml_escape(self.location)}</Location>
    <Bucket>{xml_escape(self.bucket)}</Bucket>
    <Key>{xml_escape(self.key)}</Key>
    <ETag>"{xml_escape(self.etag)}"</ETag>
</CompleteMultipartUploadResult>"""
