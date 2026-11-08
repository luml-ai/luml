from __future__ import annotations

import hashlib
import os
import shutil
import sys
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
    archive_hash = compute_file_sha256(archive_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    ready_marker = cache_dir / ready_marker_name
    lock_path = cache_dir / lock_file_name
    deadline = time.monotonic() + lock_timeout_seconds

    while True:
        lock_fd = _acquire_lock_file(lock_path)
        if lock_fd is None:
            if _remove_stale_lock(lock_path, lock_timeout_seconds):
                continue
            if time.monotonic() >= deadline:
                msg = f"Timed out waiting for cache extraction lock at '{lock_path}'."
                raise TimeoutError(msg)
            time.sleep(0.05)
            continue

        try:
            if (
                ready_marker.exists()
                and ready_marker.read_text(encoding="utf-8").strip() == archive_hash
            ):
                return
            _clear_cache_dir(cache_dir, lock_file_name)
            with tarfile.open(str(archive_path), "r") as tar:
                tar.extractall(path=str(cache_dir), filter="data")  # noqa: S202
            ready_marker.write_text(archive_hash + "\n", encoding="utf-8")
            return
        finally:
            same_file = _is_same_lock(lock_path, lock_fd)
            os.close(lock_fd)
            if same_file:
                _unlink_lock_with_retry(lock_path)


def _is_same_lock(lock_path: Path, lock_fd: int) -> bool:
    try:
        fstat_ino = os.fstat(lock_fd).st_ino
        stat_ino = lock_path.stat().st_ino
        if fstat_ino != 0 and stat_ino != 0:
            return fstat_ino == stat_ino
        return lock_path.read_text(encoding="ascii").strip() == str(os.getpid())
    except OSError:
        return False


def _unlink_lock_with_retry(lock_path: Path, retries: int = 5) -> None:
    for attempt in range(retries):
        try:
            lock_path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt < retries - 1:
                time.sleep(0.02)
            else:
                if not lock_path.exists():
                    return
                raise


def _acquire_lock_file(lock_path: Path) -> int | None:
    try:
        lock_fd = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError:
        return None
    os.write(lock_fd, str(os.getpid()).encode("ascii"))
    return lock_fd


def _is_process_alive(pid: int) -> bool:
    if pid <= 0 or pid > 0xFFFFFFFF:
        return False
    if sys.platform == "win32":
        import ctypes

        try:
            kernel32 = ctypes.windll.kernel32
            process_query_limited_information = 0x1000
            still_active = 259
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        except (OverflowError, TypeError, ValueError, ctypes.ArgumentError):
            return False
        if not handle:
            return bool(kernel32.GetLastError() == 5)  # ERROR_ACCESS_DENIED
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return bool(exit_code.value == still_active)
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):
        return False
    except PermissionError:
        return True
    return True


def _remove_stale_lock(lock_path: Path, timeout_seconds: float) -> bool:
    try:
        lock_stat = lock_path.stat()
        if time.time() - lock_stat.st_mtime < timeout_seconds:
            return False
        try:
            owner_pid = int(lock_path.read_text(encoding="ascii"))
        except (ValueError, UnicodeError):
            owner_pid = 0
        if owner_pid > 0 and _is_process_alive(owner_pid):
            return False
        current_stat = lock_path.stat()
        if (
            current_stat.st_ino == lock_stat.st_ino
            and current_stat.st_mtime_ns == lock_stat.st_mtime_ns
        ):
            try:
                _unlink_lock_with_retry(lock_path, retries=3)
            except OSError:
                return False
        return True
    except FileNotFoundError:
        return True
    except PermissionError:
        return False


def _clear_cache_dir(cache_dir: Path, lock_file_name: str) -> None:
    for path in cache_dir.iterdir():
        if path.name == lock_file_name:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
