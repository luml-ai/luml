import math
from abc import ABC, abstractmethod
from typing import Any

from dataforce_studio.constants import MAX_FILE_SIZE_BYTES, USE_MULTIPART_BYTES
from dataforce_studio.schemas.bucket_secrets import (
    AzureBucketSecret,
    AzureBucketSecretCreateIn,
    S3BucketSecret,
    S3BucketSecretCreateIn,
)
from dataforce_studio.schemas.storage import (
    AzureMultiPartUploadDetails,
    AzureUploadDetails,
    S3MultiPartUploadDetails,
    S3UploadDetails,
)


class BaseStorageClient(ABC):
    _url_expire = 12  # hours

    @staticmethod
    def _calculate_optimal_chunk_size(file_size: int) -> int:
        if file_size <= 1073741824:  # 1gb
            return 33554432  # 32 mb
        if file_size <= 5368709120:  # 5gb
            return 67108864  # 64 mb
        if file_size <= 10737418240:  # 10gb
            return 134217728  # 128 mb
        if file_size <= 107374182400:  # 100gb
            return 536870912  # 512 mb
        return 1073741824  # 1gb

    @staticmethod
    def _should_use_multipart(file_size: int) -> bool:
        return file_size > USE_MULTIPART_BYTES  # 500 mb

    def _calculate_multipart_params(self, file_size: int) -> tuple[int, int]:
        part_size = self._calculate_optimal_chunk_size(file_size)
        parts_count = math.ceil(file_size / part_size)

        return parts_count, part_size

    @staticmethod
    def validate_size(size: int) -> None:
        if size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Model cant be bigger than 5TB - {MAX_FILE_SIZE_BYTES} bytes"
            )

    @staticmethod
    @abstractmethod
    def _create_client(
        secret: AzureBucketSecret
        | AzureBucketSecretCreateIn
        | S3BucketSecret
        | S3BucketSecretCreateIn,
    ) -> Any:  # noqa: ANN401
        pass

    @abstractmethod
    async def get_upload_url(self, object_name: str) -> str:
        pass

    @abstractmethod
    async def get_download_url(self, object_name: str) -> str:
        pass

    @abstractmethod
    async def get_delete_url(self, object_name: str) -> str:
        pass

    @abstractmethod
    async def create_upload(
        self, bucket_location: str, size: int
    ) -> S3UploadDetails | AzureUploadDetails:
        pass

    @abstractmethod
    async def create_multipart_upload(
        self, bucket_location: str, size: int, upload_id: str | None = None
    ) -> S3MultiPartUploadDetails | AzureMultiPartUploadDetails:
        pass
