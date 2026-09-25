"""The flow directory as a projection of one branch's slice.

Checking a branch out is a binding plus a file write, and viewing another
branch is neither. All projection work runs on the daemon's one loop thread,
so a store change can write the checked-out slice immediately.
"""

from dataclasses import dataclass, field
from pathlib import Path

from lumlflow.flow.atomic import atomic_write_bytes, unlink_retry
from lumlflow.flow.dsl.accept import (
    CELL_SUFFIX,
    assert_cell_path,
    cell_paths,
    cell_source_matches,
)
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, FlowStore
from lumlflow.flow.store.index import BranchRow


@dataclass(frozen=True)
class Projection:
    """What a checkout did to the files."""

    branch: str
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


class Worktree:
    def __init__(self, store: FlowStore) -> None:
        self._store = store

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
        return bool(cell_paths(self.cells_dir))

    def checkout(
        self,
        name: str | None = None,
        *,
        actor: str = "user",
        intent: str | None = None,
    ) -> Projection:
        """Bind the worktree to a branch and project its slice into `cells/`.

        Never a bare bind: a flow whose root points at `main` while the files
        hold something else is a worktree that lies.
        """
        branch = self._store.branches.get(name or self.branch)
        bound = self.bound()
        if bound is None or bound.branch_id != branch.branch_id:
            self._store.branches.switch(branch.name, actor=actor, intent=intent)
        return self.project(branch.name)

    def project(self, name: str | None = None) -> Projection:
        """Write the branch's slice into `cells/`: differing files, no others.

        Workspace files are never touched — they are branch-invariant, and the
        flow directory is only a projection of the cells.
        """
        branch = self._store.branches.get(name or self.branch)
        here = self._store.index.slice_versions(branch.branch_id)
        self.cells_dir.mkdir(parents=True, exist_ok=True)
        written, keep = [], set()
        for _uid, version in sorted(here.items(), key=lambda item: item[1].slug):
            path = self.cells_dir / f"{version.slug}{CELL_SUFFIX}"
            if path.is_symlink() and not path.exists():
                continue
            assert_cell_path(path, self.cells_dir)
            keep.add(path.name.casefold())
            source = self._store.objects.get(version.raw_source_ref)
            if path.exists():
                try:
                    held = path.read_bytes()
                except OSError:
                    continue
                if cell_source_matches(held, source, version.flags):
                    continue
            atomic_write_bytes(path, source)
            written.append(version.slug)
        removed = []
        for path in cell_paths(self.cells_dir):
            if path.is_symlink() and not path.exists():
                continue
            assert_cell_path(path, self.cells_dir)
            # Case-insensitively: slugs are lowercase, so a file the author
            # called `Features.py` *is* the cell `features` on the filesystems
            # that cannot tell them apart, and deleting it would delete the
            # cell this projection had just decided to keep.
            if path.name.casefold() not in keep:
                try:
                    path.read_bytes()
                except OSError:
                    continue
                unlink_retry(path)
                removed.append(path.stem)
        return Projection(branch=branch.name, written=written, removed=removed)

    def project_cell(
        self,
        *,
        branch: str,
    ) -> bool:
        """Carry one daemon-originated edit into the checked-out files.

        The whole slice is projected rather than the one file: a rename leaves
        a file behind under the old name, and writing the slice is the only
        spelling of "the files say what the branch says". It is idempotent, so
        the extra cells cost a read each.
        """
        bound = self.bound()
        if bound is None or bound.name != branch:
            return False
        self.project(branch)
        return True
