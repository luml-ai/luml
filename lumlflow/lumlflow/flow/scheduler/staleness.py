"""Staleness, derived from recorded facts — never stored anywhere.

Nothing in the store says "stale". A verdict comes from two things it already
holds: the branch's baseline pointer, which is the last materialization that
branch observed for a cell, and the version the branch selects now. That is
what lets a fork inherit verdicts by copying pointers and a rewind restore them
by restoring pointers — neither op has a stale flag to get wrong.

Both views the surfaces serve are this one derivation. A cell's own facts give
its state and its causes; the cells above it give `upstream`, the transitive
view. They disagree on purpose: a consumer of an edited parent is genuinely
current until that parent reruns and produces something different, so the
direct view calls it synced and the transitive view says what it sits below.
"""

from dataclasses import dataclass, replace
from typing import Literal

from lumlflow.flow.store.index import (
    Index,
    MaterializationRow,
    VersionRow,
    WorkspaceTreeRow,
)

StaleState = Literal["synced", "unsynced", "unmaterialized", "failed"]
CauseKind = Literal[
    "definition-changed",
    "deps-rewired",
    "parent-rematerialized",
    "workspace-code-changed",
]

_NAMED_FILES = 3


@dataclass(frozen=True)
class Cause:
    """`detail` is the sentence a surface renders: slugs and filenames, in words."""

    kind: CauseKind
    detail: str


@dataclass(frozen=True)
class Verdict:
    uid: str
    slug: str
    state: StaleState
    causes: tuple[Cause, ...] = ()
    upstream: tuple[str, ...] = ()

    @property
    def synced(self) -> bool:
        return self.state == "synced"

    @property
    def transitive(self) -> bool:
        """Current on its own facts, sitting below something that is not."""
        return self.state == "synced" and bool(self.upstream)


def derive(index: Index, branch_id: str, uid: str) -> Verdict | None:
    """One cell's verdict, or None when the branch does not select it."""
    return derive_all(index, branch_id).get(uid)


def derive_all(index: Index, branch_id: str) -> dict[str, Verdict]:
    derivation = _Derivation(index, branch_id)
    direct = {uid: derivation.verdict(uid) for uid in derivation.here}
    return _with_upstream(direct, derivation.here)


class _Derivation:
    """The branch's facts, read once: what it selects and what it last observed."""

    def __init__(self, index: Index, branch_id: str) -> None:
        self.index = index
        self.here = index.slice_versions(branch_id)
        self.tree = index.workspace_tree()
        baselines = index.baselines(branch_id)
        self.mats = {
            uid: mat
            for uid, mat_id in baselines.items()
            if (mat := index.materialization(mat_id)) is not None
        }

    def verdict(self, uid: str) -> Verdict:
        version = self.here[uid]
        mat = self.mats.get(uid)
        if mat is None:
            # Nothing observed: asserting a change against a baseline that does
            # not exist is a claim the runtime refuses to make.
            return Verdict(uid=uid, slug=version.slug, state="unmaterialized")
        causes = (
            *self._code_causes(version, mat),
            *self._input_causes(mat),
            *self._workspace_causes(mat),
        )
        if mat.state != "succeeded":
            return Verdict(uid, version.slug, "failed", causes)
        return Verdict(uid, version.slug, "unsynced" if causes else "synced", causes)

    def _code_causes(
        self, version: VersionRow, mat: MaterializationRow
    ) -> tuple[Cause, ...]:
        """Did the cell itself move — its wiring first, since it says more."""
        now = {
            name: (ref.uid, ref.output)
            for name, ref in version.manifest.consumes.items()
        }
        then = {name: (ref.uid, ref.output) for name, ref in mat.inputs.items()}
        if now != then:
            moved = sorted(
                name
                for name in now.keys() | then.keys()
                if now.get(name) != then.get(name)
            )
            comes = "come" if len(moved) > 1 else "comes"
            return (
                Cause(
                    "deps-rewired", f"{_names(moved)} now {comes} from a different cell"
                ),
            )
        ran = self.index.version(mat.version_id)
        if ran is None or ran.definition_hash != version.definition_hash:
            return (Cause("definition-changed", f"`{version.slug}` was edited"),)
        return ()

    def _input_causes(self, mat: MaterializationRow) -> tuple[Cause, ...]:
        """Does any input still hold the content this run consumed?

        A parent the branch has observed nothing of proves nothing either way,
        so it raises no cause here — `upstream` is where it shows up.
        """
        causes = []
        for ref in mat.inputs.values():
            producer = self.mats.get(ref.uid)
            if producer is None or producer.state != "succeeded":
                continue
            output = producer.outputs.get(ref.output)
            if output is not None and output.content_hash == ref.content_hash:
                continue
            slug = self.here[ref.uid].slug if ref.uid in self.here else ref.output
            causes.append(
                Cause("parent-rematerialized", f"parent `{slug}` rematerialized")
            )
        return tuple(dict.fromkeys(causes))

    def _workspace_causes(self, mat: MaterializationRow) -> tuple[Cause, ...]:
        """Shared code the run imported has changed since it started.

        Anything that *started* before the change counts: modules are evicted
        before the next materialization, never under a running one.
        """
        if self.tree is None or mat.started_step >= self.tree.changed_step:
            return ()
        return (Cause("workspace-code-changed", _changed_files(self.tree)),)


def _with_upstream(
    direct: dict[str, Verdict], here: dict[str, VersionRow]
) -> dict[str, Verdict]:
    """Name, for every cell, the cells above it that are not current.

    Grown to a fixed point rather than walked recursively: a `consumes` graph
    an author has tied into a cycle is a flagged version, not a reason for the
    view over it to hang.
    """
    producers = {
        uid: sorted(
            {
                ref.uid
                for ref in version.manifest.consumes.values()
                if ref.uid is not None and ref.uid in here
            }
        )
        for uid, version in here.items()
    }
    upstream = {
        uid: {direct[parent].slug for parent in parents if not direct[parent].synced}
        for uid, parents in producers.items()
    }
    changed = True
    while changed:
        changed = False
        for uid, parents in producers.items():
            merged = upstream[uid].union(*(upstream[parent] for parent in parents))
            if merged != upstream[uid]:
                upstream[uid] = merged
                changed = True
    return {
        uid: replace(verdict, upstream=tuple(sorted(upstream[uid])))
        for uid, verdict in direct.items()
    }


def _changed_files(tree: WorkspaceTreeRow) -> str:
    if not tree.changed_paths:
        return "shared code changed"
    named = tree.changed_paths[:_NAMED_FILES]
    rest = len(tree.changed_paths) - len(named)
    more = f" and {rest} more" if rest else ""
    return f"{_names(named)}{more} changed"


def _names(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)
