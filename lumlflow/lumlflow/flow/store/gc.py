from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from lumlflow.flow.store.journal import Journal
from lumlflow.flow.store.models import RunRecorded

if TYPE_CHECKING:
    from lumlflow.flow.store.flowstore import FlowStore


@dataclass(frozen=True)
class SweepReport:
    collected: int
    freed_bytes: int
    kept: int


def sweep(store: "FlowStore") -> SweepReport:
    blobs = list(_blobs(store.values.root))
    with store.index.protect_value_sweep() as pinned:
        keep = pinned | journal_referenced(store.journal)
        collected = freed = kept = 0
        for blob in blobs:
            if blob.name in keep:
                kept += 1
                continue
            freed += blob.stat().st_size
            blob.unlink()
            collected += 1
    return SweepReport(collected=collected, freed_bytes=freed, kept=kept)


def disk_bytes(store: "FlowStore") -> int:
    total = 0
    for entry in store.store_dir.rglob("*"):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def journal_referenced(journal: Journal) -> set[str]:
    return {
        output.value_ref
        for transaction in journal.replay()
        for op in transaction.ops
        if isinstance(op, RunRecorded)
        for output in op.outputs.values()
        if output.value_ref is not None
    }


def _blobs(root: Path) -> Iterator[Path]:
    """Installed blobs only. `tmp/` holds half-written stages whose writer may
    still hold the fd, so reaping it needs a quiet moment the sweep cannot
    assume it has."""
    if not root.is_dir():
        return
    for shard in sorted(root.iterdir()):
        if shard.is_dir() and shard.name != "tmp":
            yield from (blob for blob in sorted(shard.iterdir()) if blob.is_file())
