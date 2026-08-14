"""Branch operations: fork, switch, archive, rewind, adopt, per-branch delete.

A branch is a selection map (uid → version_id) plus baseline pointers, so every
operation here is a row edit — no file is copied and no value is ever
duplicated. Two consequences worth stating: forking is O(one journaled op)
because the dense copy of the parent's rows happens in the index fold, and
rewind is instant because it restores pointers into a CAS that keeps
everything.

Operations address cells by slug, the name the branch's namespace knows them
by; uids stay inside.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import takewhile
from typing import TYPE_CHECKING

from lumlflow.flow.errors import (
    AdoptConflict,
    BranchAlreadyExists,
    BranchNotFound,
    CellNotFound,
    RewindTargetNotFound,
)
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.store.index import BranchRow, Index, MaterializationRow, VersionRow
from lumlflow.flow.store.models import (
    Adopted,
    BranchArchived,
    BranchCreated,
    CellRemoved,
    Checkpointed,
    Rewound,
    SelectionSet,
    Transaction,
    WorktreeBound,
)

if TYPE_CHECKING:
    from lumlflow.flow.store.flowstore import FlowStore

MAIN_BRANCH = "main"


@dataclass(frozen=True)
class RewindResult:
    branch: str
    to_step: int
    selections: dict[str, str]
    baselines: dict[str, str]


@dataclass(frozen=True)
class AdoptResult:
    """`reaccept` names the target's consumers whose bindings the adopt moved."""

    slug: str
    uid: str
    version_id: str
    reaccept: list[str] = field(default_factory=list)
    namespace_conflicts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeleteResult:
    """`dangling` names the consumers left pointing at nothing on this branch."""

    slug: str
    uid: str
    branch: str
    dangling: list[str] = field(default_factory=list)


class Branches:
    def __init__(self, store: "FlowStore") -> None:
        self._store = store

    @property
    def _index(self) -> Index:
        # Never cached: a lost index update rebuilds the object underneath us.
        return self._store.index

    def get(self, name: str) -> BranchRow:
        branch = self._index.branch(name)
        if branch is None:
            raise BranchNotFound(f"no lane named {name}")
        return branch

    def resolve(self, branch: str, slug: str) -> str:
        """The uid behind a name in the branch's namespace."""
        record = self.get(branch)
        return _resolve(self._index.slice_versions(record.branch_id), slug, branch)

    def bound_branch(self) -> BranchRow | None:
        """The branch the worktree projects, or None while nothing is bound."""
        branch_id = self._index.worktree_branch(str(self._store.flow_dir))
        return self._index.branch_by_id(branch_id) if branch_id else None

    def fork(
        self,
        name: str,
        *,
        from_branch: str,
        actor: str = "user",
        intent: str | None = None,
    ) -> BranchRow:
        if not name.strip():
            raise ValueError("a lane needs a name")
        parent = self.get(from_branch)
        if self._index.branch(name) is not None:
            raise BranchAlreadyExists(f"a lane named {name} already exists")
        created = BranchCreated(
            branch_id=new_ulid(),
            name=name,
            parent_branch_id=parent.branch_id,
            fork_step=self._store.next_step,
        )
        self._store.commit(
            [created],
            intent=intent or f"started {name} from {from_branch}",
            actor=actor,
            branch=created.branch_id,
        )
        return self.get(name)

    def switch(
        self, name: str, *, actor: str = "user", intent: str | None = None
    ) -> BranchRow:
        """Rebind the worktree — the flow root, the single v1 worktree.

        Projecting the slice into `cells/` is the daemon's half of the
        checkout; the store only records the binding.
        """
        branch = self.get(name)
        self._store.commit(
            [
                WorktreeBound(
                    path=str(self._store.flow_dir),
                    branch_id=branch.branch_id,
                    actor=actor,
                )
            ],
            intent=intent or f"put {name} on disk",
            actor=actor,
            branch=branch.branch_id,
        )
        return branch

    def archive(
        self, name: str, *, actor: str = "user", intent: str | None = None
    ) -> BranchRow:
        branch = self.get(name)
        if branch.archived:
            return branch
        self._store.commit(
            [BranchArchived(branch_id=branch.branch_id)],
            intent=intent or f"archived {name}",
            actor=actor,
            branch=branch.branch_id,
        )
        return self.get(name)

    def checkpoint(self, name: str, *, actor: str = "user", intent: str) -> Transaction:
        """Mark this point on a branch under a one-line intent.

        The deliberate counterpart of the `settled` badge, and deliberately not
        a snapshot: every version the branch selects here is already kept, so
        the only thing a checkpoint adds is a name for the step — which is the
        transaction's own intent, the field every journal line already carries.
        """
        if not intent.strip():
            raise ValueError("a checkpoint needs a one-line intent")
        branch = self.get(name)
        return self._store.commit(
            [Checkpointed(branch_id=branch.branch_id)],
            intent=intent.strip(),
            actor=actor,
            branch=branch.branch_id,
        )

    def rewind(
        self,
        name: str,
        *,
        to_step: int,
        actor: str = "user",
        intent: str | None = None,
    ) -> RewindResult:
        """Restore selections *and* baselines to their as-of-step values.

        No gate and no preflight: every value the restored state points at is
        still in the CAS, so there is nothing to warn about and nothing to
        recompute. Baselines travel with the selections, so a rewound branch
        keeps its staleness verdicts instead of lighting up wholesale.
        """
        branch = self.get(name)
        if not 1 <= to_step < self._store.next_step:
            raise RewindTargetNotFound(f"no transaction at step {to_step}")
        with self._state_at(to_step) as state:
            if state.branch_by_id(branch.branch_id) is None:
                raise RewindTargetNotFound(f"{name} did not exist at step {to_step}")
            selections = state.selections(branch.branch_id)
            baselines = state.baselines(branch.branch_id)
        self._store.commit(
            [
                Rewound(
                    branch_id=branch.branch_id,
                    to_step=to_step,
                    selections=selections,
                    baselines=baselines,
                )
            ],
            intent=intent or f"rewound {name} to step {to_step}",
            actor=actor,
            branch=branch.branch_id,
        )
        return RewindResult(
            branch=name, to_step=to_step, selections=selections, baselines=baselines
        )

    def adopt(
        self,
        slug: str,
        *,
        from_branch: str,
        to_branch: str,
        force: bool = False,
        actor: str = "user",
        intent: str | None = None,
    ) -> AdoptResult:
        """Cherry-pick one asset onto another branch — the whole v1 merge story.

        Raises `AdoptConflict` when there is a side to pick: both branches
        edited the cell since they forked, or the incoming bindings name a
        different cell here. `force` is the resolution — pick the incoming one.
        """
        if from_branch == to_branch:
            raise ValueError("adopt moves an asset between two different lanes")
        source, target = self.get(from_branch), self.get(to_branch)
        there = self._index.slice_versions(source.branch_id)
        here = self._index.slice_versions(target.branch_id)
        uid = _resolve(there, slug, from_branch)
        incoming, current = there[uid], here.get(uid)

        names = _names(here)
        clashing, rebinding = _binding_changes(incoming, names)
        taken = _slug_clash(incoming, uid, names)
        conflicts = clashing + taken
        divergent = self._both_edited(source, target, uid, incoming, current)
        if not force and (divergent or conflicts):
            raise AdoptConflict(
                _conflict_message(slug, from_branch, to_branch, divergent, conflicts),
                slug=slug,
                from_branch=from_branch,
                to_branch=to_branch,
                definition=divergent,
                namespace=tuple(conflicts),
            )

        self._store.commit(
            [
                Adopted(
                    branch_id=target.branch_id,
                    uid=uid,
                    version_id=incoming.version_id,
                    from_branch_id=source.branch_id,
                )
            ],
            intent=intent or f"adopted {slug} from {from_branch}",
            actor=actor,
            branch=target.branch_id,
        )
        reaccept = _renamed_by_adopt(here, uid, incoming.slug, current)
        if rebinding or taken:
            # The adopted version is itself a consumer whose references bind
            # differently here — to another cell, to none, or to one they were
            # missing — and a name forced in over an existing one still has to
            # be suffixed apart. Either way it is acceptance that re-binds and
            # renames it.
            reaccept = sorted({*reaccept, incoming.slug})
        return AdoptResult(
            slug=incoming.slug,
            uid=uid,
            version_id=incoming.version_id,
            reaccept=reaccept,
            namespace_conflicts=conflicts,
        )

    def delete(
        self,
        slug: str,
        *,
        branch: str,
        actor: str = "user",
        intent: str | None = None,
    ) -> DeleteResult:
        """Drop the selection entry. Every other branch keeps its own."""
        record = self.get(branch)
        here = self._index.slice_versions(record.branch_id)
        uid = _resolve(here, slug, branch)
        dangling = sorted(
            version.slug
            for other, version in here.items()
            if other != uid
            and any(
                consumed.uid == uid for consumed in version.manifest.consumes.values()
            )
        )
        self._store.commit(
            [CellRemoved(uid=uid, branch_id=record.branch_id)],
            intent=intent or f"deleted {slug} from {branch}",
            actor=actor,
            branch=record.branch_id,
        )
        return DeleteResult(slug=slug, uid=uid, branch=branch, dangling=dangling)

    @contextmanager
    def _state_at(self, step: int) -> Iterator[Index]:
        """The whole store as of `step`, folded into a throwaway index.

        Replaying through the same fold the live index uses is what keeps
        as-of-step answers honest — there is no second implementation of what
        an op means to a branch's state.
        """
        state = Index.in_memory()
        try:
            state.rebuild(
                takewhile(
                    lambda entry: entry.step <= step, self._store.journal.replay()
                )
            )
            yield state
        finally:
            state.close()

    def _both_edited(
        self,
        source: BranchRow,
        target: BranchRow,
        uid: str,
        incoming: VersionRow,
        current: VersionRow | None,
    ) -> bool:
        """Three-way on `definition_hash` against the last version both shared."""
        if current is None or current.definition_hash == incoming.definition_hash:
            return False
        base = self._shared_definition_hash(source, target, uid)
        if base is None:
            # Two different answers and no common ancestor to attribute either
            # to: that is both sides having edited, and taking one silently
            # would lose the other.
            return True
        return current.definition_hash != base and incoming.definition_hash != base

    def _shared_definition_hash(
        self, source: BranchRow, target: BranchRow, uid: str
    ) -> str | None:
        """The `definition_hash` of the newest version both branches have held.

        The merge base, read off selection history rather than off branch
        ancestry: a fork inherits everything its parent had held, and an adopt
        adds the donor's version, so the newest version the two histories share
        is the state they last had in common. Asking instead for a step where
        both *currently* selected it would find nothing whenever the split
        predates a change on one side — a fork of a fork, or siblings that
        split at different steps — and read a one-sided edit as two.
        """
        history = self._selection_history(uid)
        shared = history.get(source.branch_id, set()) & history.get(
            target.branch_id, set()
        )
        versions = [self._index.version(version_id) for version_id in shared]
        newest = max(
            (version for version in versions if version is not None),
            key=lambda version: version.created_step,
            default=None,
        )
        return newest.definition_hash if newest else None

    def _selection_history(self, uid: str) -> dict[str, set[str]]:
        """Every version each branch has ever selected for `uid`.

        Replayed through the same fold the live index uses, so a version counts
        as held however it arrived — accepted, forked in, adopted, or restored
        by a rewind. Only the inheritance a fork's dense copy leaves implicit
        has to be spelled out here: the child starts from everything its parent
        had held, not just from the one version it copied.
        """
        history: dict[str, set[str]] = {}
        state = Index.in_memory()
        try:
            for entry in self._store.journal.replay():
                for op in entry.ops:
                    if isinstance(op, BranchCreated) and op.parent_branch_id:
                        parent = history.get(op.parent_branch_id, set())
                        history[op.branch_id] = set(parent)
                state.apply(entry)
                for branch_id in _selecting_branches(entry):
                    selected = state.selection(branch_id, uid)
                    if selected is not None:
                        history.setdefault(branch_id, set()).add(selected)
        finally:
            state.close()
        return history


def is_settled(index: Index, branch_id: str) -> bool:
    """Is the branch's whole slice materialized from its selected versions?

    The badge that marks a natural checkpoint, computed at commit and never a
    gate. An empty branch has no checkpoint to highlight, so it reads unsettled.

    Identity is `definition_hash`, not the version id: a comment-only edit and
    a cross-branch memo hit both leave the branch whole, and both point the
    baseline at a materialization of some other version of the same cell.
    Behaviour is `definition_hash` *plus* the workspace tree, so anything that
    *started* before the last workspace-code change is stale too — modules are
    evicted before the next materialization, never under a running one.
    """
    here = index.slice_versions(branch_id)
    if not here:
        return False
    baselines = index.baselines(branch_id)
    code_changed_at = index.workspace_code_step()
    slice_mats: dict[str, MaterializationRow] = {}
    for uid, selected in here.items():
        mat_id = baselines.get(uid)
        mat = index.materialization(mat_id) if mat_id else None
        if mat is None or mat.state != "succeeded":
            return False
        if mat.started_step < code_changed_at:
            return False
        ran = index.version(mat.version_id)
        if ran is None or ran.definition_hash != selected.definition_hash:
            return False
        slice_mats[uid] = mat
    return all(_inputs_current(mat, slice_mats) for mat in slice_mats.values())


def _inputs_current(
    mat: MaterializationRow, slice_mats: dict[str, MaterializationRow]
) -> bool:
    """Did every input still hold this content when its producer last ran?"""
    for ref in mat.inputs.values():
        producer = slice_mats.get(ref.uid)
        if producer is None:
            return False
        output = producer.outputs.get(ref.output)
        if output is None or output.content_hash != ref.content_hash:
            return False
    return True


def _selecting_branches(entry: Transaction) -> set[str]:
    """The branches whose selection map this transaction could have moved."""
    return {
        op.branch_id
        for op in entry.ops
        if isinstance(op, SelectionSet | Adopted | Rewound | BranchCreated)
    }


def _resolve(here: dict[str, VersionRow], slug: str, branch: str) -> str:
    for uid, version in here.items():
        if version.slug == slug:
            return uid
    raise CellNotFound(f"no cell named {slug} on {branch}")


def _names(here: dict[str, VersionRow]) -> dict[str, str]:
    """slug → uid. First in uid order wins — the cell `_resolve` also picks, so
    a forced duplicate can never make the two disagree about a name."""
    names: dict[str, str] = {}
    for uid, version in here.items():
        names.setdefault(version.slug, uid)
    return names


def _renamed_by_adopt(
    here: dict[str, VersionRow],
    uid: str,
    incoming_slug: str,
    current: VersionRow | None,
) -> list[str]:
    """Consumers of a name the adopt moved — their bindings have to re-resolve."""
    if current is not None and current.slug == incoming_slug:
        return []
    moved = {incoming_slug} | ({current.slug} if current else set())
    return sorted(
        version.slug
        for other, version in here.items()
        if other != uid and moved & _producers(version)
    )


def _producers(version: VersionRow) -> set[str]:
    """The slugs a version's `consumes` references name."""
    return {
        consumed.ref.split(".", 1)[0]
        for consumed in version.manifest.consumes.values()
        if "." in consumed.ref
    }


def _binding_changes(
    incoming: VersionRow, names: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Incoming references that name a different cell here, and ones that would
    bind differently here at all.

    A reference resolving to a *different* cell is a conflict — adopting it
    would silently rewire the version. Anything else that moves is only work
    for acceptance: a reference to an upstream that is not here yet is an
    ordinary dangling one, and blocking on it would make adopting a pair of
    cells impossible one at a time, while one that was dangling on the donor
    and resolves here is a version arriving better off than it left.
    """
    clashing, rebinding = [], []
    for consumed in incoming.manifest.consumes.values():
        if "." not in consumed.ref:
            continue
        here_uid = names.get(consumed.ref.split(".", 1)[0])
        if here_uid == consumed.uid:
            continue
        rebinding.append(consumed.ref)
        if here_uid is not None and consumed.uid is not None:
            clashing.append(consumed.ref)
    return sorted(clashing), sorted(rebinding)


def _slug_clash(incoming: VersionRow, uid: str, names: dict[str, str]) -> list[str]:
    """Is the incoming name already another cell's here? Same-slug across
    branches is expected and harmless; it only bites when an adopt brings the
    two into one namespace, and it surfaces here as a rename to resolve."""
    taken = names.get(incoming.slug)
    return [incoming.slug] if taken is not None and taken != uid else []


def _conflict_message(
    slug: str, from_branch: str, to_branch: str, divergent: bool, conflicts: list[str]
) -> str:
    if divergent:
        return (
            f"{slug} was edited on both {to_branch} and {from_branch} since "
            "they split. pick a side"
        )
    names = ", ".join(conflicts)
    return f"{names} names a different cell on {to_branch}. pick a side"
