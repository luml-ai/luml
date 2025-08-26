import math
from datetime import timedelta

from minio import Minio

from dataforce_studio.infra.exceptions import BucketConnectionError
from dataforce_studio.schemas.bucket_secrets import BucketSecret, BucketSecretCreateIn
from dataforce_studio.schemas.model_artifacts import MultipartUploadInfo


class S3Service:
    def __init__(self, secret: BucketSecret | BucketSecretCreateIn) -> None:
        self._bucket_name = secret.bucket_name
        self._client = self._create_minio_client(secret)
        self._url_expire = 12  # hours

    def _create_minio_client(
        self, secret: BucketSecret | BucketSecretCreateIn
    ) -> Minio:
        return Minio(
            secret.endpoint,
            access_key=secret.access_key,
            secret_key=secret.secret_key,
            session_token=secret.session_token,
            secure=secret.secure if secret.secure is not None else True,
            region=secret.region,
            cert_check=secret.cert_check if secret.cert_check is not None else True,
        )

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

    def _calculate_multipart_params(self, file_size: int) -> tuple[int, int]:
        part_size = self._calculate_optimal_chunk_size(file_size)
        parts_count = math.ceil(file_size / part_size)

        return parts_count, part_size

    @staticmethod
    def should_use_multipart(file_size: int) -> bool:
        return file_size > 524288000  # 500 mb

    async def get_upload_url(self, object_name: str) -> str:
        try:
            return self._client.presigned_put_object(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
            )
        except Exception as e:
            raise BucketConnectionError(
                f"Failed to generate upload URL: {str(e)}"
            ) from e

    def initiate_multipart_upload(
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

        except Exception as e:
            raise ValueError(f"Failed to initiate multipart upload: {str(e)}") from e

    async def get_multipart_upload_urls(
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
        except Exception as e:
            raise BucketConnectionError(
                f"Failed to generate upload URL: {str(e)}"
            ) from e

    @staticmethod
    def parts_upload_details(
        urls: list[str], size: int, part_size: int
    ) -> list[dict[str, int | str]]:  # noqa: ANN401
        parts: list[dict[str, int | str]] = []
        start_byte: int = 0
        for part_number in range(len(urls)):
            current_part_size: int = min(part_size, size - part_number * part_size)
            end_byte: int = start_byte + current_part_size

            parts.append(
                {
                    "part_number": part_number + 1,
                    "url": urls[part_number],
                    "start_byte": start_byte,
                    "end_byte": end_byte,
                    "part_size": current_part_size,
                }
            )
            start_byte += current_part_size + 1

        return parts

    async def get_complete_url(self, object_name: str, upload_id: str) -> str:
        return self._client.get_presigned_url(
            "POST",
            self._bucket_name,
            object_name,
            expires=timedelta(hours=self._url_expire),
            extra_query_params={"uploadId": upload_id},
        )

    async def get_download_url(self, object_name: str) -> str:
        try:
            return self._client.presigned_get_object(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
            )
        except Exception as e:
            raise BucketConnectionError(
                f"Failed to generate download URL: {str(e)}"
            ) from e

    async def get_delete_url(self, object_name: str) -> str:
        try:
            return self._client.get_presigned_url(
                "DELETE",
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=timedelta(hours=self._url_expire),
            )
        except Exception as e:
            raise BucketConnectionError(
                f"Failed to generate delete URL: {str(e)}"
            ) from e
