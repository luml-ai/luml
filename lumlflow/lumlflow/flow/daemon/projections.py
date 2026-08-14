"""The worktree: the flow directory as a projection of one branch's slice.

v1 has exactly one worktree per flow — the flow root itself — so checking a
branch out is a binding plus a file write, and *viewing* a branch is neither.
That split is the point: reading another branch's cards is a store read that
takes no lock and starts no kernel, while checking it out rewrites `cells/`
and therefore has to ask whether anyone is working in there.

The lock is a policy, not a mutex. All of this runs on the daemon's one loop
thread — the watcher only posts observations to it — so ordering is already
settled; what the lock decides is *whose* files these are: an op by the agent
that holds the worktree proceeds, anyone else's waits for the session to end
or forces past it.
"""

from dataclasses import dataclass, field
from pathlib import Path

from lumlflow.flow.atomic import atomic_write_bytes, unlink_retry
from lumlflow.flow.dsl.accept import CELL_SUFFIX
from lumlflow.flow.errors import WorktreeLocked
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, FlowStore
from lumlflow.flow.store.index import AgentSessionRow, BranchRow

_CELL_GLOB = f"*{CELL_SUFFIX}"


@dataclass(frozen=True)
class Projection:
    """What a checkout did to the files. `deferred` is what it could not do."""

    branch: str
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


class Worktree:
    def __init__(self, store: FlowStore) -> None:
        self._store = store
        # Cells the store is ahead of because the files could not be written,
        # each mapped to the version the files still hold: the card's "saved ·
        # not yet written to files", and the parent an agent editing the stale
        # file would be editing from. Reconciliation completes a deferral from
        # the store alone, so losing this on a restart costs the label and the
        # parent, never the edit.
        self.deferred: dict[str, str | None] = {}

    @property
    def path(self) -> Path:
        return self._store.flow_dir

    @property
    def cells_dir(self) -> Path:
        return self.path / CELLS_DIRNAME

    def bound(self) -> BranchRow | None:
        return self._store.branches.bound_branch()

    @property
    def branch(self) -> str:
        bound = self.bound()
        return bound.name if bound is not None else MAIN_BRANCH

    def holder(self) -> AgentSessionRow | None:
        return self._store.index.worktree_holder()

    def projects_files(self) -> bool:
        """Is there a file plane to reconcile at all?

        A bound flow always has one. An unbound flow that holds cell files is
        one nobody has checked out yet — an agent's `lumlflow init` skipped, a
        directory copied in — and its files are still the truth. An unbound
        flow with no cell files is the MCP case: cells live in the store, and
        there is nothing on disk to read or to overwrite.
        """
        if self.bound() is not None:
            return True
        return any(self.cells_dir.glob(_CELL_GLOB))

    def guard(self, *, actor: str, force: bool = False) -> None:
        """Refuse to rewrite files a working agent session owns."""
        holder = self.holder()
        if holder is None or force or holder.actor == actor:
            return
        raise WorktreeLocked(
            f"{holder.label} holds these files. wait for the session to end, "
            "or force this through",
            holder=holder.label,
            branch=self.branch,
        )

    def checkout(
        self,
        name: str | None = None,
        *,
        actor: str = "user",
        intent: str | None = None,
        force: bool = False,
    ) -> Projection:
        """Bind the worktree to a branch and project its slice into `cells/`.

        Never a bare bind: a flow whose root points at `main` while the files
        hold something else is a worktree that lies. Binding and projecting are
        one op, and both wait on the lock together.
        """
        branch = self._store.branches.get(name or self.branch)
        self.guard(actor=actor, force=force)
        bound = self.bound()
        if bound is None or bound.branch_id != branch.branch_id:
            self._store.branches.switch(branch.name, actor=actor, intent=intent)
        return self.project(branch.name, actor=actor, force=force)

    def project(
        self, name: str | None = None, *, actor: str = "user", force: bool = False
    ) -> Projection:
        """Write the branch's slice into `cells/`: differing files, no others.

        Workspace files are never touched — they are branch-invariant, and the
        flow directory is only a projection of the cells.
        """
        branch = self._store.branches.get(name or self.branch)
        here = self._store.index.slice_versions(branch.branch_id)
        self.guard(actor=actor, force=force)
        self.cells_dir.mkdir(parents=True, exist_ok=True)
        written, keep = [], set()
        for uid, version in sorted(here.items(), key=lambda item: item[1].slug):
            path = self.cells_dir / f"{version.slug}{CELL_SUFFIX}"
            keep.add(path.name.lower())
            source = self._store.objects.get(version.raw_source_ref)
            if not path.exists() or path.read_bytes() != source:
                atomic_write_bytes(path, source)
                written.append(version.slug)
            self.deferred.pop(uid, None)
        removed = []
        for path in sorted(self.cells_dir.glob(_CELL_GLOB)):
            # Case-insensitively: slugs are lowercase, so a file the author
            # called `Features.py` *is* the cell `features` on the filesystems
            # that cannot tell them apart, and deleting it would delete the
            # cell this projection had just decided to keep.
            if path.name.lower() not in keep:
                unlink_retry(path)
                removed.append(path.stem)
        return Projection(branch=branch.name, written=written, removed=removed)

    def project_cell(
        self,
        uid: str,
        *,
        branch: str,
        held: str | None = None,
        actor: str = "user",
    ) -> bool:
        """Carry one daemon-originated edit into the files, or record it owed.

        The whole slice is projected rather than the one file: a rename leaves
        a file behind under the old name, and writing the slice is the only
        spelling of "the files say what the branch says". It is idempotent, so
        the extra cells cost a read each.

        `held` is the version the files still hold — remembered from the first
        deferral, never overwritten by a later one, because two deferred edits
        in a row leave the files where the first one found them.

        Only a checked-out branch held by *somebody else* leaves an edit owed.
        A flow nobody checked out has no files to be behind, and a branch that
        is not the checked-out one is projected in full the moment it is. The
        holder's own edit is written: the lock exists so nothing is rewritten
        under the agent working in these files, and an edit that agent asked
        for through a tool is not something happening under it.
        """
        bound = self.bound()
        if bound is None or bound.name != branch:
            return False
        holder = self.holder()
        if holder is not None and holder.actor != actor:
            self.deferred.setdefault(uid, held)
            return False
        self.project(branch, actor=actor)
        return True

    def pending(self) -> list[str]:
        """Cells saved in the store that the files do not hold yet."""
        here = self._store.index.slice_versions(
            self._store.branches.get(self.branch).branch_id
        )
        return sorted(here[uid].slug for uid in self.deferred if uid in here)
