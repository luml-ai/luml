from collections import defaultdict
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from lumlflow.flow.errors import CellNotFound
from lumlflow.flow.scheduler import memo, staleness
from lumlflow.flow.scheduler.staleness import Verdict
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.index import Index, VersionRow
from lumlflow.flow.store.models import ConsumedRef, TrackerRef

AutoDecline = Literal[
    "blocked",
    "never-timed",
    "too-expensive",
    "dangling-experiment",
    "unresolvable-reference",
    "refresh-failed",
]
TrackerState = Literal["ok", "missing", "unreachable"]
TrackerStateCheck = Callable[[TrackerRef], tuple[TrackerState, str]]
RefreshEpoch = Callable[[], int]


def split_target(target: str, slugs: Collection[str]) -> tuple[str, str]:
    # Cell names may contain dots, so an exact name wins over `<cell>.<output>`.
    if target in slugs:
        return target, ""
    slug, _, output = target.rpartition(".")
    return (slug, output) if slug else (target, "")


@dataclass(frozen=True)
class Bound:
    uid: str
    slug: str
    output: str
    kind: str
    content_hash: str
    mat_id: str
    value_ref: str | None


@dataclass(frozen=True)
class Step:
    uid: str
    slug: str
    version: VersionRow
    producers: tuple[str, ...] = ()
    needs_values: frozenset[str] = frozenset()
    estimate_seconds: float | None = None
    must_execute: bool = False
    demand: str | None = None


@dataclass(frozen=True)
class Plan:
    branch: str
    branch_id: str
    target: str
    steps: tuple[Step, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AutoVerdict:
    slug: str
    taken: bool
    reason: AutoDecline | None = None
    estimate_seconds: float = 0.0
    untimed: tuple[str, ...] = ()
    detail: str | None = None


@dataclass(frozen=True)
class Preflight:
    branch: str
    target: str
    cached: tuple[str, ...]
    recompute: tuple[str, ...]
    unknown: tuple[str, ...]
    estimate_seconds: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Branch:
    here: dict[str, VersionRow]
    verdicts: dict[str, Verdict]


class Planner:
    def __init__(
        self,
        store: FlowStore,
        *,
        tracker_state: TrackerStateCheck | None = None,
        refresh_epoch: RefreshEpoch | None = None,
    ) -> None:
        self._store = store
        self._tracker_state = tracker_state or _tracker_ok
        self._refresh_epoch = refresh_epoch or _no_refresh_epoch

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
        here, verdicts = over.here, over.verdicts
        uid = self._resolve_target(target, branch=branch, here=here)
        if here[uid].manifest.classification == "note":
            return Plan(branch, branch_id, target, ())
        producers = _producers(here)
        ancestors = _ancestors(uid, producers)
        consumers = _consumers(ancestors, producers)
        seed = {uid} | {
            other
            for other in ancestors
            if not verdicts[other].synced
            or not self._baseline_reusable(branch_id, other)
        }
        kept = _close_down(seed, consumers)
        kept, forced = self._with_demanded(kept, seed, consumers, here, branch_id)
        needs = _needed_outputs(kept, here)
        ordered = _ordered(kept, producers, here)
        for other in ordered:
            demand = self._dangling_output(branch_id, other, here[other])
            if demand is not None:
                forced.setdefault(other, demand)
        steps = tuple(
            Step(
                uid=other,
                slug=here[other].slug,
                version=here[other],
                producers=tuple(p for p in producers[other] if p in kept),
                needs_values=frozenset(needs[other]),
                estimate_seconds=self._store.index.last_cost(other),
                must_execute=other in forced,
                demand=forced.get(other),
            )
            for other in ordered
        )
        return Plan(
            branch,
            branch_id,
            target,
            steps,
            tuple(dict.fromkeys(forced[other] for other in ordered if other in forced)),
        )

    def _resolve_target(
        self, target: str, *, branch: str, here: dict[str, VersionRow]
    ) -> str:
        slug, output = split_target(target, {version.slug for version in here.values()})
        uid = self._store.branches.resolve(branch, slug)
        produces = here[uid].manifest.produces
        if output and output not in produces:
            declared = ", ".join(f"`{name}`" for name in produces) or "nothing"
            raise CellNotFound(f"`{slug}` produces {declared}, not `{output}`")
        return uid

    def preflight(self, *targets: str, branch: str) -> Preflight:
        if not targets:
            raise ValueError("preflight needs at least one target")
        branch_id = self._store.branches.get(branch).branch_id
        over = self._read(branch_id)
        if len(targets) == 1:
            plan = self._plan(targets[0], branch=branch, branch_id=branch_id, over=over)
        else:
            plan = self._merged(
                [
                    self._plan(target, branch=branch, branch_id=branch_id, over=over)
                    for target in targets
                ],
                over.here,
            )
        return self._preflight(plan, over.here)

    def merge(self, plans: Sequence[Plan]) -> Plan:
        """One plan over several targets of one branch: a cell they share runs
        once, and every consumer reads the same result."""
        return self._merged(
            plans, self._store.index.slice_versions(plans[0].branch_id)
        )

    def unresolvable(self, plan: Plan) -> str | None:
        return _unresolvable(plan, self._store.index.slice_versions(plan.branch_id))

    def _merged(self, plans: Sequence[Plan], here: dict[str, VersionRow]) -> Plan:
        needs: dict[str, frozenset[str]] = {}
        steps: dict[str, Step] = {}
        reasons: list[str] = []
        for planned in plans:
            reasons.extend(planned.reasons)
            for step in planned.steps:
                previous = steps.get(step.uid)
                steps[step.uid] = replace(
                    step,
                    must_execute=step.must_execute
                    or (previous is not None and previous.must_execute),
                    demand=step.demand
                    or (previous.demand if previous is not None else None),
                )
                # A cell reached from two leaves is needed for the union of
                needs[step.uid] = needs.get(step.uid, frozenset()) | step.needs_values
        producers = _producers(here)
        kept = set(steps)
        return Plan(
            plans[0].branch,
            plans[0].branch_id,
            ", ".join(planned.target for planned in plans),
            tuple(
                replace(
                    steps[uid],
                    producers=tuple(p for p in producers[uid] if p in kept),
                    needs_values=needs[uid],
                )
                for uid in _ordered(kept, producers, here)
            ),
            tuple(dict.fromkeys(reasons)),
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
            reasons=plan.reasons,
        )

    def auto_targets(self, branch: str) -> list[str]:
        return [
            verdict.slug
            for verdict in self.auto_verdicts(branch).values()
            if verdict.taken
        ]

    def auto_verdicts(self, branch: str) -> dict[str, AutoVerdict]:
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
        plan = self._plan(verdict.slug, branch=branch, branch_id=branch_id, over=over)
        unresolved = _unresolvable(plan, over.here)
        if unresolved is not None:
            return AutoVerdict(
                verdict.slug,
                taken=False,
                reason="unresolvable-reference",
                detail=unresolved,
            )
        if plan.reasons:
            return AutoVerdict(
                verdict.slug,
                taken=False,
                reason="dangling-experiment",
                detail=" ".join(plan.reasons),
            )
        refresh_failure = self._active_refresh_failure(
            uid, over.here[uid], branch_id=branch_id
        )
        if refresh_failure is not None:
            return AutoVerdict(
                verdict.slug,
                taken=False,
                reason="refresh-failed",
                detail=refresh_failure,
            )
        stalled = next(
            (
                over.verdicts[step.uid]
                for step in plan.steps
                if _stalled(over.verdicts[step.uid])
            ),
            None,
        )
        if stalled is not None:
            return AutoVerdict(
                verdict.slug,
                taken=False,
                reason="blocked",
                detail=(
                    f"blocked by failed parent `{stalled.slug}`. "
                    f"edit `{stalled.slug}` to unblock auto-refresh."
                ),
            )
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

    def _active_refresh_failure(
        self, uid: str, version: VersionRow, *, branch_id: str
    ) -> str | None:
        note = next(
            (
                found
                for found in self._store.index.cell_notes(branch_id, uid)
                if found.kind == "refresh_failed"
            ),
            None,
        )
        if note is None or note.version_id != version.version_id:
            return None
        index = self._store.index
        selected_uids = {uid}
        selected_uids.update(
            ref.uid for ref in version.manifest.consumes.values() if ref.uid is not None
        )
        if (
            self._refresh_epoch() > note.step
            or index.workspace_code_step() > note.step
            or index.env_changed_step() > note.step
            or index.selection_changed_after(branch_id, selected_uids, note.step)
            or any(
                index.explicit_run_after(branch_id, selected_uid, note.step)
                for selected_uid in selected_uids
            )
        ):
            return None
        return note.sentence

    def _baseline_reusable(self, branch_id: str, uid: str) -> bool:
        # A synced verdict says nothing about results that read the outside
        # world or the branch they ran on; only the memo rules know those.
        mat_id = self._store.index.baselines(branch_id).get(uid)
        mat = self._store.index.materialization(mat_id) if mat_id else None
        return mat is None or memo.reusable(self._store, mat, branch_id=branch_id)

    def _with_demanded(
        self,
        kept: set[str],
        seed: set[str],
        consumers: dict[str, set[str]],
        here: dict[str, VersionRow],
        branch_id: str,
    ) -> tuple[set[str], dict[str, str]]:
        baselines = self._store.index.baselines(branch_id)
        forced: dict[str, str] = {}
        while True:
            demanded: set[str] = set()
            for uid in kept:
                for ref in here[uid].manifest.consumes.values():
                    if ref.uid is None or ref.uid not in consumers:
                        continue
                    missing, reason = self._input_missing(
                        baselines, ref, producer=here[ref.uid].slug
                    )
                    if reason is not None:
                        forced.setdefault(ref.uid, reason)
                    if missing and ref.uid not in kept:
                        demanded.add(ref.uid)
            if not demanded:
                return kept, forced
            seed |= demanded
            kept = _close_down(seed, consumers)

    def _input_missing(
        self,
        baselines: Mapping[str, str],
        ref: ConsumedRef,
        *,
        producer: str,
    ) -> tuple[bool, str | None]:
        mat_id = baselines.get(str(ref.uid))
        mat = self._store.index.materialization(mat_id) if mat_id else None
        if mat is None:
            return False, None
        record = mat.outputs.get(str(ref.output))
        if record is None:
            return True, None
        if record.tracker_ref is not None:
            reason = self._tracker_demand(record.tracker_ref, producer)
            if reason is not None:
                return True, reason
        return (
            record.value_ref is None or not self._store.values.exists(record.value_ref),
            None,
        )

    def _dangling_output(
        self, branch_id: str, uid: str, version: VersionRow
    ) -> str | None:
        mat_id = self._store.index.baselines(branch_id).get(uid)
        mat = self._store.index.materialization(mat_id) if mat_id else None
        if mat is None:
            return None
        for name, spec in version.manifest.produces.items():
            record = mat.outputs.get(name)
            if spec.type != "experiment" or record is None:
                continue
            if record.tracker_ref is None:
                continue
            reason = self._tracker_demand(record.tracker_ref, version.slug)
            if reason is not None:
                return reason
        return None

    def _tracker_demand(self, ref: TrackerRef, producer: str) -> str | None:
        state, sentence = self._tracker_state(ref)
        if state == "ok":
            return None
        condition = "removed" if state == "missing" else "unreachable"
        return (
            f"`{producer}` must run because its {condition} experiment "
            f"`{ref.experiment_id}` is needed. {sentence}"
        )

    def _served(self, branch_id: str, step: Step, here: dict[str, VersionRow]) -> bool:
        if step.must_execute:
            return False
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
        slug=producer.slug if producer is not None else ref.ref.rpartition(".")[0],
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
    consumers: dict[str, set[str]] = {uid: set() for uid in ancestors}
    for uid in ancestors:
        for parent in producers[uid]:
            if parent in ancestors:
                consumers[parent].add(uid)
    return consumers


def _close_down(seed: set[str], consumers: Mapping[str, set[str]]) -> set[str]:
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


def _unresolvable(plan: Plan, here: Mapping[str, VersionRow]) -> str | None:
    for step in plan.steps:
        for ref in step.version.manifest.consumes.values():
            producer = here.get(ref.uid) if ref.uid is not None else None
            if (
                producer is not None
                and ref.output is not None
                and ref.output in producer.manifest.produces
            ):
                continue
            return (
                f"`{step.slug}` needs `{ref.ref}`, which nothing on "
                f"`{plan.branch}` produces"
            )
    return None


def reading_order(here: dict[str, VersionRow]) -> list[str]:
    return _ordered(set(here), _producers(here), here)


def _ordered(
    kept: set[str], producers: Mapping[str, list[str]], here: dict[str, VersionRow]
) -> list[str]:
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
    return verdict.state == "failed" and not verdict.causes


def _tracker_ok(_ref: TrackerRef) -> tuple[TrackerState, str]:
    return "ok", ""


def _no_refresh_epoch() -> int:
    return 0
