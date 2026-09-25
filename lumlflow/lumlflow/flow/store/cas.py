"""Content-addressed blob areas: objects, values, previews, logs.

Blobs are named by their sha256 and filed under a two-character shard so no
directory grows unbounded. Writes are atomic and idempotent — the same bytes
written twice cost one file.
"""

import os
import shutil
import tempfile
from pathlib import Path

from lumlflow.flow.atomic import fsync_dir, fsync_file, replace_retry
from lumlflow.flow.hashing import hash_bytes, hash_file

_SHARD_CHARS = 2
_DIGEST_CHARS = 64
_HEX = frozenset("0123456789abcdef")


class Cas:
    def __init__(self, root: Path) -> None:
        self.root = root

    def ensure(self) -> None:
        (self.root / "tmp").mkdir(parents=True, exist_ok=True)

    def path(self, digest: str) -> Path:
        _validate(digest)
        return self.root / digest[:_SHARD_CHARS] / digest

    def exists(self, digest: str) -> bool:
        return self.path(digest).exists()

    def get(self, digest: str) -> bytes:
        return self.path(digest).read_bytes()

    def put(self, data: bytes) -> str:
        digest = hash_bytes(data)
        target = self.path(digest)
        if target.exists():
            return digest
        staged = self._stage(data)
        self._install(staged, target, discard_on_error=True)
        return digest

    def put_file(self, source: Path, *, move: bool = False) -> str:
        """Ingest a file without reading it into memory.

        `move` consumes the source — the executor's route for declared `Path`
        outputs leaving a run's scratch directory.
        """
        digest = hash_file(source)
        target = self.path(digest)
        if target.exists():
            if move:
                source.unlink()
            return digest
        if move:
            # The staged paths fsync as they write; an adopted file has to be
            # flushed here, or the commit point can outrun its own blob.
            fsync_file(source)
            self._install(source, target, discard_on_error=False)
            return digest
        staged = self._stage_copy(source)
        self._install(staged, target, discard_on_error=True)
        return digest

    def _stage(self, data: bytes) -> Path:
        handle_fd, temp_name = tempfile.mkstemp(dir=self.root / "tmp", suffix=".tmp")
        try:
            with os.fdopen(handle_fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return Path(temp_name)

    def _stage_copy(self, source: Path) -> Path:
        handle_fd, temp_name = tempfile.mkstemp(dir=self.root / "tmp", suffix=".tmp")
        try:
            with os.fdopen(handle_fd, "wb") as handle, source.open("rb") as incoming:
                shutil.copyfileobj(incoming, handle)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return Path(temp_name)

    def _install(self, staged: Path, target: Path, *, discard_on_error: bool) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            replace_retry(staged, target)
        except BaseException:
            if discard_on_error:
                staged.unlink(missing_ok=True)
            raise
        fsync_dir(target.parent)


def _validate(digest: str) -> None:
    if len(digest) != _DIGEST_CHARS or not all(char in _HEX for char in digest):
        raise ValueError("not a content hash")
