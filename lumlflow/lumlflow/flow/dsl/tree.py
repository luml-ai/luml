"""The workspace tree hash — the shared code every flow computes against.

Watched `.py` files outside any flow's `cells/` are shared code: workspace
helpers, and the occasional stray module inside a flow directory. The store
never versions them; it records one hash over all of them, and a change to it
is what marks every cell with a cause naming the file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from pathspec import GitIgnoreSpec

from lumlflow.flow.hashing import hash_file, hash_json
from lumlflow.flow.store.flowstore import (
    CELLS_DIRNAME,
    FLOW_SUFFIX,
    STORE_DIRNAME,
)

EXCLUDED_DIRS = frozenset(
    {
        ".venv",
        ".git",
        ".tox",
        "__pycache__",
        "build",
        "dist",
        "env",
        "node_modules",
        "site-packages",
        "venv",
        STORE_DIRNAME,
    }
)
_EDITOR_FILE_PREFIXES = (".#", "._")
_VENV_MARKER = "pyvenv.cfg"


class WorkspaceExclusions:
    """Named, virtual-environment and gitignored paths under one scan root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._gitignores: dict[Path, GitIgnoreSpec | None] = {}

    def matches(self, path: Path, *, directory: bool = False) -> bool:
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(self.root)
        except (OSError, ValueError):
            return True
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            return True
        parents = self._parents(relative, include_target=False)
        marker_dirs = self._parents(relative, include_target=directory)
        if any((candidate / _VENV_MARKER).is_file() for candidate in marker_dirs):
            return True
        ignored = False
        suffix = "/" if directory else ""
        for base in parents:
            spec = self._gitignore(base)
            if spec is None:
                continue
            candidate = resolved.relative_to(base).as_posix() + suffix
            decision = spec.check_file(candidate).include
            if decision is not None:
                ignored = decision
        return ignored

    def _parents(self, relative: Path, *, include_target: bool) -> list[Path]:
        count = len(relative.parts) if include_target else len(relative.parts) - 1
        return [
            self.root.joinpath(*relative.parts[:depth]) for depth in range(count + 1)
        ]

    def _gitignore(self, directory: Path) -> GitIgnoreSpec | None:
        if directory in self._gitignores:
            return self._gitignores[directory]
        try:
            lines = (directory / ".gitignore").read_text("utf-8").splitlines()
        except (OSError, UnicodeError):
            spec = None
        else:
            spec = GitIgnoreSpec.from_lines(lines)
        self._gitignores[directory] = spec
        return spec


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
    exclusions = WorkspaceExclusions(root)
    files: dict[str, str] = {}
    strays: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not exclusions.matches(here / name, directory=True)
        )
        flow = _flow_root(here, root)
        if flow == here:
            dirnames[:] = [name for name in dirnames if name != CELLS_DIRNAME]
        for name in sorted(filenames):
            if not name.endswith(".py") or name.startswith(_EDITOR_FILE_PREFIXES):
                continue
            path = here / name
            if exclusions.matches(path):
                continue
            relative = path.relative_to(root).as_posix()
            try:
                files[relative] = hash_file(path)
            except OSError:
                continue
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
