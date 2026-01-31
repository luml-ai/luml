import os
import tarfile
from pathlib import Path

import httpx


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
    def _to_path(file_path: Path | str) -> Path:
        return Path(file_path) if isinstance(file_path, str) else file_path

    @staticmethod
    def _to_path_str(file_path: Path | str) -> str:
        return str(file_path)

    def download_file(self, url: str, file_path: str | Path) -> str:
        file_path = self._to_path_str(file_path)
        try:
            timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)

            with httpx.stream("GET", url, timeout=timeout) as response:
                if response.status_code == 403:
                    raise ValueError(
                        "Access denied to model artifact. "
                        "The download URL may have expired or access is restricted. "
                        "Please regenerate the deployment or check permissions."
                    )
                elif response.status_code == 404:
                    raise ValueError(
                        "Model artifact not found at URL. The file may have been moved or deleted."
                    )
                elif response.status_code >= 400:
                    raise ValueError(
                        f"HTTP {response.status_code} error downloading model artifact: "
                        f"{response.reason_phrase}"
                    )

                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                chunk_size = self._calculate_optimal_chunk_size(total_size)

                with open(file_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)

            return file_path

        except httpx.TimeoutException as error:
            raise ValueError(f"Download timeout: {str(error)}") from error
        except httpx.ConnectError as error:
            raise ValueError(f"Connection error: {str(error)}") from error
        except OSError as error:
            raise ValueError(f"File system error: {str(error)}") from error
        except Exception as error:
            raise ValueError(f"Download failed: {str(error)}") from error

    def remove_file(self, file_path: str | Path) -> None:
        file_path = self._to_path_str(file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    def unpack_tar_archive(self, tar_path: Path | str, extraction_dir: Path | str) -> str:
        extraction_dir = self._to_path(extraction_dir)
        extraction_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(self._to_path(tar_path), "r") as tar:
            tar.extractall(extraction_dir, filter="data")

        return str(extraction_dir)

    def dir_exist(self, directory: Path | str) -> bool:
        directory = self._to_path(directory)
        return directory.exists() and any(directory.iterdir())
