import inspect
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

from luml import __version__ as SDK_VERSION

from lumlflow.flow.daemon.reconcile import MIXED_EDITING
from lumlflow.flow.dsl import loader, portable
from lumlflow.flow.dsl.tree import stray_note
from lumlflow.flow.errors import CellNotFound, FlowError
from lumlflow.flow.scheduler import planner, staleness
from lumlflow.flow.scheduler.staleness import Verdict
from lumlflow.flow.store.index import (
    AgentSessionRow,
    BranchRow,
    MaterializationRow,
    TransactionRow,
    VersionRow,
)
from lumlflow.flow.store.models import OutputRecord, TrackerRef
from lumlflow.tracker import TrackerProvider

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

MIN_COMPARED = 2
MAX_COMPARED = 5
DEFAULT_DEPTH = 2

_RECENT_TRANSACTIONS = 8
LISTED_UNSYNCED = 10
_REPORTED_FAILURES = 3
_TRACEBACK_LINES = 12

EXPERIMENT_CACHE_MAX_AGE_S = 5.0
ExperimentStateName = Literal["ok", "missing", "unreachable"]

_KIND_ORDER = {
    kind: order
    for order, kind in enumerate(
        (
            "experiment",
            "eval",
            "plot",
            "frame",
            "note",
            "metric",
            "dataset",
            "model",
            "file",
            "checkpoint",
            "pickle",
        )
    )
}


@dataclass(frozen=True)
class ExperimentState:
    state: ExperimentStateName
    sentence: str = ""
    record: Any | None = None


@dataclass(frozen=True)
class _CachedExperiment:
    checked_at: float
    state: ExperimentState


class ExperimentStates:
    def __init__(
        self,
        tracker: TrackerProvider,
        *,
        max_age_s: float = EXPERIMENT_CACHE_MAX_AGE_S,
    ) -> None:
        self._tracker: TrackerProvider = tracker
        self.max_age_s: float = max_age_s
        self._cache: dict[tuple[Path, str], _CachedExperiment] = {}

    def read(self, ref: TrackerRef) -> ExperimentState:
        store = _tracker_path(ref.store)
        key = (store, ref.experiment_id)
        now = monotonic()
        cached = self._cache.get(key)
        if cached is not None and now - cached.checked_at < self.max_age_s:
            return cached.state
        state = self._read(ref, store)
        self._cache[key] = _CachedExperiment(now, state)
        return state

    def invalidate(self, experiment_id: str) -> None:
        self._cache = {
            key: cached
            for key, cached in self._cache.items()
            if key[1] != experiment_id
        }

    def clear(self) -> None:
        self._cache.clear()

    def _read(self, ref: TrackerRef, store: Path) -> ExperimentState:
        served = self._tracker.store_path.resolve()
        if store != served:
            return ExperimentState(
                "unreachable",
                f"experiment `{ref.experiment_id}` was recorded in a different "
                f"tracker store (`{store}`). stop the daemon "
                "(`lumlflow daemon stop`) and start `lumlflow ui --path "
                f"{store}` with that store, or run the cell again here.",
            )
        try:
            record = self._tracker.read_experiment(ref.experiment_id)
        except Exception as failure:
            sentence = str(failure) or type(failure).__name__
            return ExperimentState(
                "unreachable",
                f"experiment `{ref.experiment_id}` is unreachable in tracker store "
                f"`{served}`: {sentence}. lumlflow uses luml-sdk {SDK_VERSION}; "
                "upgrade lumlflow to read a store written by a newer SDK.",
            )
        if record is None:
            return ExperimentState(
                "missing",
                f"experiment `{ref.experiment_id}` was removed from tracker store "
                f"`{served}`.",
            )
        return ExperimentState("ok", record=record)


@dataclass(frozen=True)
class Slice:
    branch: BranchRow
    versions: dict[str, VersionRow]
    verdicts: dict[str, Verdict]
    mats: dict[str, MaterializationRow]
    env_lock_hash: str | None = None
    reused: frozenset[str] = frozenset()
    born: dict[str, int] = field(default_factory=dict)
    order: dict[str, Decimal] = field(default_factory=dict)
    eager: frozenset[str] = frozenset()
    reactivity: "Callable[[], dict[str, planner.AutoVerdict]]" = dict

    @cached_property
    def auto(self) -> dict[str, planner.AutoVerdict]:
        return self.reactivity()

    def uid_of(self, slug: str) -> str:
        for uid, version in self.versions.items():
            if version.slug == slug:
                return uid
        raise _missing(slug, self.branch.name)

    def by_slug(self) -> dict[str, VersionRow]:
        return {version.slug: version for version in self.versions.values()}

    def ordered(self) -> list[str]:
        return sorted(self.versions, key=lambda uid: self.versions[uid].slug)


def read(session: "FlowSession", branch: str) -> Slice:
    index = session.store.index
    record = session.store.branches.get(branch)
    baselines = index.baselines(record.branch_id)
    return Slice(
        branch=record,
        versions=index.slice_versions(record.branch_id),
        verdicts=staleness.derive_all(index, record.branch_id),
        mats={
            uid: mat
            for uid, mat_id in baselines.items()
            if (mat := index.materialization(mat_id)) is not None
        },
        env_lock_hash=index.env_lock_hash(),
        reused=frozenset(index.reused_baselines(record.branch_id)),
        born=index.creation_steps(),
        order=session.store.effective_order(),
        eager=frozenset(session.store.manifest.settings.eager),
        reactivity=lambda: session.planner.auto_verdicts(branch),
    )


def experiment_state(session: "FlowSession", ref: TrackerRef) -> ExperimentState:
    state = session.experiment_states.read(ref)
    if state.state != "unreachable":
        return state
    warning = _sdk_version_warning(session, ref)
    if warning is None or warning in state.sentence:
        return state
    return ExperimentState(
        state.state,
        f"{state.sentence} The recorded run reported: {warning}.",
        state.record,
    )


def experiment_locations(
    session: "FlowSession", experiment_id: str
) -> list[tuple[str, str]]:
    locations: set[tuple[str, str]] = set()
    served = session.tracker.store_path.resolve()
    index = session.store.index
    for branch in index.branches():
        versions = index.slice_versions(branch.branch_id)
        for uid, mat_id in index.baselines(branch.branch_id).items():
            version = versions.get(uid)
            mat = index.materialization(mat_id)
            if version is None or mat is None:
                continue
            output_matches = any(
                record.tracker_ref is not None
                and record.tracker_ref.experiment_id == experiment_id
                and _tracker_path(record.tracker_ref.store) == served
                for record in mat.outputs.values()
            )
            run_matches = (
                mat.experiment_id == experiment_id
                and mat.experiment_store is not None
                and _tracker_path(mat.experiment_store) == served
            )
            if output_matches or run_matches:
                locations.add((branch.name, version.slug))
    return sorted(locations)


def cell(here: Slice, uid: str) -> dict[str, Any]:
    version, verdict = here.versions[uid], here.verdicts[uid]
    mat = here.mats.get(uid)
    return {
        "slug": version.slug,
        "state": verdict.state,
        "causes": [cause.detail for cause in verdict.causes],
        "upstream": list(verdict.upstream),
        "transitive": verdict.transitive,
        "outputs": list(version.manifest.produces),
        "kinds": {
            name: _kind_of(name, version, mat) for name in version.manifest.produces
        },
        "primary": primary_output(version, mat),
        "consumes": {name: ref.ref for name, ref in version.manifest.consumes.items()},
        "note": version.manifest.classification == "note",
        "external": (mat is not None and mat.external)
        or version.manifest.volatility == "external",
        "flags": [{"code": flag.code, "detail": flag.detail} for flag in version.flags],
        "cost_seconds": mat.cost_seconds if mat is not None else None,
        "created_step": here.born.get(uid, 0),
        "order": format(here.order.get(uid, Decimal(here.born.get(uid, 0))), "f"),
        "changed_step": version.created_step,
        "mat_id": mat.mat_id if mat is not None else None,
        "older_env": _older_env(here, mat),
        "reused": uid in here.reused,
        "eager": uid in here.eager,
        "auto_declined": _declined(here, uid),
    }


def cells(
    session: "FlowSession",
    branch: str,
    *,
    unsynced: bool = False,
    include_uid: bool = False,
) -> dict[str, Any]:
    here = read(session, branch)
    return {
        "flow": session.ref.name,
        "branch": branch,
        "cells": [
            cell(here, uid)
            | {"tracker": _cell_tracker(session, here, uid)}
            | ({"uid": uid} if include_uid else {})
            for uid in here.ordered()
            if not unsynced or not here.verdicts[uid].synced
        ],
    }


def show(session: "FlowSession", branch: str, slug: str) -> dict[str, Any]:
    here = read(session, branch)
    uid = here.uid_of(slug)
    version = here.versions[uid]
    mat = here.mats.get(uid)
    source = session.store.objects.get(version.raw_source_ref).decode("utf-8")
    return cell(here, uid) | {
        "uid": uid,
        "branch": branch,
        "definition_hash": version.definition_hash,
        "source": source,
        "doc": _docstring(source),
        "params": dict(version.manifest.params),
        "author": version.author,
        "produces": {
            name: {"type": spec.type, "kind": spec.kind, "persist": spec.persist}
            for name, spec in version.manifest.produces.items()
        },
        "materialized": _outputs(mat, version),
        "tracker": _cell_tracker(session, here, uid),
        "sdk_version_warning": (mat.sdk_version_warning if mat is not None else None),
        "error": failure(session, mat),
        "failed_by": _failed_by(session, mat),
        "provenance": _provenance(session, version),
        "notes": [
            {
                "kind": note.kind,
                "sentence": note.sentence,
                "version": note.version_id,
                "step": note.step,
                "actor": note.actor,
            }
            for note in session.store.index.cell_notes(here.branch.branch_id, uid)
        ],
    }


def logs(session: "FlowSession", branch: str, slug: str) -> dict[str, Any]:
    here = read(session, branch)
    mat = here.mats.get(here.uid_of(slug))
    return {
        "flow": session.ref.name,
        "branch": branch,
        "slug": slug,
        "state": mat.state if mat is not None else None,
        "logs": _captured(session, mat),
    }


def hygiene(session: "FlowSession") -> list[str]:
    tree = session.store.index.workspace_tree()
    if tree is None:
        return []
    prefix = f"{session.ref.relpath}/"
    return [stray_note(path) for path in sorted(tree.files) if path.startswith(prefix)]


def agent_sessions(
    session: "FlowSession", *, leased: frozenset[str] = frozenset()
) -> list[dict[str, Any]]:
    return [
        {
            "actor": row.actor,
            "label": row.label,
            "begun_step": row.begun_step,
            "leased": row.actor in leased,
        }
        for row in session.store.index.agent_sessions()
    ]


def tree(
    session: "FlowSession", *, leased: frozenset[str] = frozenset()
) -> dict[str, Any]:
    index = session.store.index
    bound = session.store.branches.bound_branch()
    sessions = index.agent_sessions()
    agent = sessions[0] if sessions else None
    return {
        "flow": session.ref.name,
        "branch": session.branch,
        "agent_sessions": agent_sessions(session, leased=leased),
        "branches": [
            _branch(session, record, checked_out=_same(bound, record), agent=agent)
            for record in index.branches()
        ],
    }


def graph(
    session: "FlowSession",
    branch: str,
    *,
    around: str | None = None,
    depth: int = DEFAULT_DEPTH,
) -> dict[str, Any]:
    here = read(session, branch)
    edges = _edges(here)
    kept = (
        set(here.versions)
        if around is None
        else _near(here.uid_of(around), edges, depth)
    )
    return {
        "flow": session.ref.name,
        "branch": branch,
        "around": around,
        "nodes": [cell(here, uid) for uid in here.ordered() if uid in kept],
        "edges": [
            {
                "from": f"{here.versions[producer].slug}.{output}",
                "to": here.versions[consumer].slug,
                "input": name,
            }
            for producer, consumer, output, name in sorted(
                edges, key=lambda edge: (edge[1], edge[3])
            )
            if producer in kept and consumer in kept
        ],
    }


def diff(session: "FlowSession", branches: list[str]) -> dict[str, Any]:
    slices = _compared(session, branches)
    definition: list[dict[str, Any]] = []
    materialization: list[dict[str, Any]] = []
    shapeless: list[dict[str, Any]] = []
    for uid in _compared_uids(slices):
        present = {name: here for name, here in slices.items() if uid in here.versions}
        name = next(iter(present.values())).versions[uid].slug
        if len(present) != len(slices) or _renamed(present, uid):
            shapeless.append(_shapeless(slices, uid, name))
        if len({here.versions[uid].definition_hash for here in present.values()}) > 1:
            definition.append(
                {
                    "slug": name,
                    "versions": [
                        _version_side(branch, here.versions[uid])
                        | _result_side(branch, here, uid)
                        for branch, here in present.items()
                    ],
                }
            )
        elif _results_differ(present.values(), uid):
            materialization.append(
                {
                    "slug": name,
                    "results": [
                        _result_side(branch, here, uid)
                        for branch, here in present.items()
                    ],
                }
            )
    return {
        "flow": session.ref.name,
        "branches": branches,
        "definition": definition,
        "materialization": materialization,
        "shapeless": shapeless,
        "integrity": _integrity(session, slices),
    }


def export(session: "FlowSession", branch: str) -> dict[str, Any]:
    here = read(session, branch)
    ordered = [here.versions[uid] for uid in planner.reading_order(here.versions)]
    carried = [
        portable.PortableCell(
            slug=version.slug,
            source=session.store.objects.get(version.raw_source_ref).decode("utf-8"),
        )
        for version in ordered
    ]
    return {
        "flow": session.ref.name,
        "branch": branch,
        "cells": [version.slug for version in ordered],
        "source": portable.render(carried, flow=session.ref.name, branch=branch),
    }


def asset(session: "FlowSession", branch: str, target: str) -> dict[str, Any]:
    here = read(session, branch)
    slug, output, record = locate(here, target)
    uid = here.uid_of(slug)
    version = here.versions[uid]
    mat = here.mats.get(uid)
    tracker = (
        _materialization_tracker(session, mat, record)
        if version.manifest.produces[output].type == "experiment"
        else None
    )
    return {
        "flow": session.ref.name,
        "branch": branch,
        "slug": slug,
        "output": output,
        "state": here.verdicts[here.uid_of(slug)].state,
        "kind": record.kind if record is not None else None,
        "size": record.size if record is not None else None,
        "persisted": record.persisted if record is not None else None,
        "preview": _preview(session, record),
        "tracker": tracker,
    }


def locate(here: Slice, target: str) -> tuple[str, str, OutputRecord | None]:
    slug, _, output = target.partition(".")
    uid = here.uid_of(slug)
    version = here.versions[uid]
    declared = list(version.manifest.produces)
    if output and output not in declared:
        raise CellNotFound(
            f"`{slug}` produces {_names(declared) or 'nothing'}, not `{output}`"
        )
    mat = here.mats.get(uid)
    name = output or primary_output(version, mat)
    if name is None:
        raise CellNotFound(f"`{slug}` declares no outputs")
    return slug, name, (mat.outputs.get(name) if mat is not None else None)


def training_frames(
    session: "FlowSession", model: MaterializationRow
) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for consumed in model.inputs.values():
        trained_on = session.store.index.materialization(consumed.mat_id)
        record = trained_on.outputs.get(consumed.output) if trained_on else None
        if record is None or record.kind != "frame" or record.value_ref is None:
            continue
        if not session.store.values.exists(record.value_ref):
            continue
        found.append({"value_ref": record.value_ref, "kind": record.kind})
    return found


def _kind_of(name: str, version: VersionRow, mat: MaterializationRow | None) -> str:
    spec = version.manifest.produces[name]
    record = mat.outputs.get(name) if mat is not None else None
    if spec.type != "asset":
        return spec.type
    return record.kind if record is not None else (spec.kind or "asset")


def primary_output(
    version: VersionRow, mat: MaterializationRow | None = None
) -> str | None:
    produces = version.manifest.produces
    if not produces:
        return None
    order = list(produces)
    return min(
        produces, key=lambda name: (_rank(name, version, mat), order.index(name))
    )


def downstream_outputs(
    version: VersionRow,
    mat: MaterializationRow | None = None,
    *,
    include_all: bool = False,
) -> list[str]:
    outputs = list(version.manifest.produces)
    if include_all:
        return outputs
    non_experiments = [
        name for name in outputs if _kind_of(name, version, mat) != "experiment"
    ]
    candidates = non_experiments or outputs
    if not candidates:
        return []
    return [
        min(
            candidates,
            key=lambda name: (_rank(name, version, mat), outputs.index(name)),
        )
    ]


def context(session: "FlowSession", branch: str) -> dict[str, Any]:
    here = read(session, branch)
    index = session.store.index
    checkpoint = index.checkpoint(here.branch.branch_id)
    dirty = [uid for uid in here.ordered() if not here.verdicts[uid].synced]
    sessions = index.agent_sessions()
    agent = sessions[0] if sessions else None
    bound = session.store.branches.bound_branch()
    checked_out = _same(bound, here.branch)
    rewrite = index.last_cells_rewrite(bound.branch_id) if bound is not None else None
    return {
        "workspace": str(session.workspace_dir),
        "flow": session.ref.name,
        "branch": branch,
        "checked_out": checked_out,
        "agent": agent.label if (checked_out and agent is not None) else None,
        "checkpoint": _transaction(checkpoint) if checkpoint is not None else None,
        "position": {
            "step": index.head_step(here.branch.branch_id),
            "newest": index.newest_step(here.branch.branch_id),
        },
        "last_cells_rewrite": (
            {"verb": rewrite.verb, "lane": bound.name, "step": rewrite.step}
            if rewrite is not None and bound is not None
            else None
        ),
        "cells": len(here.versions),
        "unsynced": [
            {
                "slug": here.versions[uid].slug,
                "state": here.verdicts[uid].state,
                "causes": [cause.detail for cause in here.verdicts[uid].causes],
            }
            for uid in dirty[:LISTED_UNSYNCED]
        ],
        "unsynced_omitted": max(0, len(dirty) - LISTED_UNSYNCED),
        "failures": _failures(session, here, dirty),
        "pending": _pending_cost(session, here, dirty),
        "recent": [
            _transaction(entry)
            for entry in index.history(
                limit=_RECENT_TRANSACTIONS,
                branch_id=here.branch.branch_id,
                shared=True,
            )
        ],
    }


def head(session: "FlowSession", branch: str, slug: str) -> VersionRow:
    record = session.store.branches.get(branch)
    for version in session.store.index.slice_versions(record.branch_id).values():
        if version.slug == slug:
            return version
    raise _missing(slug, branch)


def failure(session: "FlowSession", mat: MaterializationRow | None) -> str | None:
    if mat is None or mat.state == "succeeded":
        return None
    captured = _captured(session, mat)
    if captured is None:
        return None
    return "\n".join(captured.splitlines()[-_TRACEBACK_LINES:]).strip() or None


def _docstring(source: str) -> str:
    parsed = loader.parse(source).cell
    return inspect.cleandoc(parsed.docstring or "") if parsed is not None else ""


def _captured(session: "FlowSession", mat: MaterializationRow | None) -> str | None:
    if mat is None or mat.log_ref is None or not session.store.logs.exists(mat.log_ref):
        return None
    return session.store.logs.get(mat.log_ref).decode("utf-8", errors="replace")


def _failed_by(session: "FlowSession", mat: MaterializationRow | None) -> str | None:
    if mat is None or mat.state == "succeeded":
        return None
    version = session.store.index.version(mat.version_id)
    return version.author if version is not None else None


def _provenance(session: "FlowSession", version: VersionRow) -> dict[str, Any]:
    index = session.store.index
    born = index.first_version(version.uid) or version
    line = index.transaction(version.created_step)
    return {
        "created_by": born.author,
        "created_step": born.created_step,
        "last_edited_by": version.author,
        "step": version.created_step,
        "intent": line.intent if line is not None else None,
        "attribution_uncertain": MIXED_EDITING
        in index.transaction_flags(version.created_step),
    }


def _missing(slug: str, branch: str) -> CellNotFound:
    return CellNotFound(f"no cell named `{slug}` on `{branch}`")


def _compared(session: "FlowSession", branches: list[str]) -> dict[str, Slice]:
    if not MIN_COMPARED <= len(branches) <= MAX_COMPARED:
        raise FlowError(
            f"comparing takes {MIN_COMPARED} to {MAX_COMPARED} lanes, "
            f"not {len(branches)}"
        )
    if len(set(branches)) != len(branches):
        raise FlowError("comparing takes lanes that differ")
    return {name: read(session, name) for name in branches}


def _rank(name: str, version: VersionRow, mat: MaterializationRow | None) -> int:
    spec = version.manifest.produces[name]
    record = mat.outputs.get(name) if mat is not None else None
    claims = [spec.type, spec.kind, record.kind if record is not None else None]
    return min(_KIND_ORDER.get(claim or "", len(_KIND_ORDER)) for claim in claims)


def _branch(
    session: "FlowSession",
    record: BranchRow,
    *,
    checked_out: bool,
    agent: AgentSessionRow | None,
) -> dict[str, Any]:
    index = session.store.index
    verdicts = staleness.derive_all(index, record.branch_id)
    checkpoint = index.checkpoint(record.branch_id)
    standing = index.head(record.branch_id)
    head_step = standing.step if standing is not None else record.fork_step
    newest_step = index.newest_step(record.branch_id)
    parent = (
        index.branch_by_id(record.parent_branch_id)
        if record.parent_branch_id is not None
        else None
    )
    parent_step: int | None = None
    if parent is not None:
        parent_step = record.parent_step
    if parent is not None and parent_step is None:
        # A fork line from before positions were recorded: the parent's newest
        # line at the fork. The fork line belongs to the child, so it cannot
        # mask the parent's newest line at the same global step.
        found = index.last_step_on(parent.branch_id, at_or_before=record.fork_step)
        parent_step = record.fork_step if found is None else found
    states: dict[str, int] = {}
    for verdict in verdicts.values():
        states[verdict.state] = states.get(verdict.state, 0) + 1
    return {
        "branch": record.name,
        "branch_id": record.branch_id,
        "parent": parent.name if parent is not None else None,
        "forked_at_step": record.fork_step,
        "parent_step": parent_step,
        "archived": record.archived,
        "checked_out": checked_out,
        "cells": len(verdicts),
        "states": states,
        "checkpoint": checkpoint.step if checkpoint is not None else None,
        "head_step": head_step,
        "newest_step": newest_step,
        "last_intent": _transaction(standing) if standing is not None else None,
        "agent": agent.label if (checked_out and agent is not None) else None,
    }


def _edges(here: Slice) -> list[tuple[str, str, str, str]]:
    return [
        (ref.uid, uid, ref.output or "", name)
        for uid, version in here.versions.items()
        for name, ref in version.manifest.consumes.items()
        if ref.uid is not None and ref.uid in here.versions
    ]


def _near(uid: str, edges: Iterable[tuple[str, str, str, str]], depth: int) -> set[str]:
    adjacency: dict[str, set[str]] = {}
    for producer, consumer, _, _ in edges:
        adjacency.setdefault(producer, set()).add(consumer)
        adjacency.setdefault(consumer, set()).add(producer)
    reached, frontier = {uid}, {uid}
    for _ in range(max(0, depth)):
        frontier = {
            other
            for node in frontier
            for other in adjacency.get(node, set())
            if other not in reached
        }
        reached |= frontier
    return reached


def _declined(here: Slice, uid: str) -> dict[str, Any] | None:
    verdict = here.auto.get(uid)
    if verdict is None or verdict.taken:
        return None
    declined: dict[str, Any] = {
        "reason": verdict.reason,
        "estimate_seconds": verdict.estimate_seconds,
        "untimed": list(verdict.untimed),
    }
    if verdict.detail is not None:
        declined["detail"] = verdict.detail
    return declined


def _older_env(here: Slice, mat: MaterializationRow | None) -> bool:
    return (
        mat is not None
        and mat.env_lock_hash is not None
        and mat.env_lock_hash != here.env_lock_hash
    )


def _outputs(
    mat: MaterializationRow | None, version: VersionRow
) -> list[dict[str, Any]]:
    if mat is None:
        return []
    produces = version.manifest.produces
    return [
        {
            "name": name,
            "kind": record.kind,
            "kind_source": record.kind_source,
            # The four-word vocabulary the cell declared it under — what says
            # whether the output leaves the flow, which no inferred kind can:
            # a `model` whose value is a string still infers as a note.
            "declared": produces[name].type if name in produces else "asset",
            "size": record.size,
            "persisted": record.persisted,
        }
        for name, record in sorted(mat.outputs.items())
    ]


def _materialization_tracker(
    session: "FlowSession",
    mat: MaterializationRow | None,
    output: OutputRecord | None = None,
) -> dict[str, Any] | None:
    if mat is None:
        return None
    ref = output.tracker_ref if output is not None else None
    if ref is None:
        ref = next(
            (
                record.tracker_ref
                for record in mat.outputs.values()
                if record.tracker_ref is not None
            ),
            None,
        )
    if ref is None:
        if mat.experiment_id is None or mat.experiment_store is None:
            return None
        branch = session.store.index.branch_by_id(mat.branch_id)
        version = session.store.index.version(mat.version_id)
        ref = TrackerRef(
            experiment_id=mat.experiment_id,
            group=session.ref.name,
            store=mat.experiment_store,
            tags=[
                branch.name if branch is not None else "",
                version.slug if version is not None else "",
            ],
        )
    state = experiment_state(session, ref)
    record = state.record
    group = str(getattr(record, "group_name", None) or ref.group)
    group_id = getattr(record, "group_id", None)
    url = None
    if state.state == "ok" and group_id:
        url = (
            f"/experiments/{quote(str(group_id), safe='')}"
            f"/{quote(ref.experiment_id, safe='')}"
        )
    return {
        "id": ref.experiment_id,
        "group": group,
        "state": state.state,
        "url": url,
        "store": ref.store,
        "tags": [tag for tag in ref.tags if tag],
        "sentence": state.sentence,
        "recorded_step": mat.finished_step or mat.started_step,
    }


def _cell_tracker(
    session: "FlowSession", here: Slice, uid: str
) -> dict[str, Any] | None:
    version = here.versions[uid]
    if not any(
        spec.type == "experiment" for spec in version.manifest.produces.values()
    ):
        return None
    return _materialization_tracker(session, here.mats.get(uid))


def _failures(
    session: "FlowSession", here: Slice, dirty: list[str]
) -> list[dict[str, Any]]:
    failed = [uid for uid in dirty if here.verdicts[uid].state == "failed"]
    return [
        {
            "slug": here.versions[uid].slug,
            "error": failure(session, here.mats.get(uid)),
        }
        for uid in failed[:_REPORTED_FAILURES]
    ]


def _pending_cost(
    session: "FlowSession", here: Slice, dirty: list[str]
) -> dict[str, Any]:
    recompute: dict[str, None] = {}
    unknown: dict[str, None] = {}
    for uid in dirty:
        if here.versions[uid].manifest.classification == "note":
            continue
        preflight = session.planner.preflight(
            here.versions[uid].slug, branch=here.branch.name
        )
        recompute.update(dict.fromkeys(preflight.recompute))
        unknown.update(dict.fromkeys(preflight.unknown))
    by_slug = here.by_slug()
    seconds = sum(
        session.store.index.last_cost(by_slug[slug].uid) or 0.0
        for slug in recompute
        if slug in by_slug
    )
    return {
        "recompute": sorted(recompute),
        "unknown": sorted(unknown),
        "estimate_seconds": round(seconds, 6),
    }


def _compared_uids(slices: Mapping[str, Slice]) -> list[str]:
    seen: dict[str, str] = {}
    for here in slices.values():
        for uid, version in here.versions.items():
            seen.setdefault(uid, version.slug)
    return sorted(seen, key=lambda uid: seen[uid])


def _renamed(present: Mapping[str, Slice], uid: str) -> bool:
    return len({here.versions[uid].slug for here in present.values()}) > 1


def _shapeless(slices: Mapping[str, Slice], uid: str, name: str) -> dict[str, Any]:
    return {
        "slug": name,
        "branches": {
            branch: (here.versions[uid].slug if uid in here.versions else None)
            for branch, here in slices.items()
        },
    }


def _results_differ(present: Iterable[Slice], uid: str) -> bool:
    observed = {_fingerprint(here.mats.get(uid)) for here in present}
    return len(observed) > 1


def _fingerprint(mat: MaterializationRow | None) -> str:
    if mat is None:
        return "unmaterialized"
    return json.dumps(
        [mat.state, {name: r.content_hash for name, r in sorted(mat.outputs.items())}],
        sort_keys=True,
    )


def _version_side(branch: str, version: VersionRow) -> dict[str, Any]:
    return {
        "branch": branch,
        "slug": version.slug,
        "author": version.author,
        "step": version.created_step,
        "flags": [flag.code for flag in version.flags],
        "params": dict(version.manifest.params),
    }


def _integrity(
    session: "FlowSession", slices: Mapping[str, Slice]
) -> list[dict[str, Any]]:
    index = session.store.index
    named = {here.branch.branch_id: name for name, here in slices.items()}
    drifted: dict[tuple[str, str], list[str]] = {}
    for name, here in slices.items():
        above = slices.get(named.get(here.branch.parent_branch_id or "", ""))
        if above is None:
            continue
        for uid in index.pinned(here.branch.branch_id):
            mine, theirs = here.versions.get(uid), above.versions.get(uid)
            if mine is None or theirs is None:
                continue
            if mine.definition_hash != theirs.definition_hash:
                drifted.setdefault((mine.slug, above.branch.name), []).append(name)
    return [
        {
            "kind": "divergent-pin",
            "slug": slug,
            "branches": sorted(pinned),
            "message": (
                f"`{slug}` is pinned where these lanes split. `{parent}` "
                f"has edited it since. their results come from a different "
                f"`{slug}`"
            ),
        }
        for (slug, parent), pinned in sorted(drifted.items())
    ]


def _result_side(branch: str, here: Slice, uid: str) -> dict[str, Any]:
    mat = here.mats.get(uid)
    return {
        "branch": branch,
        "state": here.verdicts[uid].state,
        "cost_seconds": mat.cost_seconds if mat is not None else None,
        "outputs": _outputs(mat, here.versions[uid]),
    }


def _preview(session: "FlowSession", record: OutputRecord | None) -> Any:
    if record is None or record.preview_ref is None:
        return None
    if not session.store.previews.exists(record.preview_ref):
        return None
    try:
        return json.loads(session.store.previews.get(record.preview_ref))
    except ValueError:
        return None


def _transaction(entry: TransactionRow) -> dict[str, Any]:
    return {
        "step": entry.step,
        "ts": entry.ts,
        "actor": entry.actor,
        "intent": entry.intent,
        "offline": entry.offline,
        "settled": entry.settled,
        "mark": entry.mark,
        "position": entry.position,
    }


def _same(bound: BranchRow | None, record: BranchRow) -> bool:
    return bound is not None and bound.branch_id == record.branch_id


def _names(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def _tracker_path(value: str | Path) -> Path:
    raw = str(value)
    if raw.startswith("sqlite://"):
        raw = raw.removeprefix("sqlite://")
    return Path(raw).expanduser().resolve()


def _sdk_version_warning(session: "FlowSession", ref: TrackerRef) -> str | None:
    index = session.store.index
    for branch in index.branches():
        for mat_id in index.baselines(branch.branch_id).values():
            mat = index.materialization(mat_id)
            if mat is None or mat.sdk_version_warning is None:
                continue
            if mat.experiment_id == ref.experiment_id or any(
                output.tracker_ref == ref for output in mat.outputs.values()
            ):
                return mat.sdk_version_warning
    return None
