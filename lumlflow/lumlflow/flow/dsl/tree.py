"""The workspace tree hash — the shared code every flow computes against.

Watched `.py` files outside any flow's `cells/` are shared code: workspace
helpers, and the occasional stray module inside a flow directory. The store
never versions them; it records one hash over all of them, and a change to it
is what marks every cell with a cause naming the file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from lumlflow.flow.hashing import hash_file, hash_json
from lumlflow.flow.store.flowstore import (
    CELLS_DIRNAME,
    FLOW_SUFFIX,
    STORE_DIRNAME,
)

EXCLUDED_DIRS = frozenset(
    {".venv", ".git", "node_modules", "__pycache__", STORE_DIRNAME}
)


@dataclass(frozen=True)
class WorkspaceTree:
    """`strays` names shared code that sits inside a flow — a hygiene note."""

    tree_hash: str
    files: dict[str, str] = field(default_factory=dict)
    strays: list[str] = field(default_factory=list)

    def changed_paths(self, other: "WorkspaceTree") -> list[str]:
        return sorted(
            path
            for path in self.files.keys() | other.files.keys()
            if self.files.get(path) != other.files.get(path)
        )


def scan_workspace(workspace_dir: Path) -> WorkspaceTree:
    root = workspace_dir.resolve()
    files: dict[str, str] = {}
    strays: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        flow = _flow_root(here, root)
        if flow == here:
            dirnames[:] = [name for name in dirnames if name != CELLS_DIRNAME]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            relative = (here / name).relative_to(root).as_posix()
            files[relative] = hash_file(here / name)
            if flow is not None:
                strays.append(relative)
    return WorkspaceTree(tree_hash=tree_hash(files), files=files, strays=strays)


def tree_hash(files: dict[str, str]) -> str:
    return hash_json(sorted(files.items()))


def stray_note(relative_path: str) -> str:
    return (
        f"`{relative_path}` sits inside the flow but is not a cell. a flow is "
        "one directory of cells. shared code belongs to the workspace"
    )


def _flow_root(directory: Path, root: Path) -> Path | None:
    """The `.flow` directory this one lives in, if any."""
    for parent in (directory, *directory.parents):
        if parent == root:
            return None
        if parent.name.endswith(FLOW_SUFFIX):
            return parent
    return None
