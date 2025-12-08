import base64
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import httpx

from .._exceptions import FileUploadError
from .._types import PartDetails
from .base_file_handler import BaseFileHandler


class AzureFileHandler(BaseFileHandler):
    def upload_simple(
        self,
        url: str,
        file_path: str,
        file_size: int,
        file_name: str = "",
    ) -> httpx.Response:
        try:
            update_progress = self.create_progress_bar(file_size, file_name)

            timeout = httpx.Timeout(connect=30.0, read=300.0, write=600.0, pool=30.0)

            response = httpx.put(
                url,
                content=self.create_file_generator(
                    file_path, file_size, update_progress
                ),
                headers={
                    "Content-Length": str(file_size),
                    "x-ms-blob-type": "BlockBlob",
                },
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
        try:
            update_progress = self.create_progress_bar(file_size, file_name)
            block_ids = []
            progress_lock = Lock()

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_part = {
                    executor.submit(
                        self._upload_single_block,
                        part,
                        file_path,
                        progress_lock,
                        update_progress,
                    ): part
                    for part in parts
                }

                for future in as_completed(future_to_part):
                    block_id = future.result()
                    block_ids.append(block_id)

            return self._commit_block_list(complete_url, block_ids)

        except Exception as error:
            raise FileUploadError(f"Multipart upload failed: {error}") from error

    @staticmethod
    def _get_block_id(part_number: int) -> str:
        return base64.b64encode(f"block-{part_number:08d}".encode()).decode()

    @staticmethod
    def _upload_single_block(
        part: PartDetails,
        file_path: str,
        progress_lock: Lock,
        update_progress: Callable[[int], None],
    ) -> str:
        part_size = part.end_byte - part.start_byte + 1

        with open(file_path, "rb") as f:
            f.seek(part.start_byte)
            part_data = f.read(part_size)
            actual_size = len(part_data)

        with httpx.Client(timeout=300) as client:
            response = client.put(
                part.url,
                content=part_data,
                headers={
                    "Content-Length": str(actual_size),
                    "x-ms-blob-type": "BlockBlob",
                },
            )
            response.raise_for_status()

        with progress_lock:
            update_progress(actual_size)

        return AzureFileHandler._get_block_id(part.part_number)

    def _commit_block_list(self, url: str, block_ids: list[str]) -> httpx.Response:
        block_ids.sort()

        xml_blocks = ""
        for block_id in block_ids:
            xml_blocks += f"<Latest>{block_id}</Latest>"

        block_list_xml = (
            f'<?xml version="1.0" encoding="utf-8"?><BlockList>{xml_blocks}</BlockList>'
        )

        with httpx.Client(timeout=300) as client:
            response = client.put(
                url=url,
                content=block_list_xml,
                headers={"Content-Type": "application/xml"},
            )

            response.raise_for_status()
            result = response

        self.finish_progress()

        return result
