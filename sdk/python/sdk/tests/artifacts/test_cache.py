import io
import os
import tarfile
import time
from pathlib import Path

import pytest

from luml.artifacts._cache import extract_archive_cached


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    path = tmp_path / "archive.tar"
    with tarfile.open(path, "w") as tar:
        member = tarfile.TarInfo("payload.txt")
        member.size = 7
        tar.addfile(member, io.BytesIO(b"payload"))
    return path


@pytest.mark.parametrize(
    "contents", ["", "invalid", "999999999", "999999999999999999999999999999"]
)
def test_expired_lock_recovers(archive: Path, tmp_path: Path, contents: str) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    lock = cache / ".materialize.lock"
    lock.write_text(contents)
    expired = time.time() - 10
    os.utime(lock, (expired, expired))
    extract_archive_cached(archive, cache, lock_timeout_seconds=0.1)
    assert (cache / "payload.txt").read_text() == "payload"
    assert not lock.exists()


def test_recent_lock_eventually_recovers(archive: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ".materialize.lock").touch()
    extract_archive_cached(archive, cache, lock_timeout_seconds=0.1)
    assert (cache / "payload.txt").exists()


def test_live_lock_is_not_stolen(archive: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    lock = cache / ".materialize.lock"
    lock.write_text(str(os.getpid()))
    expired = time.time() - 10
    os.utime(lock, (expired, expired))
    with pytest.raises(TimeoutError, match="cache extraction lock"):
        extract_archive_cached(archive, cache, lock_timeout_seconds=0.1)
    assert lock.exists()


def test_legacy_ready_marker_is_refreshed(archive: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ".materialized.ok").write_text("ok\n")
    (cache / "payload.txt").write_text("wrong archive")
    extract_archive_cached(archive, cache)
    assert (cache / "payload.txt").read_text() == "payload"


def test_failed_extraction_can_retry(archive: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    invalid_archive = tmp_path / "invalid.tar"
    invalid_archive.write_text("invalid")
    with pytest.raises(tarfile.ReadError):
        extract_archive_cached(invalid_archive, cache)
    assert not (cache / ".materialized.ok").exists()
    assert not (cache / ".materialize.lock").exists()
    extract_archive_cached(archive, cache)
    assert (cache / "payload.txt").exists()


def test_completed_cache_is_reused(archive: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    extract_archive_cached(archive, cache)
    (cache / "sentinel").touch()
    extract_archive_cached(archive, cache)
    assert (cache / "sentinel").exists()


def test_concurrent_waiters_recover_one_stale_lock(
    archive: Path, tmp_path: Path
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    cache = tmp_path / "cache"
    cache.mkdir()
    lock = cache / ".materialize.lock"
    lock.touch()
    expired = time.time() - 10
    os.utime(lock, (expired, expired))
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(
                extract_archive_cached, archive, cache, lock_timeout_seconds=1.0
            )
            for _ in range(4)
        ]
        for future in futures:
            future.result(timeout=5)
    assert (cache / "payload.txt").read_text() == "payload"
    assert not lock.exists()
