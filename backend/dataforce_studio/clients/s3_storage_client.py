from datetime import timedelta
from uuid import UUID

from minio import Minio

from dataforce_studio.clients.base_storage_client import BaseStorageClient
from dataforce_studio.infra.exceptions import BucketConnectionError
from dataforce_studio.schemas.bucket_secrets import (
    BucketType,
    S3BucketSecret,
    S3BucketSecretCreateIn,
)
from dataforce_studio.schemas.storage import (
    MultipartUploadInfo,
    PartDetails,
    S3MultiPartUploadDetails,
    S3UploadDetails,
)


class S3Client(BaseStorageClient):
    def __init__(self, secret: S3BucketSecret | S3BucketSecretCreateIn) -> None:
        self._bucket_id: UUID | None = getattr(secret, "id", None)
        self._bucket_name = secret.bucket_name
        self._client = self._create_client(secret)

    @staticmethod
    def _create_client(secret: S3BucketSecret | S3BucketSecretCreateIn) -> Minio:  # type: ignore[override]
        return Minio(
            secret.endpoint,
            access_key=secret.access_key,
            secret_key=secret.secret_key,
            session_token=secret.session_token,
            secure=secret.secure if secret.secure is not None else True,
            region=secret.region,
            cert_check=secret.cert_check if secret.cert_check is not None else True,
        )

    async def get_initiate_multipart_url(self, object_name: str) -> str:
        try:
            return self._client.get_presigned_url(
                "POST",
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
                extra_query_params={"uploads": ""},
            )
        except Exception as error:
            raise BucketConnectionError(
                f"Failed to generate initiate URL: {error}"
            ) from error

    def _initiate_multipart_upload(
        self, object_name: str, file_size: int
    ) -> MultipartUploadInfo:
        try:
            parts_count, part_size = self._calculate_multipart_params(file_size)

            upload_id = self._client._create_multipart_upload(
                bucket_name=self._bucket_name,
                object_name=object_name,
                headers={"Transfer-Encoding": "chunked"},
            )

            return MultipartUploadInfo(
                upload_id=upload_id, parts_count=parts_count, part_size=part_size
            )

        except Exception as error:
            raise BucketConnectionError(
                "Failed to initiate multipart upload."
            ) from error

    async def _get_multipart_upload_urls(
        self, object_name: str, upload_id: str, parts_count: int
    ) -> list[str]:
        try:
            urls = []
            for part_number in range(1, parts_count + 1):
                url = self._client.get_presigned_url(
                    "PUT",
                    bucket_name=self._bucket_name,
                    object_name=object_name,
                    expires=timedelta(hours=self._url_expire),
                    extra_query_params={
                        "partNumber": str(part_number),
                        "uploadId": upload_id,
                    },
                )
                urls.append(url)
            return urls
        except Exception as error:
            raise BucketConnectionError("Failed to generate upload URL.") from error

    @staticmethod
    def _parts_upload_details(
        urls: list[str], size: int, part_size: int
    ) -> list[PartDetails]:
        parts: list[PartDetails] = []
        start_byte: int = 0
        for part_number in range(len(urls)):
            current_part_size: int = min(part_size, size - part_number * part_size)
            end_byte: int = start_byte + current_part_size

            parts.append(
                PartDetails(
                    part_number=part_number + 1,
                    url=urls[part_number],
                    start_byte=start_byte,
                    end_byte=end_byte,
                    part_size=current_part_size,
                )
            )
            start_byte += current_part_size + 1

        return parts

    async def get_upload_url(self, object_name: str) -> str:
        try:
            return self._client.presigned_put_object(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
            )
        except Exception as error:
            raise BucketConnectionError("Failed to generate upload URL.") from error

    async def get_complete_url(self, object_name: str, upload_id: str) -> str:
        try:
            return self._client.get_presigned_url(
                "POST",
                self._bucket_name,
                object_name,
                expires=timedelta(hours=self._url_expire),
                extra_query_params={"uploadId": upload_id},
            )
        except Exception as error:
            raise BucketConnectionError("Failed to generate complete URL.") from error

    async def get_download_url(self, object_name: str) -> str:
        try:
            return self._client.presigned_get_object(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
            )
        except Exception as error:
            raise BucketConnectionError("Failed to generate download URL.") from error

    async def get_delete_url(self, object_name: str) -> str:
        try:
            return self._client.get_presigned_url(
                "DELETE",
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
            )
        except Exception as error:
            raise BucketConnectionError("Failed to generate delete URL.") from error

    async def create_multipart_upload(
        self, bucket_location: str, size: int, upload_id: str | None = None
    ) -> S3MultiPartUploadDetails:
        if upload_id is None:
            raise ValueError("upload_id is required for S3 multipart uploads")

        parts_count, part_size = self._calculate_multipart_params(size)

        urls = await self._get_multipart_upload_urls(
            bucket_location, upload_id, parts_count
        )
        return S3MultiPartUploadDetails(
            upload_id=upload_id,
            parts=self._parts_upload_details(urls, size, part_size),
            complete_url=await self.get_complete_url(bucket_location, upload_id),
        )

    async def create_upload(self, bucket_location: str, size: int) -> S3UploadDetails:
        if self._bucket_id is None:
            raise ValueError("Bucket secret ID is required for creating upload URLs")

        self.validate_size(size)

        if self._should_use_multipart(size):
            return S3UploadDetails(
                type=BucketType.S3,
                url=await self.get_initiate_multipart_url(bucket_location),
                multipart=True,
                bucket_location=bucket_location,
                bucket_secret_id=self._bucket_id,
            )
        return S3UploadDetails(
            type=BucketType.S3,
            url=await self.get_upload_url(bucket_location),
            bucket_location=bucket_location,
            bucket_secret_id=self._bucket_id,
        )
