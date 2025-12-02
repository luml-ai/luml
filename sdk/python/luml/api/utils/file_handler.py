from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from xml.etree import ElementTree as ET

import httpx

from .._exceptions import FileDownloadError, FileUploadError, LumlAPIError
from .._types import (
    PartDetails,
)


class FileHandler:
    @staticmethod
    def _calculate_optimal_chunk_size(file_size: int) -> int:
        if file_size < 10485760:  # 10mb
            return 1048576  # 1mb
        if file_size < 52428800:  # 50mb
            return 4194304  # 4mb
        if file_size < 104857600:  # 100mb
            return 16777216  # 16mb
        if file_size < 524288000:  # 500mb
            return 67108864  # 64mb
        if file_size < 1073741824:  # 1gb
            return 134217728  # 128mb
        if file_size < 5368709120:  # 5gb
            return 268435456  # 256mb
        return 268435456  # 256mb

    @staticmethod
    def create_progress_bar(
        total_size: int, file_name: str = ""
    ) -> Callable[[int], None]:
        uploaded = 0
        description_shown = False

        def update_progress(chunk_size: int) -> None:
            nonlocal uploaded, description_shown
            uploaded += chunk_size

            if not description_shown and file_name:
                print(f'Uploading file "{file_name}"...')  # noqa: T201
                description_shown = True

            if total_size > 0:
                progress = (uploaded / total_size) * 100
                bar_length = 30
                filled_length = int(bar_length * uploaded // total_size)
                bar = "=" * filled_length + ">" + " " * (bar_length - filled_length - 1)
                print(f"\r[{bar}] {progress:.1f}%", end="", flush=True)  # noqa: T201

        return update_progress

    @staticmethod
    def finish_progress() -> None:
        print()  # noqa: T201

    def create_file_generator(
        self,
        file_path: str,
        file_size: int,
        update_progress: Callable[[int], None],
        chunk_size: int | None = None,
    ) -> Generator[bytes, None, None]:
        chunk_size = (
            self._calculate_optimal_chunk_size(file_size)
            if chunk_size is None
            else chunk_size
        )

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                update_progress(len(chunk))
                yield chunk

    def upload_simple_file_with_progress(
        self,
        url: str,
        file_path: str,
        file_size: int,
        file_name: str = "",
        headers: dict | None = None,
    ) -> httpx.Response:
        try:
            update_progress = self.create_progress_bar(file_size, file_name)

            timeout = httpx.Timeout(connect=30.0, read=300.0, write=600.0, pool=30.0)

            response = httpx.put(
                url,
                content=self.create_file_generator(
                    file_path, file_size, update_progress
                ),
                headers={**{"Content-Length": str(file_size)}, **(headers or {})},
                timeout=timeout,
            )

            self.finish_progress()
            response.raise_for_status()
            return response
        except Exception as error:
            self.finish_progress()
            raise FileUploadError(f"Upload failed: {error}") from error

    def download_file_with_progress(
        self, url: str, file_path: str, file_name: str = ""
    ) -> str:
        try:
            timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)

            with httpx.stream("GET", url, timeout=timeout) as response:
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                update_progress = self.create_progress_bar(total_size, file_name)

                chunk_size = self._calculate_optimal_chunk_size(total_size)

                with open(file_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        update_progress(len(chunk))

                self.finish_progress()
            return file_path
        except Exception as error:
            self.finish_progress()
            raise FileDownloadError(f" Error: {error}") from error

    def _complete_multipart_upload(
        self, url: str, parts_complete: list[dict[str, int | str]]
    ) -> httpx.Response:
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

    @staticmethod
    def _upload_single_part(
        part: PartDetails,
        file_path: str,
        progress_lock: Lock,
        update_progress: Callable[[int], None],
    ) -> dict[str, int | str]:
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

    def upload_multipart(
        self,
        parts: list[PartDetails],
        complete_url: str,
        file_size: int,
        file_path: str,
        file_name: str = "",
        max_workers: int = 5,
    ) -> httpx.Response:
        try:
            update_progress = self.create_progress_bar(file_size, file_name)
            parts_complete = []
            progress_lock = Lock()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
    def initiate_multipart_upload(initiate_url: str) -> str | None:
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
