from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.dsl import loader, normalize
from lumlflow.flow.dsl.accept import (
    CELL_SUFFIX,
    AcceptedCell,
    Batch,
    CellReadError,
    cell_paths,
)
from lumlflow.flow.dsl.tree import WorkspaceTree, scan_workspace
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.store.models import (
    CellNoted,
    CellRemoved,
    FlagSet,
    Op,
    WorkspaceCodeChanged,
)

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

Tier = Literal["live", "quiesce", "cold"]

MIXED_EDITING = "mixed_editing"
MIXED_EDITING_DETAIL = "attribution uncertain. two authors edited in one window"
SEVERAL_AGENTS_DETAIL = (
    "attribution uncertain. {count} agents were registered, and any of them "
    "or you could have written this"
)

_MAX_PASSES = 3
_NAMED_CHANGES = 3


@dataclass(frozen=True)
class AcceptedFile:
    digest: str
    step: int
    uid: str
    branch: str


@dataclass(frozen=True)
class Reconciliation:
    accepted: list[AcceptedCell] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    projected: list[str] = field(default_factory=list)
    step: int | None = None

    @property
    def moved(self) -> bool:
        return bool(self.accepted or self.removed)


def reconcile(
    session: "FlowSession",
    *,
    tier: Tier = "quiesce",
    actor: str | None = None,
    intent: str | None = None,
) -> Reconciliation:
    worktree = session.worktree
    if not worktree.projects_files():
        return Reconciliation()
    branch = worktree.branch
    branch_id = session.store.branches.get(branch).branch_id
    registered = session.store.index.agent_sessions()
    explicit = actor is not None and actor != "user"
    sole_agent = registered[0] if len(registered) == 1 else None
    author = (
        str(actor)
        if explicit
        else sole_agent.actor
        if sole_agent is not None
        else "user"
    )

    completed = _complete_projections(session, branch_id)
    batch = Batch()
    accept = partial(
        _accept_files,
        session,
        batch,
        branch=branch,
        actor=author,
    )
    seen = accept()
    removed = _accept_removals(session, batch, branch_id=branch_id, seen=seen)
    if removed:
        accept()
    if not batch.ops:
        return Reconciliation(projected=completed)

    ops: list[Op] = list(batch.ops)
    if not explicit and sole_agent is not None:
        ops.append(FlagSet(flag=MIXED_EDITING, detail=MIXED_EDITING_DETAIL))
    elif not explicit and len(registered) > 1:
        ops.append(
            FlagSet(
                flag=MIXED_EDITING,
                detail=SEVERAL_AGENTS_DETAIL.format(count=len(registered)),
            )
        )
    transaction = session.store.commit(
        ops,
        intent=intent or _intent(tier, batch.accepted, removed),
        actor=author,
        branch=branch_id,
        offline=tier == "cold",
    )
    session.store.save_manifest()
    return Reconciliation(
        accepted=list(batch.accepted),
        removed=removed,
        projected=completed,
        step=transaction.step,
    )


def sync_workspace_code(
    root: Path, sessions: Iterable["FlowSession"], *, actor: str = "system"
) -> dict[Path, list[str]]:
    tree = scan_workspace(root)
    changed: dict[Path, list[str]] = {}
    for session in sessions:
        known = session.store.index.workspace_tree()
        if known is not None and known.tree_hash == tree.tree_hash:
            continue
        paths = (
            tree.changed_paths(WorkspaceTree(known.tree_hash, dict(known.files)))
            if known is not None
            else []
        )
        session.store.commit(
            [
                WorkspaceCodeChanged(
                    tree_hash=tree.tree_hash,
                    previous_tree_hash=known.tree_hash if known else None,
                    changed_paths=paths,
                    files=dict(tree.files),
                )
            ],
            intent=_code_intent(paths),
            actor=actor,
        )
        if paths:
            changed[session.ref.path] = paths
    return changed


def _accept_files(
    session: "FlowSession",
    batch: Batch,
    *,
    branch: str,
    actor: str,
) -> set[str]:
    seen: set[str] = set()
    cells = session.worktree.cells_dir
    if not cells.is_dir():
        return seen
    level = _Level(session, batch, branch=branch)
    unreadable = False
    for _ in range(_MAX_PASSES):
        moved = False
        deferred_rewires: list[AcceptedCell] = []
        read: list[tuple[Path, str]] = []
        for path in cell_paths(cells):
            if path.is_symlink() and not path.exists():
                unreadable = True
                continue
            unmoved = level.uid_of(path)
            if unmoved is not None:
                seen.add(unmoved)
                continue
            try:
                accepted = session.acceptance.accept_path(
                    path,
                    branch=branch,
                    actor=actor,
                    batch=batch,
                )
            except CellReadError:
                unreadable = True
                continue
            seen.add(accepted.uid)
            read.append((path, accepted.uid))
            moved = moved or not accepted.unchanged
            if accepted.renamed_from is not None and accepted.rewire:
                unplaced = _rewire(session, accepted, batch, branch=branch)
                if unplaced:
                    deferred_rewires.append(replace(accepted, rewire=unplaced))
        # A consumer that was renamed in this same burst is only reachable once
        # its own file has been accepted under its new name — which has happened
        # by the end of the pass. Without this it would keep the old spelling
        # for good: no later pass has a rename left to notice.
        for pending_rewire in deferred_rewires:
            _rewire(session, pending_rewire, batch, branch=branch)
        if not moved:
            # Nothing in this pass wrote a file or a version, so what is on disk
            # is what the branch head holds — the one moment a stamp can be
            # taken that the next reconciliation is entitled to trust.
            level.remember(read)
            break
    if unreadable:
        seen.update(
            batch.slice_over(
                session.store.index.slice_versions(
                    session.store.branches.get(branch).branch_id
                )
            )
        )
    return seen


class _Level:
    def __init__(self, session: "FlowSession", batch: Batch, *, branch: str) -> None:
        self._session = session
        self._batch = batch
        self._branch = branch
        self._known = session.accepted_files

    def _settled(self) -> bool:
        return not self._batch.ops

    def uid_of(self, path: Path) -> str | None:
        if not self._settled():
            return None
        known = self._known.get(path.name)
        if known is None or known.branch != self._branch:
            return None
        if known.step != self._session.store.next_step:
            return None
        digest = _digest(path)
        return known.uid if digest is not None and digest == known.digest else None

    def remember(self, read: Sequence[tuple[Path, str]]) -> None:
        if not self._settled():
            return
        step = self._session.store.next_step
        for path, uid in read:
            digest = _digest(path)
            if digest is None:
                self._known.pop(path.name, None)
                continue
            self._known[path.name] = AcceptedFile(
                digest=digest, step=step, uid=uid, branch=self._branch
            )


def _digest(path: Path) -> str | None:
    try:
        return hash_bytes(path.read_bytes())
    except OSError:
        return None


def _rewire(
    session: "FlowSession",
    accepted: AcceptedCell,
    batch: Batch,
    *,
    branch: str,
) -> list[str]:
    here = batch.slice_over(
        session.store.index.slice_versions(session.store.branches.get(branch).branch_id)
    )
    unplaced = []
    for uid in accepted.rewire:
        consumer = here.get(uid)
        if consumer is None:
            continue
        path = session.acceptance.cell_path(consumer.slug)
        if not path.exists():
            unplaced.append(uid)
            continue
        try:
            source = path.read_bytes().decode("utf-8-sig")
        except (OSError, UnicodeDecodeError):
            unplaced.append(uid)
            continue
        cell = loader.parse(source).cell
        if cell is None:
            continue
        canonical = {
            reference: reference.replace(
                f"{accepted.renamed_from}.", f"{accepted.slug}.", 1
            )
            for reference in cell.consumes.values()
            if reference.split(".", 1)[0] == accepted.renamed_from
        }
        if not canonical:
            continue
        rewritten = normalize.rewrite(
            source, cell, uid=cell.uid or uid, canonical=canonical
        )
        if rewritten != source:
            atomic_write_bytes(path, rewritten.encode("utf-8"))
    return unplaced


def _accept_removals(
    session: "FlowSession", batch: Batch, *, branch_id: str, seen: Collection[str]
) -> list[str]:
    if session.worktree.bound() is None:
        return []
    here = batch.slice_over(session.store.index.slice_versions(branch_id))
    removed = []
    for uid, version in sorted(here.items(), key=lambda item: item[1].slug):
        if uid in seen:
            continue
        batch.ops.append(CellRemoved(uid=uid, branch_id=branch_id))
        batch.removed.add(uid)
        batch.overlay.pop(uid, None)
        removed.append(version.slug)
    return removed


def _complete_projections(session: "FlowSession", branch_id: str) -> list[str]:
    """Sort out the files a store-side edit got ahead of.

    A file that diverged from the head but holds bytes from a version this lane
    selected before is not an edit — it is the projection of a store-side edit
    that has not landed yet, and accepting it would write the old version back
    over the new one. So the store wins and the file catches up. A version seen
    only on another lane is an ordinary file edit on this one.

    Only a version *older* than the head can be one of these: a projection is
    the store having got ahead of the files, so the bytes left behind are the
    bytes from before. Newer ones are edits that happen to restate something
    the store has seen — re-applying an edit a rewind took back, or carrying a
    fork's version over by hand — and completing those would quietly undo the
    author's work and accept nothing in its place.

    A file an author reverted by hand to an older version reads the same way,
    and is completed too: content cannot tell the two apart, and of the two
    readings only this one can lose nothing — every version is still in the
    store, and the revert is one rewind away from being made again. The note
    makes that completion visible and names the rewind escape hatch.
    """
    store = session.store
    here = store.index.slice_versions(branch_id)
    completed: list[str] = []
    for uid, version in sorted(here.items(), key=lambda item: item[1].slug):
        candidate = session.worktree.cells_dir / f"{version.slug}{CELL_SUFFIX}"
        if candidate.is_symlink() and not candidate.exists():
            continue
        path = session.acceptance.cell_path(version.slug)
        if not path.exists():
            continue
        source = store.objects.get(version.raw_source_ref)
        try:
            held = path.read_bytes()
        except OSError:
            continue
        if held == source:
            continue
        older = store.index.version_by_source(
            uid,
            hash_bytes(held),
            version_ids=store.branches.selected_versions(branch_id, uid),
        )
        if older is None or older.created_step >= version.created_step:
            continue
        atomic_write_bytes(path, source)
        sentence = (
            f"projection completed for `{version.slug}`: restored version "
            f"`{version.version_id}`; use `rewind` to keep the file's bytes instead"
        )
        store.commit(
            [
                CellNoted(
                    uid=uid,
                    kind="projection_completed",
                    sentence=sentence,
                    version_id=version.version_id,
                )
            ],
            intent=sentence,
            actor="system",
            branch=branch_id,
        )
        completed.append(version.slug)
    return completed


def _intent(
    tier: Tier, accepted: Sequence[AcceptedCell], removed: Sequence[str]
) -> str:
    changed = {cell.slug for cell in accepted} | set(removed)
    if tier == "cold":
        return f"offline edits: {len(changed)} cells changed"
    summaries = [cell.summary for cell in accepted if cell.summary]
    summaries += [f"deleted {slug}" for slug in removed]
    if not summaries:
        return f"{len(changed)} cells changed"
    if len(summaries) <= _NAMED_CHANGES:
        return "; ".join(summaries)
    return f"{len(changed)} cells changed"


def _code_intent(paths: Sequence[str]) -> str:
    if not paths:
        return "recorded the workspace's shared code"
    named = ", ".join(f"`{path}`" for path in paths[:_NAMED_CHANGES])
    rest = len(paths) - min(len(paths), _NAMED_CHANGES)
    return f"{named}{f' and {rest} more' if rest else ''} changed"
