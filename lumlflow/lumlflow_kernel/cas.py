"""The store's blob areas, written from the kernel side.

`lumlflow.flow.store.cas` owns this layout; the kernel cannot import it — the
venv holds no lumlflow code — so the sha256 name, the two-character shard, and
the atomic install are restated here. A test pins the two implementations to
the same bytes and the same paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_SHARD_CHARS = 2
_FILE_CHUNK_BYTES = 1 << 20
_RETRY_DELAYS_S = (0.005, 0.02, 0.05, 0.15, 0.3)


def canonical_json(value: Any) -> bytes:
    """Sorted keys, no insignificant whitespace, NaN/Infinity rejected."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_FILE_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


class Cas:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, digest: str) -> Path:
        return self.root / digest[:_SHARD_CHARS] / digest

    def exists(self, digest: str) -> bool:
        return self.path(digest).exists()

    def get(self, digest: str) -> bytes:
        return self.path(digest).read_bytes()

    def put(
        self,
        data: bytes,
        *,
        before_stage: Callable[[str], None] | None = None,
    ) -> str:
        digest = hash_bytes(data)
        if before_stage is not None:
            before_stage(digest)
        target = self.path(digest)
        if target.exists():
            return digest
        self._install(self._stage(data), target, discard_on_error=True)
        return digest

    def put_file(
        self,
        source: Path,
        *,
        move: bool,
        before_stage: Callable[[str], None] | None = None,
    ) -> str:
        """Ingest a file without reading it into memory.

        `move` consumes the source — the route for a declared `Path` output
        leaving the run's scratch directory. A path the cell did not create
        under scratch is copied instead: the store never eats a user's file.
        """
        digest = hash_file(source)
        if before_stage is not None:
            before_stage(digest)
        target = self.path(digest)
        if target.exists():
            if move:
                source.unlink()
            return digest
        if move:
            _fsync_file(source)
            self._install(source, target, discard_on_error=False)
            return digest
        self._install(self._stage_copy(source), target, discard_on_error=True)
        return digest

    def _stage(self, data: bytes) -> Path:
        return self._write_temp(lambda handle: handle.write(data))

    def _stage_copy(self, source: Path) -> Path:
        with source.open("rb") as incoming:
            return self._write_temp(lambda handle: shutil.copyfileobj(incoming, handle))

    def _write_temp(self, fill: Any) -> Path:
        staging = self.root / "tmp"
        staging.mkdir(parents=True, exist_ok=True)
        handle_fd, temp_name = tempfile.mkstemp(dir=staging, suffix=".tmp")
        try:
            with os.fdopen(handle_fd, "wb") as handle:
                fill(handle)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return Path(temp_name)

    def _install(self, staged: Path, target: Path, *, discard_on_error: bool) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            _replace_retry(staged, target)
        except BaseException:
            # Only a staging copy may be dropped: on the move path `staged` is
            # the run's own declared output, and an install that failed is no
            # reason to destroy the file it was handed.
            if discard_on_error:
                staged.unlink(missing_ok=True)
            raise
        _fsync_dir(target.parent)


def _replace_retry(source: Path, target: Path) -> None:
    """Windows loses this race to antivirus and editors; POSIX never retries."""
    for delay in _RETRY_DELAYS_S:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            time.sleep(delay)
    os.replace(source, target)


def _fsync_file(path: Path) -> None:
    _fsync(path)


def _fsync_dir(path: Path) -> None:
    _fsync(path)


def _fsync(path: Path) -> None:
    """A no-op where the platform forbids it — Windows cannot fsync a directory."""
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
