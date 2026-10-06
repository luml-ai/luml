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
from lumlflow.flow.store.index import (
    BranchRow,
    Index,
    MaterializationRow,
    TransactionRow,
    VersionRow,
)
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
    slugs: dict[str, str]
    baselines: dict[str, str]


@dataclass(frozen=True)
class AdoptResult:
    slug: str
    uid: str
    version_id: str
    reaccept: list[str] = field(default_factory=list)
    rewire: list[str] = field(default_factory=list)
    namespace_conflicts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeleteResult:
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
        record = self.get(branch)
        return _resolve(self._index.slice_versions(record.branch_id), slug, branch)

    def selected_versions(self, branch_id: str, uid: str) -> set[str]:
        return self._selection_history(uid).get(branch_id, set())

    def bound_branch(self) -> BranchRow | None:
        branch_id = self._index.worktree_branch(self._store.manifest.flow_id)
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
            parent_step=self._index.head_step(parent.branch_id),
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
        branch = self.get(name)
        self._store.commit(
            [
                WorktreeBound(
                    flow_id=self._store.manifest.flow_id,
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

    def checkpoint(
        self,
        name: str,
        *,
        step: int | None = None,
        actor: str = "user",
        intent: str,
    ) -> TransactionRow:
        if not intent.strip():
            raise ValueError("a checkpoint needs a one-line intent")
        branch = self.get(name)
        index = self._store.index
        if step is None:
            standing = index.head(branch.branch_id)
            if standing is None:
                raise ValueError(f"nothing on {name} to mark yet")
            step = standing.step
        else:
            found = index.transaction(step)
            if found is None or found.branch != branch.branch_id:
                raise ValueError(f"step {step} is not on {name}")
        self._store.commit(
            [Checkpointed(branch_id=branch.branch_id, step=step)],
            intent=intent.strip(),
            actor=actor,
            branch=branch.branch_id,
        )
        marked = index.transaction(step)
        assert marked is not None
        return marked

    def rewind(
        self,
        name: str,
        *,
        to_step: int,
        actor: str = "user",
        intent: str | None = None,
    ) -> RewindResult:
        branch = self.get(name)
        if not 1 <= to_step < self._store.next_step:
            raise RewindTargetNotFound(f"no transaction at step {to_step}")
        with self._state_at(to_step) as state:
            if state.branch_by_id(branch.branch_id) is None:
                raise RewindTargetNotFound(f"{name} did not exist at step {to_step}")
            selections = state.selections(branch.branch_id)
            slugs = {
                uid: version.slug
                for uid, version in state.slice_versions(branch.branch_id).items()
            }
            baselines = state.baselines(branch.branch_id)
        self._store.commit(
            [
                Rewound(
                    branch_id=branch.branch_id,
                    to_step=to_step,
                    selections=selections,
                    slugs=slugs,
                    baselines=baselines,
                )
            ],
            intent=intent or f"rewound {name} to step {to_step}",
            actor=actor,
            branch=branch.branch_id,
        )
        return RewindResult(
            branch=name,
            to_step=to_step,
            selections=selections,
            slugs=slugs,
            baselines=baselines,
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
        rewire = _renamed_by_adopt(here, uid, incoming.slug, current)
        reaccept: list[str] = []
        if rebinding or taken:
            reaccept = [uid]
        return AdoptResult(
            slug=incoming.slug,
            uid=uid,
            version_id=incoming.version_id,
            reaccept=reaccept,
            rewire=rewire,
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
        if current is None or current.definition_hash == incoming.definition_hash:
            return False
        base = self._shared_definition_hash(source, target, uid)
        if base is None:
            # Two different answers and no common ancestor to attribute either
            return True
        return current.definition_hash != base and incoming.definition_hash != base

    def _shared_definition_hash(
        self, source: BranchRow, target: BranchRow, uid: str
    ) -> str | None:
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
    for ref in mat.inputs.values():
        producer = slice_mats.get(ref.uid)
        if producer is None:
            return False
        output = producer.outputs.get(ref.output)
        if output is None or output.content_hash != ref.content_hash:
            return False
    return True


def _selecting_branches(entry: Transaction) -> set[str]:
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
    if current is None or current.slug == incoming_slug:
        return []
    return sorted(
        other
        for other, version in here.items()
        if other != uid
        and any(consumed.uid == uid for consumed in version.manifest.consumes.values())
    )


def _binding_changes(
    incoming: VersionRow, names: dict[str, str]
) -> tuple[list[str], list[str]]:
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
