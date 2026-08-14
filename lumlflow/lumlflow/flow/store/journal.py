"""The append-only transaction log — the store's source of truth.

The fsync'd append is the commit point: CAS blobs are written before it, the
SQLite index after it. A crash mid-append leaves a torn trailing line, which
`repair()` truncates; anything else that fails to parse is corruption, not a
recoverable tail, and is refused loudly.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError

from lumlflow.flow.atomic import fsync_dir
from lumlflow.flow.errors import JournalCorruption
from lumlflow.flow.store.models import Transaction

_SCAN_CHUNK_BYTES = 64 * 1024


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
            fsync_dir(self.path.parent)

    def append(self, transaction: Transaction) -> None:
        with self.path.open("ab") as handle:
            handle.write(transaction.to_line())
            handle.flush()
            os.fsync(handle.fileno())

    def replay(self) -> Iterator[Transaction]:
        if not self.path.exists():
            return
        previous_step = 0
        with self.path.open("rb") as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                transaction = _parse(line, number)
                if transaction.step <= previous_step:
                    raise JournalCorruption(
                        f"{self.path}: line {number} steps backwards"
                    )
                previous_step = transaction.step
                yield transaction

    def since(self, step: int) -> Iterator[Transaction]:
        for transaction in self.replay():
            if transaction.step > step:
                yield transaction

    def last_step(self) -> int:
        size = self.path.stat().st_size if self.path.exists() else 0
        if size == 0:
            return 0
        with self.path.open("rb") as handle:
            start = _rfind_newline(handle, size - 1) + 1
            handle.seek(start)
            line = handle.read(size - start)
        return _parse(line, 0).step

    def repair(self) -> int:
        """Truncate a torn trailing line; returns the number of bytes dropped."""
        size = self.path.stat().st_size if self.path.exists() else 0
        if size == 0:
            return 0
        with self.path.open("rb+") as handle:
            handle.seek(size - 1)
            if handle.read(1) == b"\n":
                return 0
            keep = _rfind_newline(handle, size) + 1
            handle.truncate(keep)
            handle.flush()
            os.fsync(handle.fileno())
        return size - keep


def _parse(line: bytes, number: int) -> Transaction:
    try:
        return Transaction.from_line(line)
    except ValidationError as error:
        raise JournalCorruption(f"unreadable transaction at line {number}") from error


def _rfind_newline(handle: BinaryIO, limit: int) -> int:
    """Offset of the last newline strictly before `limit`, or -1 if there is none."""
    position = limit
    while position > 0:
        start = max(0, position - _SCAN_CHUNK_BYTES)
        handle.seek(start)
        block = handle.read(position - start)
        index = block.rfind(b"\n")
        if index != -1:
            return start + index
        position = start
    return -1
