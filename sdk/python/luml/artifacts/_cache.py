from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import time
from pathlib import Path

DEFAULT_READY_MARKER = ".materialized.ok"
DEFAULT_LOCK_FILE = ".materialize.lock"
DEFAULT_LOCK_TIMEOUT_SECONDS = 60.0


def compute_file_sha256(path: Path) -> str:
    hash_sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def default_cache_dir_for_archive(
    archive_path: Path,
    cache_root: Path,
    namespace: str,
) -> Path:
    archive_hash = compute_file_sha256(archive_path)
    return cache_root / namespace / archive_hash[:16]


def extract_archive_cached(
    archive_path: Path,
    cache_dir: Path,
    ready_marker_name: str = DEFAULT_READY_MARKER,
    lock_file_name: str = DEFAULT_LOCK_FILE,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    ready_marker = cache_dir / ready_marker_name
    lock_path = cache_dir / lock_file_name
    deadline = time.monotonic() + lock_timeout_seconds

    while True:
        if ready_marker.exists():
            return

        lock_fd = _acquire_lock_file(lock_path)
        if lock_fd is None:
            if time.monotonic() >= deadline:
                msg = f"Timed out waiting for cache extraction lock at '{lock_path}'."
                raise TimeoutError(msg)
            time.sleep(0.05)
            continue

        try:
            if ready_marker.exists():
                return
            _clear_cache_dir(cache_dir, lock_file_name)
            with tarfile.open(str(archive_path), "r") as tar:
                tar.extractall(path=str(cache_dir), filter="data")  # noqa: S202
            ready_marker.write_text("ok\n", encoding="utf-8")
            return
        finally:
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)


def _acquire_lock_file(lock_path: Path) -> int | None:
    try:
        return os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError:
        return None


def _clear_cache_dir(cache_dir: Path, lock_file_name: str) -> None:
    for path in cache_dir.iterdir():
        if path.name == lock_file_name:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
