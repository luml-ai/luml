"""The kind registry: one plugin contract for serde, hashing, preview, paging.

`AssetType` is structural, like the cell DSL — a kind is any object carrying
these members, so a workspace can define one without importing us. Registration
comes from three places, and where a kind came from is a recorded fact the
handshake reports, because the daemon stores kind inference as provenance.

Resolution per output is fixed: an explicit dict override wins, then matchers
in registry priority, then the pickle fallback. Priority is a number, low
first; plugins default ahead of the builtins so a workspace can claim its own
types back from a general matcher.
"""

from __future__ import annotations

import ast
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lumlflow_kernel.kinds.preview import Block

ENTRY_POINT_GROUP = "lumlflow.kinds"
PLUGIN_DECLARATION = "LUMLFLOW_KINDS"
PLUGIN_PRIORITY = 10

DECLARED = "declared"
MATCHER = "matcher"
FALLBACK = "fallback"


class KindError(Exception):
    """A kind was named that no registry entry answers to."""


class AssetType(Protocol):
    """What a kind is. `content_hash` and `page` are optional; a plugin that
    omits `priority` or `python_types` is registered ahead of the builtins and
    reported as claiming nothing in particular."""

    kind: str
    priority: int
    python_types: tuple[str, ...]

    def matches(self, value: Any) -> bool: ...

    def serialize(self, value: Any) -> bytes | Path: ...

    def deserialize(self, source: Path) -> Any: ...

    def preview(self, value: Any) -> list[Block]: ...


@dataclass(frozen=True)
class Resolution:
    asset_type: AssetType
    source: str

    @property
    def kind(self) -> str:
        return self.asset_type.kind


@dataclass(frozen=True)
class _Entry:
    asset_type: AssetType
    provenance: str
    fallback: bool


class Registry:
    def __init__(self) -> None:
        self._entries: list[_Entry] = []

    def register(
        self, asset_type: AssetType, *, provenance: str, fallback: bool = False
    ) -> None:
        self._entries = [
            entry for entry in self._entries if entry.asset_type.kind != asset_type.kind
        ]
        self._entries.append(_Entry(asset_type, provenance, fallback))
        self._entries.sort(key=lambda entry: _priority(entry.asset_type))

    def report(self) -> list[dict[str, Any]]:
        """What the handshake tells the daemon about this flow's kinds."""
        return [
            {
                "kind": entry.asset_type.kind,
                "priority": _priority(entry.asset_type),
                "provenance": entry.provenance,
                "python_types": list(getattr(entry.asset_type, "python_types", ())),
            }
            for entry in self._entries
        ]

    def get(self, kind: str) -> AssetType:
        for entry in self._entries:
            if entry.asset_type.kind == kind:
                return entry.asset_type
        known = ", ".join(sorted(entry.asset_type.kind for entry in self._entries))
        raise KindError(f"no kind named `{kind}` — this flow knows {known}")

    def resolve(self, value: Any, declared: str | None = None) -> Resolution:
        if declared is not None:
            return Resolution(self.get(declared), DECLARED)
        for entry in self._entries:
            if entry.asset_type.matches(value):
                return Resolution(
                    entry.asset_type, FALLBACK if entry.fallback else MATCHER
                )
        raise KindError("nothing in this flow's registry can store that value")


def build(workspace_dir: Path | None = None) -> Registry:
    """Builtins, then installed plugins, then the workspace's own kinds."""
    from lumlflow_kernel.kinds import builtin

    registry = Registry()
    for asset_type in builtin.asset_types():
        registry.register(
            asset_type,
            provenance="builtin",
            fallback=asset_type.kind == builtin.PICKLE,
        )
    for asset_type, provenance in _installed():
        registry.register(asset_type, provenance=provenance)
    if workspace_dir is not None:
        for asset_type, provenance in _from_workspace(workspace_dir):
            registry.register(asset_type, provenance=provenance)
    return registry


def _installed() -> list[tuple[AssetType, str]]:
    from importlib.metadata import entry_points

    found: list[tuple[AssetType, str]] = []
    for point in entry_points(group=ENTRY_POINT_GROUP):
        try:
            loaded = point.load()
        except Exception:
            # A broken plugin is not a reason to refuse to run cells; its
            # absence shows up in the handshake's registry report.
            continue
        found.extend(
            (asset_type, f"entry point `{point.name}`")
            for asset_type in _instances(loaded)
        )
    return found


def _from_workspace(workspace_dir: Path) -> list[tuple[AssetType, str]]:
    """Import only the workspace modules that say they define kinds.

    Found by parse, not by importing everything and looking: the workspace is
    the user's own code, and a kind scan is no reason to run all of it.
    """
    root = str(workspace_dir)
    if root not in sys.path:
        sys.path.insert(0, root)
    found: list[tuple[AssetType, str]] = []
    for path in sorted(workspace_dir.glob("*.py")):
        if not _declares_kinds(path):
            continue
        try:
            module = importlib.import_module(path.stem)
        except Exception:
            continue
        declared = getattr(module, PLUGIN_DECLARATION, ())
        found.extend(
            (asset_type, f"`{path.name}`") for asset_type in _instances(declared)
        )
    return found


def _declares_kinds(path: Path) -> bool:
    try:
        module = ast.parse(path.read_bytes())
    except (SyntaxError, ValueError, OSError):
        return False
    return any(
        isinstance(target, ast.Name) and target.id == PLUGIN_DECLARATION
        for statement in module.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
    )


def _instances(declared: Any) -> list[AssetType]:
    """Accept a kind, a class, or a sequence of either."""
    if isinstance(declared, (list, tuple, set)):
        return [item for entry in declared for item in _instances(entry)]
    if isinstance(declared, type):
        try:
            declared = declared()
        except Exception:
            return []
    kind = getattr(declared, "kind", None)
    if not isinstance(kind, str) or not hasattr(declared, "serialize"):
        return []
    return [declared]


def _priority(asset_type: AssetType) -> int:
    priority = getattr(asset_type, "priority", PLUGIN_PRIORITY)
    return priority if isinstance(priority, int) else PLUGIN_PRIORITY
