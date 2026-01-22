from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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
    created: datetime = field(default_factory=datetime.now)


@dataclass
class S3Request:
    bucket: str | None = None
    key: str | None = None
    query_params: dict[str, str] = field(default_factory=dict)

    @property
    def has_bucket_and_key(self) -> bool:
        return self.bucket is not None and self.key is not None


@dataclass
class S3ProxyConfig:
    host: str = "127.0.0.1"
    port: int = 9000
    storage_root: Path = field(default_factory=lambda: Path("./s3_storage"))
    credentials: dict[str, str] = field(default_factory=dict)
    cors_enabled: bool = False
    cors_origins: str = "*"
    cors_methods: str = "GET, PUT, POST, DELETE, HEAD, OPTIONS"
    cors_headers: str = "Authorization, Content-Type, Content-MD5, x-amz-*, Range"
    debug: bool = False

    @property
    def has_credentials(self) -> bool:
        return bool(self.credentials)


@dataclass
class S3ErrorResponse:
    code: str
    message: str
    request_id: str

    def to_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Error>
    <Code>{self.code}</Code>
    <Message>{self.message}</Message>
    <RequestId>{self.request_id}</RequestId>
</Error>"""


@dataclass
class InitiateMultipartUploadResponse:
    bucket: str
    key: str
    upload_id: str

    def to_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<InitiateMultipartUploadResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Bucket>{self.bucket}</Bucket>
    <Key>{self.key}</Key>
    <UploadId>{self.upload_id}</UploadId>
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
    <Location>{self.location}</Location>
    <Bucket>{self.bucket}</Bucket>
    <Key>{self.key}</Key>
    <ETag>"{self.etag}"</ETag>
</CompleteMultipartUploadResult>"""
