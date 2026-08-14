"""What a request could have to run, and what that will cost before it runs.

A plan is the minimal stale closure of a target: every ancestor that is not
current, everything between those and the target, any producer whose bytes were
never persisted — and the target itself. It is a set of *candidates*, not a set
of verdicts: whether a cell actually recomputes depends on what its parents
produce, and that is only known once they have. The queue decides that as it
goes, which is where early cutoff lives.

A preflight is the honest guess at the same question made in advance, so the
cost of a click is on screen before the click. It reads the keys it can compute
now and calls everything below a recompute a recompute, because that is what it
knows.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal

from lumlflow.flow.scheduler import memo, staleness
from lumlflow.flow.scheduler.staleness import Verdict
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import Index, VersionRow
from lumlflow.flow.store.models import ConsumedRef

#: Why reactivity left a cell for the user to run.
#:
#: `blocked` is a failure in the closure that nothing has changed since —
#: retrying it on every pass would be a loop. `never-timed` is a closure this
#: store has no measurement of, which is not the same as a cheap one: a
#: threshold cannot admit a cost nobody has ever observed. `too-expensive` is
#: the honest one — timed, and over the line.
AutoDecline = Literal["blocked", "never-timed", "too-expensive"]


@dataclass(frozen=True)
class Bound:
    """One resolved input: where its value sits and what it hashed to.

    `shared` is answered only under strict mode, where it decides whether the
    consumer is handed a copy — everywhere else the question costs a query
    nobody reads the answer to.
    """

    uid: str
    slug: str
    output: str
    kind: str
    content_hash: str
    mat_id: str
    value_ref: str | None
    shared: bool = False


@dataclass(frozen=True)
class Step:
    """A cell the request may have to execute.

    `needs_values` names this cell's outputs that a scheduled consumer will
    need the bytes of — which is what keeps a memo hit from satisfying a
    request the hit cannot feed.
    """

    uid: str
    slug: str
    version: VersionRow
    producers: tuple[str, ...] = ()
    needs_values: frozenset[str] = frozenset()
    estimate_seconds: float | None = None


@dataclass(frozen=True)
class Plan:
    branch: str
    branch_id: str
    target: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class AutoVerdict:
    """What reactivity decided about one cell, and what it decided it on.

    Served rather than re-derived: the sweep runs the `taken` ones and the card
    renders the rest, so "this is too expensive to refresh by itself" is one
    fact with one definition instead of a rule the UI restates and drifts from.
    """

    slug: str
    taken: bool
    reason: AutoDecline | None = None
    estimate_seconds: float = 0.0
    untimed: tuple[str, ...] = ()


@dataclass(frozen=True)
class Preflight:
    """`cached` is everything that will not execute — a hit or already current.

    `unknown` names cells this store has never timed, whose seconds are
    therefore missing from the total rather than guessed at.
    """

    branch: str
    target: str
    cached: tuple[str, ...]
    recompute: tuple[str, ...]
    unknown: tuple[str, ...]
    estimate_seconds: float


@dataclass(frozen=True)
class _Branch:
    """One branch's slice and its verdicts, read once and shared.

    Both are derived from the whole slice, so a caller planning several targets
    against the same branch pays for them once rather than once per target.
    """

    here: dict[str, VersionRow]
    verdicts: dict[str, Verdict]


class Planner:
    def __init__(self, store: FlowStore) -> None:
        self._store = store

    def plan(self, target: str, *, branch: str) -> Plan:
        branch_id = self._store.branches.get(branch).branch_id
        return self._plan(
            target, branch=branch, branch_id=branch_id, over=self._read(branch_id)
        )

    def _read(self, branch_id: str) -> "_Branch":
        return _Branch(
            here=self._store.index.slice_versions(branch_id),
            verdicts=staleness.derive_all(self._store.index, branch_id),
        )

    def _plan(
        self, target: str, *, branch: str, branch_id: str, over: "_Branch"
    ) -> Plan:
        """One plan against a slice and its verdicts already in hand.

        Split from `plan` because planning every stale cell — which is what
        reactivity asks for — would otherwise re-derive staleness once per
        cell, and that derivation is the expensive half of a plan.
        """
        here, verdicts = over.here, over.verdicts
        uid = self._store.branches.resolve(branch, target)
        if here[uid].manifest.classification == "note":
            # A note has no `materialize` to call; it is prose the branch
            # carries, and scheduling it would be a guaranteed failure.
            return Plan(branch, branch_id, target, ())
        producers = _producers(here)
        ancestors = _ancestors(uid, producers)
        consumers = _consumers(ancestors, producers)
        seed = {uid} | {other for other in ancestors if not verdicts[other].synced}
        kept = _close_down(seed, consumers)
        kept = self._with_demanded(kept, seed, consumers, here, branch_id)
        needs = _needed_outputs(kept, here)
        steps = tuple(
            Step(
                uid=other,
                slug=here[other].slug,
                version=here[other],
                producers=tuple(p for p in producers[other] if p in kept),
                needs_values=frozenset(needs[other]),
                estimate_seconds=self._store.index.last_cost(other),
            )
            for other in _ordered(kept, producers, here)
        )
        return Plan(branch, branch_id, target, steps)

    def preflight(self, *targets: str, branch: str) -> Preflight:
        """The cost of running these targets together, not one after another.

        Several targets share ancestors, so preflighting each alone and adding
        the totals would bill a common parent once per leaf. Their plans merge
        into one — deduplicated, still producers-before-consumers — and that is
        what the estimate is read off.
        """
        if not targets:
            raise ValueError("preflight needs at least one target")
        branch_id = self._store.branches.get(branch).branch_id
        over = self._read(branch_id)
        if len(targets) == 1:
            plan = self._plan(
                targets[0], branch=branch, branch_id=branch_id, over=over
            )
        else:
            plan = self._merged(targets, branch=branch, branch_id=branch_id, over=over)
        return self._preflight(plan, over.here)

    def _merged(
        self, targets: tuple[str, ...], *, branch: str, branch_id: str, over: "_Branch"
    ) -> Plan:
        here = over.here
        needs: dict[str, frozenset[str]] = {}
        steps: dict[str, Step] = {}
        for target in targets:
            planned = self._plan(
                target, branch=branch, branch_id=branch_id, over=over
            )
            for step in planned.steps:
                steps[step.uid] = step
                # A cell reached from two leaves is needed for the union of
                # what both wanted of it: dropping one leaf's outputs would let
                # a memo hit satisfy a request whose bytes it cannot feed.
                needs[step.uid] = needs.get(step.uid, frozenset()) | step.needs_values
        producers = _producers(here)
        kept = set(steps)
        return Plan(
            branch,
            branch_id,
            ", ".join(targets),
            tuple(
                replace(
                    steps[uid],
                    producers=tuple(p for p in producers[uid] if p in kept),
                    needs_values=needs[uid],
                )
                for uid in _ordered(kept, producers, here)
            ),
        )

    def _preflight(self, plan: Plan, here: dict[str, VersionRow]) -> Preflight:
        cached, recompute, unknown = [], [], []
        total = 0.0
        recomputing: set[str] = set()
        for step in plan.steps:
            if any(
                parent in recomputing for parent in step.producers
            ) or not self._served(plan.branch_id, step, here):
                recomputing.add(step.uid)
                recompute.append(step.slug)
                if step.estimate_seconds is None:
                    unknown.append(step.slug)
                else:
                    total += step.estimate_seconds
            else:
                cached.append(step.slug)
        return Preflight(
            branch=plan.branch,
            target=plan.target,
            cached=tuple(cached),
            recompute=tuple(recompute),
            unknown=tuple(unknown),
            estimate_seconds=round(total, 6),
        )

    def auto_targets(self, branch: str) -> list[str]:
        """What the reactivity setting says should run without being asked."""
        return [
            verdict.slug
            for verdict in self.auto_verdicts(branch).values()
            if verdict.taken
        ]

    def auto_verdicts(self, branch: str) -> dict[str, AutoVerdict]:
        """Reactivity's answer for every cell that is not already current.

        A change marks; only a closure that preflights under the threshold runs
        itself, so a cheap plot under an expensive stale parent still waits. A
        failure with nothing changed since is left alone — retrying it on every
        pass would be a loop, and the next edit is what makes it worth retrying.
        Its consumers are left alone for the same reason: running one would
        retry the failure underneath it on every pass just the same.

        A closure carrying a cell this store has never timed is left alone too,
        and this is the rule that makes the threshold mean anything: a preflight
        counts an unmeasured cell as nothing, so admitting one would let a
        six-hour train the flow has never run read as free and start itself the
        first time a workbench was opened on it. Under a threshold, an unknown
        cost is a cost that has not been shown to be under it. Running the cell
        once is what teaches the flow, and after that reactivity keeps it fresh.

        `eager` is the labelled way out of both cost gates — never out of the
        failure gate, which is about a run that cannot succeed rather than about
        what it would cost.

        Cells already current with nothing unsynced above them are absent
        entirely: reactivity has no opinion about a cell there is nothing to do
        to. Under `lazy` that is every cell, so the map is empty.
        """
        settings = self._store.manifest.settings
        if settings.reactivity == "lazy":
            return {}
        branch_id = self._store.branches.get(branch).branch_id
        over = self._read(branch_id)
        decided: dict[str, AutoVerdict] = {}
        for uid, verdict in sorted(
            over.verdicts.items(), key=lambda item: item[1].slug
        ):
            if not _worth_running(verdict, over.here[uid]):
                continue
            decided[uid] = self._auto_verdict(
                uid, verdict, branch=branch, branch_id=branch_id, over=over
            )
        return decided

    def _auto_verdict(
        self,
        uid: str,
        verdict: Verdict,
        *,
        branch: str,
        branch_id: str,
        over: "_Branch",
    ) -> AutoVerdict:
        settings = self._store.manifest.settings
        plan = self._plan(
            verdict.slug, branch=branch, branch_id=branch_id, over=over
        )
        if any(_stalled(over.verdicts[step.uid]) for step in plan.steps):
            return AutoVerdict(verdict.slug, taken=False, reason="blocked")
        cost = self._preflight(plan, over.here)
        if uid in settings.eager:
            return AutoVerdict(
                verdict.slug,
                taken=True,
                estimate_seconds=cost.estimate_seconds,
                untimed=cost.unknown,
            )
        if cost.unknown:
            return AutoVerdict(
                verdict.slug,
                taken=False,
                reason="never-timed",
                estimate_seconds=cost.estimate_seconds,
                untimed=cost.unknown,
            )
        return AutoVerdict(
            verdict.slug,
            taken=cost.estimate_seconds <= settings.eager_cost_threshold_s,
            reason=(
                None
                if cost.estimate_seconds <= settings.eager_cost_threshold_s
                else "too-expensive"
            ),
            estimate_seconds=cost.estimate_seconds,
        )

    def _with_demanded(
        self,
        kept: set[str],
        seed: set[str],
        consumers: dict[str, set[str]],
        here: dict[str, VersionRow],
        branch_id: str,
    ) -> set[str]:
        """Pull in producers whose bytes a scheduled consumer cannot read.

        Declared unpersisted outputs live nowhere, so demand for one schedules
        its producer whatever staleness says about it.
        """
        baselines = self._store.index.baselines(branch_id)
        while True:
            demanded = {
                ref.uid
                for uid in kept
                for ref in here[uid].manifest.consumes.values()
                if ref.uid is not None
                and ref.uid in consumers
                and ref.uid not in kept
                and self._bytes_missing(baselines, ref)
            }
            if not demanded:
                return kept
            seed |= demanded
            kept = _close_down(seed, consumers)

    def _bytes_missing(self, baselines: Mapping[str, str], ref: ConsumedRef) -> bool:
        mat_id = baselines.get(str(ref.uid))
        mat = self._store.index.materialization(mat_id) if mat_id else None
        if mat is None:
            return False
        record = mat.outputs.get(str(ref.output))
        return (
            record is None
            or record.value_ref is None
            or not self._store.values.exists(record.value_ref)
        )

    def _served(self, branch_id: str, step: Step, here: dict[str, VersionRow]) -> bool:
        """Could this step be answered from the store as things stand?"""
        inputs, missing = resolve_inputs(
            self._store.index, branch_id, step.version, here
        )
        if missing:
            return False
        hashes = {name: bound.content_hash for name, bound in inputs.items()}
        key = memo.key_for(self._store.index, step.version, hashes)
        return (
            current(self._store, branch_id, step, key)
            or memo.lookup(
                self._store, key, branch_id=branch_id, require_values=step.needs_values
            )
            is not None
        )


def current(store: FlowStore, branch_id: str, step: Step, key: str) -> bool:
    """Has this branch already run exactly this — the early-cutoff question.

    Asked of every step as the queue reaches it, so a parent that
    rematerialized to the same bytes leaves its consumers' keys unchanged and
    they are never executed again.
    """
    mat_id = store.index.baselines(branch_id).get(step.uid)
    mat = store.index.materialization(mat_id) if mat_id else None
    if mat is None or mat.state != "succeeded" or mat.memo_key != key:
        return False
    return memo.reusable(
        store, mat, branch_id=branch_id, require_values=step.needs_values
    )


def resolve_inputs(
    index: Index,
    branch_id: str,
    version: VersionRow,
    here: dict[str, VersionRow],
) -> tuple[dict[str, Bound], tuple[str, ...]]:
    """Every input's value as the branch resolves it now, and what it cannot.

    Resolution is two-step and version-free: the reference names a cell, the
    branch's baseline names which of its materializations this branch has.
    """
    baselines = index.baselines(branch_id)
    resolved: dict[str, Bound] = {}
    missing: list[str] = []
    for name, ref in version.manifest.consumes.items():
        bound = _bind(index, baselines, here, ref)
        if bound is None:
            missing.append(ref.ref)
        else:
            resolved[name] = bound
    return resolved, tuple(missing)


def _bind(
    index: Index,
    baselines: Mapping[str, str],
    here: dict[str, VersionRow],
    ref: ConsumedRef,
) -> Bound | None:
    if ref.uid is None or ref.output is None:
        return None
    mat_id = baselines.get(ref.uid)
    mat = index.materialization(mat_id) if mat_id else None
    if mat is None or mat.state != "succeeded":
        return None
    record = mat.outputs.get(ref.output)
    if record is None:
        return None
    producer = here.get(ref.uid)
    return Bound(
        uid=ref.uid,
        slug=producer.slug if producer is not None else ref.ref.split(".", 1)[0],
        output=ref.output,
        kind=record.kind,
        content_hash=record.content_hash,
        mat_id=mat.mat_id,
        value_ref=record.value_ref,
    )


def _producers(here: dict[str, VersionRow]) -> dict[str, list[str]]:
    return {
        uid: sorted(
            {
                ref.uid
                for ref in version.manifest.consumes.values()
                if ref.uid is not None and ref.uid in here
            }
        )
        for uid, version in here.items()
    }


def _ancestors(uid: str, producers: Mapping[str, list[str]]) -> set[str]:
    seen, stack = {uid}, [uid]
    while stack:
        for parent in producers[stack.pop()]:
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def _consumers(
    ancestors: set[str], producers: Mapping[str, list[str]]
) -> dict[str, set[str]]:
    """The edges pointing down, restricted to what leads to the target."""
    consumers: dict[str, set[str]] = {uid: set() for uid in ancestors}
    for uid in ancestors:
        for parent in producers[uid]:
            if parent in ancestors:
                consumers[parent].add(uid)
    return consumers


def _close_down(seed: set[str], consumers: Mapping[str, set[str]]) -> set[str]:
    """Everything downstream of the seed — a rerun above puts them all in play."""
    kept, stack = set(seed), list(seed)
    while stack:
        for child in consumers[stack.pop()]:
            if child not in kept:
                kept.add(child)
                stack.append(child)
    return kept


def _needed_outputs(kept: set[str], here: dict[str, VersionRow]) -> dict[str, set[str]]:
    needs: dict[str, set[str]] = defaultdict(set)
    for uid in kept:
        for ref in here[uid].manifest.consumes.values():
            if ref.uid in kept and ref.output is not None:
                needs[str(ref.uid)].add(ref.output)
    return needs


def reading_order(here: dict[str, VersionRow]) -> list[str]:
    """The whole slice, producers before consumers — how the flow reads through.

    The order a plan runs in, over everything rather than over one target's
    closure: what a notebook column and a single-file export both want, and one
    order both can be read against.
    """
    return _ordered(set(here), _producers(here), here)


def _ordered(
    kept: set[str], producers: Mapping[str, list[str]], here: dict[str, VersionRow]
) -> list[str]:
    """Topological over the kept set, ties broken by slug so plans are stable.

    A `consumes` cycle leaves cells no order can place; they go last, in name
    order, and the run they are part of fails on its own terms rather than here.
    """
    pending = {uid: {p for p in producers[uid] if p in kept} for uid in kept}
    ordered: list[str] = []
    while pending:
        ready = sorted(
            (uid for uid, parents in pending.items() if not parents),
            key=lambda uid: here[uid].slug,
        )
        if not ready:
            return ordered + sorted(pending, key=lambda uid: here[uid].slug)
        for uid in ready:
            del pending[uid]
        ordered.extend(ready)
        for parents in pending.values():
            parents.difference_update(ready)
    return ordered


def _worth_running(verdict: Verdict, version: VersionRow) -> bool:
    if version.manifest.classification == "note":
        return False
    if _stalled(verdict):
        return False
    return not verdict.synced or bool(verdict.upstream)


def _stalled(verdict: Verdict) -> bool:
    """Failed, with nothing changed since — waiting on an edit, not on a run."""
    return verdict.state == "failed" and not verdict.causes
