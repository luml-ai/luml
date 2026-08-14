"""The read side of the daemon API: what a surface renders, shaped once here.

Every verdict a surface shows — staleness and its causes, what diverged between
branches, what the pending work costs — is derived from recorded facts on this
side of the socket, so the CLI, the MCP server and the browser cannot disagree
about them. Nothing here writes.

The vocabulary is the user's: cells are named by slug, branches by name, outputs
by the names the cell declared. Identifiers the runtime keys on — uids, content
hashes, memo keys — stay inside; these shapes carry verdicts and words instead,
which is what keeps them out of every surface built on top.
"""

import inspect
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

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
from lumlflow.flow.store.models import OutputRecord

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

MIN_COMPARED = 2
MAX_COMPARED = 5
DEFAULT_DEPTH = 2

_RECENT_TRANSACTIONS = 8
LISTED_UNSYNCED = 10
_REPORTED_FAILURES = 3
_TRACEBACK_LINES = 12

# `experiment > eval > plot > frame > note > metric > dataset > model > file >
# checkpoint > pickle`: experiments, evals and plots are what a reader came for;
# a model's config dump is not. Declared asset types share the ordering with
# inferred kinds — a cell that says `experiment` and one whose value turned out
# to be an experiment are the same thing to a reader.
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
class Slice:
    """One branch's cells, its verdicts about them, and what it last observed."""

    branch: BranchRow
    versions: dict[str, VersionRow]
    verdicts: dict[str, Verdict]
    mats: dict[str, MaterializationRow]
    env_lock_hash: str | None = None
    #: Cells whose baseline a memo hit put there — nothing ran for them here.
    reused: frozenset[str] = frozenset()
    #: The step each cell was minted at, store-wide — the notebook's tiebreak.
    born: dict[str, int] = field(default_factory=dict)
    #: Cells opted into eager materialization, whatever the cost threshold says.
    eager: frozenset[str] = frozenset()
    #: How to ask reactivity what it decided. Deferred, not held: answering
    #: costs a plan per stale cell, and most reads of a slice — paging a value,
    #: diffing, previewing — never look. `auto` is the property that asks.
    reactivity: "Callable[[], dict[str, planner.AutoVerdict]]" = dict

    @cached_property
    def auto(self) -> dict[str, planner.AutoVerdict]:
        """What reactivity decided about each cell it has an opinion about.

        Only the ones that are not already current are in it, and under `lazy`
        none of them are — reactivity has no opinion about a cell it will never
        act on either way.
        """
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
        eager=frozenset(session.store.manifest.settings.eager),
        reactivity=lambda: session.planner.auto_verdicts(branch),
    )


def cell(here: Slice, uid: str) -> dict[str, Any]:
    """One card's worth of facts: what it is, where it stands, and why."""
    version, verdict = here.versions[uid], here.verdicts[uid]
    mat = here.mats.get(uid)
    return {
        "slug": version.slug,
        "state": verdict.state,
        "causes": [cause.detail for cause in verdict.causes],
        "upstream": list(verdict.upstream),
        # The transitive view, served rather than left to be re-derived from the
        # two fields above: a surface that computed it would be the second place
        # this verdict is defined, and the first one to drift.
        "transitive": verdict.transitive,
        "outputs": list(version.manifest.produces),
        # What each output reads as, so a lens over the slice — the panel's
        # experiments, models and data — can name kinds without pulling every
        # cell's detail and every preview behind it.
        "kinds": {
            name: _kind_of(name, version, mat) for name in version.manifest.produces
        },
        "primary": primary_output(version, mat),
        "consumes": {name: ref.ref for name, ref in version.manifest.consumes.items()},
        "note": version.manifest.classification == "note",
        # Reads something the store does not version — a workspace file, a
        # network call — so it never memoizes and its inputs are not ours to
        # track. Declared or observed on the last run; either one is the fact.
        "external": (mat is not None and mat.external)
        or version.manifest.volatility == "external",
        "flags": [{"code": flag.code, "detail": flag.detail} for flag in version.flags],
        "cost_seconds": mat.cost_seconds if mat is not None else None,
        # The mint order, which is what breaks ties in the notebook's column:
        # sorting siblings by name would move a card whenever one is renamed.
        "created_step": here.born.get(uid, 0),
        "older_env": _older_env(here, mat),
        # A memo hit put this result here: the cost below is what the run cost
        # whoever ran it, and printing that alone would read as work that just
        # happened. A fork inheriting a baseline is not this — nothing was
        # claimed for it, and nothing is badged.
        "reused": uid in here.reused,
        # Opted out of the cost threshold: this one rematerializes on change
        # however expensive its closure is.
        "eager": uid in here.eager,
        # Why this one is *not* refreshing itself, when reactivity is on and it
        # is out of date. Silence is the thing that made auto mode feel broken:
        # a cell whose closure is over the threshold looked exactly like a cell
        # the runtime had forgotten about.
        "auto_declined": _declined(here, uid),
    }


def cells(
    session: "FlowSession", branch: str, *, unsynced: bool = False
) -> dict[str, Any]:
    here = read(session, branch)
    return {
        "flow": session.ref.name,
        "branch": branch,
        "cells": [
            cell(here, uid)
            for uid in here.ordered()
            if not unsynced or not here.verdicts[uid].synced
        ],
    }


def show(session: "FlowSession", branch: str, slug: str) -> dict[str, Any]:
    """A cell in full: its source, its declarations, and its last run."""
    here = read(session, branch)
    uid = here.uid_of(slug)
    version = here.versions[uid]
    mat = here.mats.get(uid)
    source = session.store.objects.get(version.raw_source_ref).decode("utf-8")
    return cell(here, uid) | {
        "branch": branch,
        # The version an editor started from, handed back with `cells edit
        # --base` to take the optimistic lock. Nothing prints it.
        "definition_hash": version.definition_hash,
        "source": source,
        # What the cell says it is, in the author's words — and the whole of a
        # note cell, whose docstring is not a description of the content but
        # the content.
        "doc": _docstring(source),
        "params": dict(version.manifest.params),
        "author": version.author,
        "produces": {
            name: {"type": spec.type, "kind": spec.kind, "persist": spec.persist}
            for name, spec in version.manifest.produces.items()
        },
        "materialized": _outputs(mat, version),
        "error": failure(session, mat),
        # Who wrote the version that broke, which need not be whoever wrote the
        # one on screen: an edit after a failure moves the head and leaves the
        # failure where it happened.
        "failed_by": _failed_by(session, mat),
        "provenance": _provenance(session, version),
    }


def logs(session: "FlowSession", branch: str, slug: str) -> dict[str, Any]:
    """The console the branch's last observed run of this cell left behind.

    Keyed on the baseline rather than on the newest run anywhere, so a rewound
    branch answers with *that* run's output: every materialization keeps its
    own capped artifact, and reading the latest would show a run this branch
    has no record of.
    """
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
    """Shared code sitting inside the flow — a note, never a refusal.

    Read off the recorded workspace tree rather than the disk: the scan already
    drops `cells/` under a flow root, so anything left under this flow's
    directory is a stray by construction and no second walk is needed.
    """
    tree = session.store.index.workspace_tree()
    if tree is None:
        return []
    prefix = f"{session.ref.relpath}/"
    return [stray_note(path) for path in sorted(tree.files) if path.startswith(prefix)]


def tree(session: "FlowSession") -> dict[str, Any]:
    """The fork tree: every branch, where it split, and how it stands.

    Read from the store rather than from any session's memory, so a branch
    nobody has viewed since the daemon started reads the same as the open one.
    """
    index = session.store.index
    bound = session.store.branches.bound_branch()
    holder = index.worktree_holder()
    return {
        "flow": session.ref.name,
        "branch": session.branch,
        "branches": [
            _branch(session, record, checked_out=_same(bound, record), holder=holder)
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
    """The declared wiring — the graph the scheduler runs, not a second one.

    `around` slices a neighbourhood out of it: the cells within `depth` hops of
    one, upstream and downstream both, which is what keeps a large flow's graph
    answerable in a terminal.
    """
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
    """How 2–5 branches differ, split by what a reader can do about it.

    Definition divergence is someone having edited the cell — structural, rare,
    and the branching point of everything below it. Materialization divergence
    is the same code fed different inputs, which is most of a sweep and collapses
    to one row per asset. What neither shape covers — a cell one branch does not
    carry, a name that moved — is listed exhaustively underneath.
    """
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
                    # Each side says what it is *and* what it produced: a
                    # comparison whose subject is the edited cell would
                    # otherwise be the one asset with no results on screen.
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
    """A branch's cells as one file — the flow's travelling form, not the flow.

    Producers first, so the file reads the way the flow runs, and the sources
    are the ones the store holds rather than the ones on disk: a branch nobody
    has checked out exports exactly as well as the one somebody has.
    """
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
    """One output as the store holds it: its verdict, and its stored preview.

    Previews are the kernel-free tier — browsing a flow never starts a process,
    however large the value behind it is.
    """
    here = read(session, branch)
    slug, output, record = locate(here, target)
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
    }


def asset_diff(
    session: "FlowSession", branches: list[str], target: str
) -> dict[str, Any]:
    """One asset across two branches: did the code move, did the result move."""
    if len(branches) != MIN_COMPARED:
        raise FlowError("comparing one asset takes two lanes")
    slices = _compared(session, branches)
    slug, _, output = target.partition(".")
    sides = [
        {"branch": name}
        | (
            _result_side(name, here, here.by_slug()[slug].uid)
            if slug in here.by_slug()
            else {"state": "absent"}
        )
        for name, here in slices.items()
    ]
    definitions = {
        here.by_slug()[slug].definition_hash
        for here in slices.values()
        if slug in here.by_slug()
    }
    return {
        "flow": session.ref.name,
        "slug": slug,
        "output": output or None,
        "branches": branches,
        "definition": "same" if len(definitions) == 1 else "differs",
        "result": _result_verdict(
            [_content_hashes(here, slug, output) for here in slices.values()]
        ),
        "sides": sides,
    }


def locate(here: Slice, target: str) -> tuple[str, str, OutputRecord | None]:
    """Resolve `slug` or `slug.output` to the output record the branch observed.

    A bare slug means the cell's primary output — the one its card opens on — so
    that naming an asset never requires knowing how many outputs it has.
    """
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


def repl_names(session: "FlowSession", here: Slice) -> dict[str, dict[str, str]]:
    """The names scratch code resolves on a branch, and where their bytes are.

    Every stored output is `cell_output`, and each cell's primary output is
    also its own bare name — the same two spellings `slug.output` and `slug`
    already mean everywhere else, rendered as identifiers. A cell's own name
    never loses to a derived one.

    Only outputs whose bytes are in the store are named: a declared
    `persist: False` output has none to hand out, and a name bound to nothing
    would read as a value that is empty rather than one that was never kept.
    """
    derived: dict[str, dict[str, str]] = {}
    primary: dict[str, dict[str, str]] = {}
    for uid, version in here.versions.items():
        mat = here.mats.get(uid)
        if mat is None or mat.state != "succeeded":
            continue
        leading = primary_output(version, mat)
        for name, record in mat.outputs.items():
            if record.value_ref is None or not session.store.values.exists(
                record.value_ref
            ):
                continue
            where = {"value_ref": record.value_ref, "kind": record.kind}
            derived[f"{version.slug}_{name}"] = where
            if name == leading:
                primary[version.slug] = where
    return derived | primary


def _kind_of(name: str, version: VersionRow, mat: MaterializationRow | None) -> str:
    """What one output reads as — the badge, and what a lens groups it under.

    The declared word wins where there is one: `model`, `dataset` and
    `experiment` say what leaves the flow, and a run whose value happened to
    infer as a frame or a dict of numbers does not demote it. An `asset` says
    nothing about shape, so what the value turned out to be answers for it.
    """
    spec = version.manifest.produces[name]
    record = mat.outputs.get(name) if mat is not None else None
    if spec.type != "asset":
        return spec.type
    return record.kind if record is not None else (spec.kind or "asset")


def primary_output(
    version: VersionRow, mat: MaterializationRow | None = None
) -> str | None:
    """The output a cell is read by: experiments and plots first, dumps last."""
    produces = version.manifest.produces
    if not produces:
        return None
    order = list(produces)
    return min(
        produces, key=lambda name: (_rank(name, version, mat), order.index(name))
    )


def context(session: "FlowSession", branch: str) -> dict[str, Any]:
    """The brief an agent reads before it does anything: where it is, what is
    unsynced and why, what broke, what the pending work costs, what just
    happened.

    Budgeted on purpose — an agent that has to page through its own orientation
    reads none of it.
    """
    here = read(session, branch)
    index = session.store.index
    checkpoint = index.checkpoint(here.branch.branch_id)
    dirty = [uid for uid in here.ordered() if not here.verdicts[uid].synced]
    holder = index.worktree_holder()
    focus = session.focus
    # Both facts are about the files, and the files are one branch's: a brief on
    # a branch nobody checked out must not claim the agent working in `main` is
    # working in it.
    checked_out = _same(session.store.branches.bound_branch(), here.branch)
    return {
        "workspace": str(session.workspace_dir),
        "flow": session.ref.name,
        "branch": branch,
        "checked_out": checked_out,
        "agent": holder.label if (checked_out and holder is not None) else None,
        # Omitted rather than nulled when nothing was reported: an agent reading
        # this must not spend a line learning that the user is nowhere.
        **(
            {
                "focus": {
                    "branch": focus.branch,
                    "asset": focus.asset,
                    "compare": list(focus.compare),
                }
            }
            if focus is not None
            else {}
        ),
        "checkpoint": _transaction(checkpoint) if checkpoint is not None else None,
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
    """The version a branch selects for a name — what an edit starts from.

    A slice read without the verdicts: what asks for this is about to write, not
    to render, and deriving staleness for it would be work nobody reads.
    """
    record = session.store.branches.get(branch)
    for version in session.store.index.slice_versions(record.branch_id).values():
        if version.slug == slug:
            return version
    raise _missing(slug, branch)


def failure(session: "FlowSession", mat: MaterializationRow | None) -> str | None:
    """The tail of a failed run's log — the traceback, where the cell left it."""
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
    """Who made this cell, who last touched it, and how sure the store is.

    The last word is the honest one: a version accepted while an agent held the
    worktree may well have been the human typing in another window, and the
    transaction that recorded it says as much. Nothing here guesses a name over
    a flag the runtime already raised.
    """
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
    """One wording for a name the branch does not know, wherever it is asked."""
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
    """Where this output sits in the reading order.

    Both what the cell said and what the value turned out to be count, and the
    stronger claim wins: a dict of numbers infers as a `metric` whether it is a
    config dump or the run whose experiment the reader came for — the declared
    `experiment` is what tells those apart.
    """
    spec = version.manifest.produces[name]
    record = mat.outputs.get(name) if mat is not None else None
    claims = [spec.type, spec.kind, record.kind if record is not None else None]
    return min(_KIND_ORDER.get(claim or "", len(_KIND_ORDER)) for claim in claims)


def _branch(
    session: "FlowSession",
    record: BranchRow,
    *,
    checked_out: bool,
    holder: AgentSessionRow | None,
) -> dict[str, Any]:
    index = session.store.index
    verdicts = staleness.derive_all(index, record.branch_id)
    checkpoint = index.checkpoint(record.branch_id)
    last = index.history(limit=1, branch_id=record.branch_id)
    parent = (
        index.branch_by_id(record.parent_branch_id)
        if record.parent_branch_id is not None
        else None
    )
    states: dict[str, int] = {}
    for verdict in verdicts.values():
        states[verdict.state] = states.get(verdict.state, 0) + 1
    return {
        "branch": record.name,
        # The key the journal scopes transactions by. A surface never prints it
        # — branches are named — but a client reading the stream has no other
        # way to tell which branch a transaction landed on.
        "branch_id": record.branch_id,
        "parent": parent.name if parent is not None else None,
        "forked_at_step": record.fork_step,
        "archived": record.archived,
        "checked_out": checked_out,
        "cells": len(verdicts),
        "states": states,
        "checkpoint": checkpoint.step if checkpoint is not None else None,
        "last_intent": _transaction(last[0]) if last else None,
        "agent": holder.label if (checked_out and holder is not None) else None,
    }


def _edges(here: Slice) -> list[tuple[str, str, str, str]]:
    """(producer, consumer, output, input name) for wiring that resolved."""
    return [
        (ref.uid, uid, ref.output or "", name)
        for uid, version in here.versions.items()
        for name, ref in version.manifest.consumes.items()
        if ref.uid is not None and ref.uid in here.versions
    ]


def _near(uid: str, edges: Iterable[tuple[str, str, str, str]], depth: int) -> set[str]:
    """Everything within `depth` hops of a cell, upstream and downstream."""
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
    """Reactivity's refusal, in the words a card renders — or None.

    None covers three different silences that need no sentence: reactivity is
    off, the cell is current, or the cell is about to refresh itself and saying
    so would be a label that is gone by the time it is read.
    """
    verdict = here.auto.get(uid)
    if verdict is None or verdict.taken:
        return None
    return {
        "reason": verdict.reason,
        "estimate_seconds": verdict.estimate_seconds,
        "untimed": list(verdict.untimed),
    }


def _older_env(here: Slice, mat: MaterializationRow | None) -> bool:
    """Was this result computed under packages the workspace has since moved?

    Provenance, not staleness — the result stands, and nothing reruns over it.
    A run from before the flow observed any env recorded no lock hash, and
    calling that older than something would compare against a baseline that
    never existed.
    """
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
            "uploaded": record.luml_ref is not None,
        }
        for name, record in sorted(mat.outputs.items())
    ]


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
    """What running everything unsynced would cost, counted once per cell."""
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
    """What a branch has of an asset, as one comparable string."""
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
        # What the sides of a sweep actually differ by, nine times in ten. They
        # are declared data and stay read-only wherever they are shown.
        "params": dict(version.manifest.params),
    }


def _integrity(
    session: "FlowSession", slices: Mapping[str, Slice]
) -> list[dict[str, Any]]:
    """Where pin-at-fork stopped holding, so the columns are not comparable.

    A fork pins its parent's selections, which is what keeps a sweep varying
    exactly what its branches edited and nothing else. The one thing that
    breaks it is the parent moving on: a branch still holding what it pinned,
    read beside the branch that has edited the cell since, is two results
    computed under different code — a difference nobody chose and the reason a
    side-by-side of two numbers can be worse than no comparison at all.
    """
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


def _content_hashes(here: Slice, slug: str, output: str) -> str | None:
    by_slug = here.by_slug()
    if slug not in by_slug:
        return None
    mat = here.mats.get(by_slug[slug].uid)
    if mat is None or mat.state != "succeeded":
        return None
    wanted = {name: r.content_hash for name, r in mat.outputs.items()}
    if output:
        wanted = {name: value for name, value in wanted.items() if name == output}
    return json.dumps(wanted, sort_keys=True)


def _result_verdict(observed: list[str | None]) -> str:
    if any(record is None for record in observed):
        return "unmaterialized"
    return "same" if len(set(observed)) == 1 else "differs"


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
    }


def _same(bound: BranchRow | None, record: BranchRow) -> bool:
    return bound is not None and bound.branch_id == record.branch_id


def _names(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)
