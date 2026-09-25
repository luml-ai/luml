"""Mark-and-sweep over the values CAS.

The journal is the mark set: a value any transaction references is truth and
survives forever — archived branches and rewound-past history included, which
is what makes rewind promptless. Objects, previews, and logs are never pruned,
so the sweep only ever touches `values/`, where everything it finds
unreferenced is a crash leftover.

In-flight runs cover the window between staging bytes and journaling the
transaction that references them, and the two halves have to interlock. A run
**pins before it stages** and releases only after its transaction lands; the
sweep **lists blobs, then reads pins, then the journal**. A listed blob was
already installed when the pins were read, so its run had pinned by then; and a
run that releases its pin in the meantime has already appended the transaction
the journal read then sees. So a value in flight is never collected, whichever
order the two race in — a run that starts after the listing is invisible to
this sweep entirely.
"""

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
    """What this flow costs on disk — the whole store, not just the values.

    Nothing here is prunable on request: the journal, objects, previews and logs
    are kept forever by contract, so the number `status` shows has to be the
    number the disk shows, or it is an invitation to go looking for a sweep that
    would free something.
    """
    total = 0
    for entry in store.store_dir.rglob("*"):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            # A kernel scratch file that went away mid-walk is not an error;
            # it is a file that no longer costs anything.
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
