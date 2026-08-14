"""Reconciliation: one primitive, three tiers.

Diff the worktree against the branch head and accept whatever diverged. The
watcher calls it with events in hand, every version-resolving op calls it
first, and a daemon that just started calls it over a directory nobody was
watching. Same code each time — which is what lets the watcher be a latency
optimization rather than a correctness dependency: a missed event costs
milliseconds, never a wrong version.

The three tiers differ only in the envelope they commit under. Live and
quiesce attribute to whoever holds the worktree and land as an ordinary
transaction; a cold start lands as one coarse `offline` transaction attributed
to `user`, because the fine-grained sequence genuinely was not recorded and
claiming otherwise would be a lie the UI would then render.
"""

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.dsl import loader, normalize
from lumlflow.flow.dsl.accept import CELL_SUFFIX, AcceptedCell, Batch
from lumlflow.flow.dsl.tree import WorkspaceTree, scan_workspace
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.store.models import CellRemoved, FlagSet, Op, WorkspaceCodeChanged

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

Tier = Literal["live", "quiesce", "cold"]

MIXED_EDITING = "mixed_editing"
MIXED_EDITING_DETAIL = "attribution uncertain. two authors edited in one window"

_CELL_GLOB = f"*{CELL_SUFFIX}"
# One pass names every cell, a second binds the references that pass one could
# not resolve, and a third takes up the files a rename rewired. Nothing a
# fourth could find: slugs, uids and bindings are all settled by then.
_MAX_PASSES = 3
_NAMED_CHANGES = 3


@dataclass(frozen=True)
class AcceptedFile:
    """A cell file as it stood when acceptance last found nothing to do.

    `digest` is over the file's bytes; `step` is the store's next step at that
    moment, which is what a later commit invalidates.
    """

    digest: str
    step: int
    uid: str
    branch: str


@dataclass(frozen=True)
class Reconciliation:
    """`projected` names cells whose files the store completed, not the author."""

    accepted: list[AcceptedCell] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    projected: list[str] = field(default_factory=list)
    step: int | None = None

    @property
    def moved(self) -> bool:
        return bool(self.accepted or self.removed)


@dataclass
class _Pending:
    """Files the store is ahead of: written back, or left for a working agent.

    `withheld` maps the slug whose file was left alone to the cell it holds —
    the name acceptance skips, and the identity removal detection must still
    count as present on disk.
    """

    completed: list[str] = field(default_factory=list)
    withheld: dict[str, str] = field(default_factory=dict)


def reconcile(
    session: "FlowSession",
    *,
    tier: Tier = "quiesce",
    actor: str | None = None,
    intent: str | None = None,
) -> Reconciliation:
    """Bring the store level with the files, and journal what that took."""
    worktree = session.worktree
    if not worktree.projects_files():
        return Reconciliation()
    branch = worktree.branch
    branch_id = session.store.branches.get(branch).branch_id
    holder = None if tier == "cold" else worktree.holder()
    author = actor or (holder.actor if holder is not None else "user")

    pending = _complete_projections(session, branch_id)
    batch = Batch()
    accept = partial(
        _accept_files,
        session,
        batch,
        branch=branch,
        actor=author,
        skip=set(pending.withheld),
    )
    seen = accept() | set(pending.withheld.values())
    removed = _accept_removals(session, batch, branch_id=branch_id, seen=seen)
    if removed:
        # A name that left the branch is a namespace change like any other:
        # its consumers re-bind, and the ones left pointing at nothing say so.
        accept()
    if not batch.ops:
        return Reconciliation(projected=pending.completed)

    ops: list[Op] = list(batch.ops)
    if holder is not None:
        ops.append(FlagSet(flag=MIXED_EDITING, detail=MIXED_EDITING_DETAIL))
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
        projected=pending.completed,
        step=transaction.step,
    )


def sync_workspace_code(
    root: Path, sessions: Iterable["FlowSession"], *, actor: str = "system"
) -> dict[Path, list[str]]:
    """Fold the workspace's shared code into every flow that could import it.

    The transition is appended to each hosted flow's own journal — a flow has
    to rebuild its index standalone, and a hash it never recorded is a hash it
    cannot derive staleness against. Returns the changed paths per flow, which
    is what says whose kernel has modules to forget.
    """
    tree = scan_workspace(root)
    changed: dict[Path, list[str]] = {}
    for session in sessions:
        known = session.store.index.workspace_tree()
        if known is not None and known.tree_hash == tree.tree_hash:
            continue
        # The first observation marks nothing: there is no previous tree to have
        # changed from, and calling every cell stale over that would be a
        # verdict about a baseline that never existed.
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
    skip: Collection[str] = (),
) -> set[str]:
    """Accept every cell file, until a pass finds nothing left to move.

    Idempotent by construction, so re-reading a directory nobody touched writes
    nothing — and, past the first look, does not re-parse it either: see
    `_Level`, which is what keeps a burst of verbs from paying for the same
    nine ASTs nine times over. Returns the cells the files were found to hold —
    which is what says, by elimination, whose file is gone.
    """
    seen: set[str] = set()
    cells = session.worktree.cells_dir
    if not cells.is_dir():
        return seen
    held = _held_versions(session, branch)
    level = _Level(session, batch, branch=branch, usable=not held)
    for _ in range(_MAX_PASSES):
        moved = False
        deferred_rewires: list[AcceptedCell] = []
        read: list[tuple[Path, str]] = []
        for path in sorted(cells.glob(_CELL_GLOB)):
            if path.stem in skip:
                continue
            unmoved = level.uid_of(path)
            if unmoved is not None:
                seen.add(unmoved)
                continue
            accepted = session.acceptance.accept_path(
                path,
                branch=branch,
                actor=actor,
                batch=batch,
                base_version_id=held.get(path.stem),
            )
            seen.add(accepted.uid)
            read.append((path, accepted.uid))
            moved = moved or not accepted.unchanged
            if not accepted.unchanged:
                # Whatever the file held before, it holds this now — from the
                # *next* reconciliation's point of view. Within this one the
                # parent stays put, or a second pass would supersede the
                # version it just wrote and drop the divergence with it.
                session.worktree.deferred.pop(accepted.uid, None)
            if accepted.renamed_from is not None and accepted.rewire:
                unplaced = _rewire(session, accepted, batch, branch=branch, skip=skip)
                if unplaced:
                    deferred_rewires.append(replace(accepted, rewire=unplaced))
        # A consumer that was renamed in this same burst is only reachable once
        # its own file has been accepted under its new name — which has happened
        # by the end of the pass. Without this it would keep the old spelling
        # for good: no later pass has a rename left to notice.
        for pending_rewire in deferred_rewires:
            _rewire(session, pending_rewire, batch, branch=branch, skip=skip)
        if not moved:
            # Nothing in this pass wrote a file or a version, so what is on disk
            # is what the branch head holds — the one moment a stamp can be
            # taken that the next reconciliation is entitled to trust.
            level.remember(read)
            return seen
    return seen


class _Level:
    """Which cell files are known to hold exactly what the branch head does.

    Reconciliation is idempotent, and the workbench leans on that hard: a
    notebook opening asks twenty verbs in a second and every one of them
    reconciles first, re-reading and re-parsing a directory that cannot have
    moved between two calls a millisecond apart. Parsing is the expensive half
    of acceptance — an AST per cell, deep-copied and unparsed to build the bound
    source — so this skips it for a file that is byte-for-byte the one already
    accepted.

    The file is still read every time. Only the parse is skipped, and only for
    bytes that hash to what was accepted — a timestamp would have been cheaper
    and would have made this a bet on the filesystem's clock, which is a
    resolution that varies by platform and a bet the guarantee here cannot
    afford. Reading a cell costs microseconds; parsing one costs milliseconds.

    Three more conditions, because a file standing still is not the only way
    what it means can move:

    - The store's `next_step`. Every rename, adopt, delete, checkout and run
      commits a transaction, and those are what change the *namespace* a file's
      references bind against — an unchanged file can still need re-binding
      after one, so a commit drops every stamp rather than only the toucher's.
    - The branch. A stamp is a claim about one branch's head, never about a file.
    - An empty batch. Inside a reconciliation the namespace moves before it is
      committed — a removal is what sends every consumer back through binding —
      so once anything is drafted the fast path is off for the rest of the pass,
      and nothing is stamped until a whole pass has found nothing to do.

    A deferred projection — the worktree lock holding an agent's edit — takes
    the fast path off entirely: those accepts carry a base version the stamp
    does not describe, and they are rare enough not to be worth encoding.
    """

    def __init__(
        self, session: "FlowSession", batch: Batch, *, branch: str, usable: bool
    ) -> None:
        self._session = session
        self._batch = batch
        self._branch = branch
        self._usable = usable
        self._known = session.accepted_files

    def _settled(self) -> bool:
        return self._usable and not self._batch.ops

    def uid_of(self, path: Path) -> str | None:
        """The uid this file was last accepted as, if nothing can have moved."""
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


def _held_versions(session: "FlowSession", branch: str) -> dict[str, str]:
    """Which files are known to hold an older version than the branch head.

    Only deferred projections: everywhere else the files are the head, and
    naming a parent the acceptance would have found anyway says nothing. Here
    it is the difference between an edit that derived from what the author saw
    and one the daemon pretends derived from a version they never read.
    """
    deferred = session.worktree.deferred
    if not deferred:
        return {}
    here = session.store.index.slice_versions(
        session.store.branches.get(branch).branch_id
    )
    return {
        here[uid].slug: version_id
        for uid, version_id in deferred.items()
        if version_id is not None and uid in here
    }


def _rewire(
    session: "FlowSession",
    accepted: AcceptedCell,
    batch: Batch,
    *,
    branch: str,
    skip: Collection[str] = (),
) -> list[str]:
    """Rewrite the consumers that still spell a renamed cell's old name.

    A rename costs nothing because references bind to uids: the files change
    spelling, the bound sources do not, and every consumer keeps its
    `definition_hash` — so nothing goes stale and no cache is lost. The next
    acceptance pass picks the rewritten files up.

    Consumers are addressed by identity and looked up at the name the store
    currently gives them; the ones whose file is not there are returned rather
    than dropped, because a consumer renamed in the same burst is between names
    until its own file has been accepted.

    A file already waiting on a projection is left alone: the version that
    outran it will be written whole when the worktree is free, spelling and
    all.
    """
    here = batch.slice_over(
        session.store.index.slice_versions(session.store.branches.get(branch).branch_id)
    )
    unplaced = []
    for uid in accepted.rewire:
        consumer = here.get(uid)
        if consumer is None or consumer.slug in skip:
            continue
        path = session.acceptance.cell_path(consumer.slug)
        if not path.exists():
            unplaced.append(uid)
            continue
        source = path.read_bytes().decode("utf-8")
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
    """Cells the branch selects that the files no longer hold.

    Absence is decided by identity, not by filename: acceptance has just read
    every file, so a selected cell no file turned out to hold is the deleted
    one. Looking for a file named after the slug instead would be wrong exactly
    where the two come apart — a slug the store had to move aside is carried by
    a file under the name that collided, and asking for it by slug would report
    the cell deleted, re-accept it, and do it again on the next quiesce.

    Only for a bound worktree: a complete projection of the slice is the one
    thing that makes an absent file mean "deleted" rather than "never written".
    An unbound flow's cells live in the store, and reading absence as intent
    there would delete the MCP path's work the moment a stray file appeared.
    """
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


def _complete_projections(session: "FlowSession", branch_id: str) -> _Pending:
    """Sort out the files a store-side edit got ahead of.

    A file that diverged from the head but holds bytes some *known* version of
    that same cell was accepted under is not an edit — it is the projection of
    a store-side edit that has not landed yet, and accepting it would write the
    old version back over the new one. So the store wins and the file catches
    up, except while an agent session holds the worktree: then the file is
    neither rewritten nor accepted, and the deferral simply stands. Both
    readings come off the files alone, which is what a daemon restarted
    mid-deferral has to work from.

    Only a version *older* than the head can be one of these: a projection is
    the store having got ahead of the files, so the bytes left behind are the
    bytes from before. Newer ones are edits that happen to restate something
    the store has seen — re-applying an edit a rewind took back, or carrying a
    fork's version over by hand — and completing those would quietly undo the
    author's work and accept nothing in its place.

    A file an author reverted by hand to an older version reads the same way,
    and is completed too: content cannot tell the two apart, and of the two
    readings only this one can lose nothing — every version is still in the
    store, and the revert is one edit away from being made again.
    """
    store = session.store
    worktree = session.worktree
    locked = worktree.holder() is not None
    here = store.index.slice_versions(branch_id)
    pending = _Pending()
    for uid, version in sorted(here.items(), key=lambda item: item[1].slug):
        path = session.acceptance.cell_path(version.slug)
        if not path.exists():
            continue
        source = store.objects.get(version.raw_source_ref)
        held = path.read_bytes()
        if held == source:
            worktree.deferred.pop(uid, None)
            continue
        older = store.index.version_by_source(uid, hash_bytes(held))
        if older is None or older.created_step >= version.created_step:
            continue
        if locked:
            worktree.deferred.setdefault(uid, older.version_id)
            pending.withheld[version.slug] = uid
            continue
        atomic_write_bytes(path, source)
        worktree.deferred.pop(uid, None)
        pending.completed.append(version.slug)
    return pending


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
