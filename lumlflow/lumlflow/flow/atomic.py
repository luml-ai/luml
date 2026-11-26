"""Atomic file replacement, portable to Windows.

Every durable write in the store lands as temp + `os.replace`. On Windows the
replace can lose a race with an antivirus or an editor holding the target
open, which surfaces as a transient `PermissionError` — retried here rather
than propagated as a write failure.
"""

import os
import tempfile
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

_RETRY_DELAYS_S = (0.005, 0.02, 0.05, 0.15, 0.3)


def replace_retry(
    source: Path, target: Path, *, before_replace: Callable[[], None] | None = None
) -> None:
    for delay in _RETRY_DELAYS_S:
        if before_replace is not None:
            before_replace()
        try:
            os.replace(source, target)
            return
        except PermissionError:
            time.sleep(delay)
    if before_replace is not None:
        before_replace()
    os.replace(source, target)


def unlink_retry(path: Path) -> None:
    """Remove a file, waiting out whoever is holding it open.

    Windows refuses to unlink a file another process has open, which for a
    projected cell is an editor, an agent, or a virus scanner that got there
    first — transient every time, and not worth failing a checkout over.
    """
    for delay in _RETRY_DELAYS_S:
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(delay)
    path.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes, *, fsync: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with staged_bytes(path, data, fsync=fsync) as staged:
        replace_retry(staged, path)
    if fsync:
        fsync_dir(path.parent)


@contextmanager
def staged_bytes(
    path: Path, data: bytes, *, mode: int | None = None, fsync: bool = True
) -> Generator[Path]:
    """Stage bytes beside their destination. The caller publishes them on success."""
    handle_fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            if mode is not None:
                temp_path.chmod(mode)
            if fsync:
                os.fsync(handle.fileno())
        yield temp_path
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def fsync_file(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
