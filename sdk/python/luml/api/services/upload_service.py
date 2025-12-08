from typing import TYPE_CHECKING

import httpx

from .._exceptions import LumlAPIError
from .._types import UploadDetails
from ..utils.file_handler_factory import create_file_handler
from ..utils.s3_file_handler import S3FileHandler

if TYPE_CHECKING:
    from ..resources.bucket_secrets import (
        AsyncBucketSecretResource,
        BucketSecretResource,
    )


class UploadService:
    def __init__(self, bucket_secrets_client: "BucketSecretResource") -> None:
        self._bucket_secrets = bucket_secrets_client

    def upload_file(
        self,
        upload_details: UploadDetails,
        file_path: str,
        file_size: int,
        file_name: str = "",
    ) -> httpx.Response:
        handler = create_file_handler(upload_details.type)

        if upload_details.multipart:
            upload_id = None
            if isinstance(handler, S3FileHandler):
                if not upload_details.url:
                    raise LumlAPIError("Upload URL is required for multipart upload")
                upload_id = handler.initiate_multipart_upload(upload_details.url)
                if not upload_id:
                    raise LumlAPIError("Failed to initiate multipart upload")

            multipart_urls = self._bucket_secrets.get_multipart_upload_urls(
                upload_details.bucket_secret_id,
                upload_details.bucket_location,
                file_size,
                upload_id,
            )

            return handler.upload_multipart(
                parts=multipart_urls.parts,
                complete_url=multipart_urls.complete_url,
                file_size=file_size,
                file_path=file_path,
                file_name=file_name,
                upload_id=upload_id,
            )
        if not upload_details.url:
            raise LumlAPIError("Upload URL is required for simple upload")
        return handler.upload_simple(
            url=upload_details.url,
            file_path=file_path,
            file_size=file_size,
            file_name=file_name,
        )


class AsyncUploadService:
    def __init__(self, bucket_secrets_client: "AsyncBucketSecretResource") -> None:
        self._bucket_secrets = bucket_secrets_client

    async def upload_file(
        self,
        upload_details: UploadDetails,
        file_path: str,
        file_size: int,
        file_name: str = "",
    ) -> httpx.Response:
        handler = create_file_handler(upload_details.type)

        if upload_details.multipart:
            upload_id = None
            if isinstance(handler, S3FileHandler):
                if not upload_details.url:
                    raise LumlAPIError("Upload URL is required for multipart upload")
                upload_id = handler.initiate_multipart_upload(upload_details.url)
                if not upload_id:
                    raise LumlAPIError("Failed to initiate multipart upload")

            multipart_urls = await self._bucket_secrets.get_multipart_upload_urls(
                upload_details.bucket_secret_id,
                upload_details.bucket_location,
                file_size,
                upload_id,
            )

            return handler.upload_multipart(
                parts=multipart_urls.parts,
                complete_url=multipart_urls.complete_url,
                file_size=file_size,
                file_path=file_path,
                file_name=file_name,
                upload_id=upload_id,
            )
        if not upload_details.url:
            raise LumlAPIError("Upload URL is required for simple upload")
        return handler.upload_simple(
            url=upload_details.url,
            file_path=file_path,
            file_size=file_size,
            file_name=file_name,
        )
