from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from xml.etree import ElementTree as ET

import httpx

from api.luml_api._exceptions import FileUploadError, LumlAPIError
from api.luml_api._types import PartDetails
from api.luml_api.handlers.base_file_handler import BaseFileHandler


class S3FileHandler(BaseFileHandler):
    """File handler for S3-compatible storage."""

    def upload_simple(
        self,
        url: str,
        file_path: str,
        file_size: int,
        file_name: str = "",
    ) -> httpx.Response:
        """Upload a file using simple PUT request."""
        try:
            update_progress = self.create_progress_bar(file_size, file_name)

            timeout = httpx.Timeout(connect=30.0, read=300.0, write=600.0, pool=30.0)

            response = httpx.put(
                url,
                content=self.create_file_generator(
                    file_path, file_size, update_progress
                ),
                headers={"Content-Length": str(file_size)},
                timeout=timeout,
            )

            self.finish_progress()
            response.raise_for_status()
            return response
        except Exception as error:
            self.finish_progress()
            raise FileUploadError(f"Upload failed: {error}") from error

    def upload_multipart(
        self,
        parts: list[PartDetails],
        complete_url: str,
        file_size: int,
        file_path: str,
        file_name: str = "",
        upload_id: str | None = None,
    ) -> httpx.Response:
        """Upload a file using S3 multipart upload."""

        if upload_id is None:
            raise ValueError("upload_id is required for S3 multipart uploads")

        try:
            update_progress = self.create_progress_bar(file_size, file_name)
            parts_complete = []
            progress_lock = Lock()

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_part = {
                    executor.submit(
                        self._upload_single_part,
                        part,
                        file_path,
                        progress_lock,
                        update_progress,
                    ): part
                    for part in parts
                }

                for future in as_completed(future_to_part):
                    part_result = future.result()
                    parts_complete.append(part_result)

            return self._complete_multipart_upload(complete_url, parts_complete)

        except Exception as error:
            raise FileUploadError(f"Multipart upload failed: {error}") from error

    @staticmethod
    def _upload_single_part(
        part: PartDetails,
        file_path: str,
        progress_lock: Lock,
        update_progress: Callable[[int], None],
    ) -> dict[str, int | str]:
        """Upload a single part of multipart upload."""

        part_size = part.end_byte - part.start_byte + 1

        with open(file_path, "rb") as f:
            f.seek(part.start_byte)
            part_data = f.read(part_size)
            actual_size = len(part_data)

        with httpx.Client(timeout=300) as client:
            response = client.put(
                part.url,
                content=part_data,
                headers={"Content-Length": str(actual_size)},
            )
            response.raise_for_status()
            etag = response.headers.get("ETag", "").strip('"')

        with progress_lock:
            update_progress(actual_size)

        return {"part_number": part.part_number, "etag": etag}

    def _complete_multipart_upload(
        self, url: str, parts_complete: list[dict[str, int | str]]
    ) -> httpx.Response:
        """Complete S3 multipart upload."""

        parts_complete.sort(key=lambda x: x["part_number"])
        parts_xml = ""
        for part in parts_complete:
            parts_xml += f"<Part><PartNumber>{part['part_number']}</PartNumber><ETag>{part['etag']}</ETag></Part>"  # noqa: E501
        complete_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <CompleteMultipartUpload>
        {parts_xml}
        </CompleteMultipartUpload>"""
        with httpx.Client(timeout=300) as client:
            response = client.post(
                url=url,
                content=complete_xml,
                headers={"Content-Type": "application/xml"},
            )

            response.raise_for_status()
            result = response

        self.finish_progress()

        return result

    def initiate_multipart_upload(self, initiate_url: str | None) -> str | None:
        if not initiate_url:
            raise LumlAPIError(
                "Upload URL is required for S3 multipart upload initialization"
            )

        try:
            with httpx.Client(timeout=300) as client:
                response = client.post(initiate_url)
                response.raise_for_status()

                root = ET.fromstring(response.content)

                upload_id = root.find(
                    ".//{http://s3.amazonaws.com/doc/2006-03-01/}UploadId"
                )
                if upload_id is None:
                    raise LumlAPIError("UploadId not found in S3 response")

                return upload_id.text

        except Exception as error:
            raise LumlAPIError(
                f"Failed to initiate multipart upload: {error}"
            ) from error
