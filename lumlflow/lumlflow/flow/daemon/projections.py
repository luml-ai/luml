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
        branch = self._store.branches.get(name or self.branch)
        bound = self.bound()
        if bound is None or bound.branch_id != branch.branch_id:
            self._store.branches.switch(branch.name, actor=actor, intent=intent)
        return self.project(branch.name)

    def project(self, name: str | None = None) -> Projection:
        branch = self._store.branches.get(name or self.branch)
        here = self._store.index.slice_versions(branch.branch_id)
        self.cells_dir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        keep: dict[str, Path] = {}
        for _uid, version in sorted(here.items(), key=lambda item: item[1].slug):
            path = self.cells_dir / f"{version.slug}{CELL_SUFFIX}"
            if path.is_symlink() and not path.exists():
                continue
            assert_cell_path(path, self.cells_dir)
            keep[path.name.casefold()] = path
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
            if not _kept(path, keep):
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


def _kept(path: Path, keep: dict[str, Path]) -> bool:
    projected = keep.get(path.name.casefold())
    if projected is None:
        return False
    # On a case-insensitive filesystem `Features.py` *is* the projected
    # `features.py`, and deleting it would delete the kept cell; on a
    # case-sensitive one it is a separate file shadowing the cell.
    try:
        return path.name == projected.name or path.samefile(projected)
    except OSError:
        return False
