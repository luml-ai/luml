from collections.abc import Callable, Generator

import httpx

from dataforce.api._exceptions import FileDownloadError, FileUploadError


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
        total_size: int, description: str = ""
    ) -> Callable[[int], None]:
        uploaded = 0
        description_shown = False

        def update_progress(chunk_size: int) -> None:
            nonlocal uploaded, description_shown
            uploaded += chunk_size

            if not description_shown and description:
                print(f"{description}")  # noqa: T201
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

    def upload_file_with_progress(
        self,
        url: str,
        file_path: str,
        file_size: int,
        description: str = "",
        headers: dict | None = None,
    ) -> httpx.Response:
        try:
            update_progress = self.create_progress_bar(file_size, description)

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
        self, url: str, file_path: str, description: str = ""
    ) -> str:
        try:
            timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)

            with httpx.stream("GET", url, timeout=timeout) as response:
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                update_progress = self.create_progress_bar(total_size, description)

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
