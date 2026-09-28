"""The run queue: one cell at a time, the branch you are looking at first.

Execution is serial by design — one kernel runs one cell — so the queue's real
work is deciding what does *not* have to run. Three rules do that, applied to
each step of a plan as it is reached, against facts that may have changed while
the step above it ran:

*Early cutoff.* A step whose memo key matches what this branch already ran is
skipped. A parent that rematerialized to the same bytes leaves its consumers'
keys untouched, so a plan collapses to nothing below the change.

*Memo hits.* A key matching any succeeded materialization is journaled as a hit
rather than executed, cross-branch included.

*Coalescing.* A key already in flight is awaited, not started twice — twenty
forks of one sweep share one run. That run is preempted only when the last
branch awaiting it has stopped wanting it; one branch editing out from under it
just leaves.
"""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from lumlflow.flow.errors import FlowError, InputUnavailable
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.scheduler import memo
from lumlflow.flow.scheduler.planner import (
    Bound,
    Plan,
    Planner,
    Step,
    current,
    resolve_inputs,
)
from lumlflow.flow.store.flowstore import FlowStore
from lumlflow.flow.store.models import (
    CellNoted,
    InputRef,
    MaterializationState,
    MemoHit,
    OutputRecord,
    OutputSpec,
    RunRecorded,
    TrackerRef,
)

StepOutcome = Literal["pruned", "cached", "executed", "failed", "abandoned"]


@dataclass(frozen=True)
class RunRequest:
    """What a kernel needs to run one cell. No store handles cross this line."""

    run_id: str
    flow: str
    flow_id: str
    flow_path: str
    branch: str
    step: int
    uid: str
    slug: str
    version_id: str
    source: str
    produces: dict[str, OutputSpec]
    params: dict[str, Any]
    inputs: dict[str, Bound]


@dataclass(frozen=True)
class RunResult:
    state: MaterializationState
    outputs: dict[str, OutputRecord] = field(default_factory=dict)
    identity_dependent: bool = False
    external: bool = False
    cost_seconds: float | None = None
    log_ref: str | None = None
    experiment_id: str | None = None
    experiment_store: str | None = None
    experiment_close_error: str | None = None
    sdk_version_warning: str | None = None


class Executor(Protocol):
    async def run(self, request: RunRequest) -> RunResult: ...

    def cancel(self, run_id: str) -> None: ...


@dataclass(frozen=True)
class RunOutcome:
    branch: str
    target: str
    executed: tuple[str, ...] = ()
    cached: tuple[str, ...] = ()
    pruned: tuple[str, ...] = ()
    failed: str | None = None
    abandoned: bool = False


@dataclass(frozen=True)
class Abandoned:
    """What leaving a run actually did — the wording after the click.

    `stopped` is false when other branches were still awaiting the result, in
    which case this branch merely left and `awaiting` counts who stayed.
    """

    branch: str
    left: int = 0
    stopped: bool = False
    awaiting: int = 0


@dataclass
class _Waiter:
    branch: str
    future: "asyncio.Future[RunResult | None]"
    abandoned: bool = False


@dataclass
class _Flight:
    """One execution and everyone waiting on it, keyed by its memo key."""

    key: str
    run_id: str
    origin: str
    slug: str = ""
    waiters: list[_Waiter] = field(default_factory=list)
    task: "asyncio.Task[None] | None" = None
    mat_id: str | None = None
    preempted: bool = False


class RunQueue:
    def __init__(
        self,
        store: FlowStore,
        executor: Executor,
        *,
        planner: Planner | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._store = store
        self._executor = executor
        self._planner = planner or Planner(store)
        self._active: str | None = None
        self._flights: dict[str, _Flight] = {}
        self._busy = False
        self._gate: list[tuple[str, asyncio.Future[None]]] = []
        self._on_event = on_event

    @property
    def busy(self) -> bool:
        """Is a cell executing right now — what a kernel restart would kill."""
        return self._busy

    def focus(self, branch: str | None) -> None:
        """The branch the user is watching: it goes first when the gate frees."""
        self._active = branch

    async def submit(
        self, target: str, *, branch: str, actor: str = "user", force: bool = False
    ) -> RunOutcome:
        """Run the target's minimal stale closure.

        `force` is the labeled modifier, not the default: it drops both savings
        — early cutoff and memo hits — for every step of *this* plan, so a
        result the store could have served is computed again. Ancestors the
        branch already has current stay out of the plan either way; forcing
        re-runs the closure the request is about, not the whole flow.
        """
        plan = self._planner.plan(target, branch=branch)
        _validate_experiment_outputs(plan)
        done: dict[str, list[str]] = {"executed": [], "cached": [], "pruned": []}
        failed: str | None = None
        abandoned = False
        for step in plan.steps:
            outcome = await self._advance(plan, step, actor=actor, force=force)
            if outcome in ("failed", "abandoned"):
                # Nothing below a step that did not produce can run: its
                # consumers have no input to resolve.
                failed = step.slug if outcome == "failed" else None
                abandoned = outcome == "abandoned"
                break
            done[outcome].append(step.slug)
        return RunOutcome(
            branch=branch,
            target=target,
            executed=tuple(done["executed"]),
            cached=tuple(done["cached"]),
            pruned=tuple(done["pruned"]),
            failed=failed,
            abandoned=abandoned,
        )

    def abandon(self, branch: str) -> Abandoned:
        """The branch's inputs moved: stop it awaiting what it no longer wants.

        Preemption is the last waiter leaving, never the first. A run twenty
        forks are awaiting keeps going when one of them edits; only that branch
        re-queues — and the report says which of the two happened, so nothing
        upstream has to claim a run stopped that is still going.
        """
        left = 0
        stopped = False
        awaiting = 0
        for flight in list(self._flights.values()):
            leaving = [waiter for waiter in flight.waiters if waiter.branch == branch]
            if not leaving:
                continue
            left += 1
            flight.waiters = [w for w in flight.waiters if w.branch != branch]
            for waiter in leaving:
                waiter.abandoned = True
                if not waiter.future.done():
                    waiter.future.set_result(None)
            if not flight.waiters:
                flight.preempted = True
                stopped = True
                self._executor.cancel(flight.run_id)
            else:
                awaiting = max(awaiting, _awaiting(flight))
            self._announce(flight)
        return Abandoned(branch=branch, left=left, stopped=stopped, awaiting=awaiting)

    async def _advance(
        self, plan: Plan, step: Step, *, actor: str, force: bool = False
    ) -> StepOutcome:
        here = self._store.index.slice_versions(plan.branch_id)
        selected = here.get(step.uid)
        if selected is None or selected.version_id != step.version.version_id:
            return "abandoned"
        inputs, missing = resolve_inputs(
            self._store.index, plan.branch_id, step.version, here
        )
        if missing:
            raise InputUnavailable(
                f"`{step.slug}` needs {_names(missing)}, which nothing on "
                f"`{plan.branch}` produces"
            )
        hashes = {name: bound.content_hash for name, bound in inputs.items()}
        key = memo.key_for(self._store.index, step.version, hashes)
        if not force and not step.must_execute:
            if current(self._store, plan.branch_id, step, key):
                return "pruned"
            hit = memo.lookup(
                self._store,
                key,
                branch_id=plan.branch_id,
                require_values=step.needs_values,
            )
            if hit is not None:
                self._record_hit(plan, step, key, hit.mat_id, actor=actor)
                return "cached"
        return await self._execute(plan, step, key, inputs, actor=actor, force=force)

    async def _execute(
        self,
        plan: Plan,
        step: Step,
        key: str,
        inputs: dict[str, Bound],
        *,
        actor: str,
        force: bool,
    ) -> StepOutcome:
        flight = next(
            (
                candidate
                for candidate in self._flights.values()
                if candidate.key == key
                and (not force or candidate.origin == plan.branch)
            ),
            None,
        )
        if flight is not None:
            joined = await self._join(flight, plan, step, key, actor=actor)
            if joined is not None:
                return joined
        return await self._start(plan, step, key, inputs, actor=actor)

    async def _join(
        self, flight: _Flight, plan: Plan, step: Step, key: str, *, actor: str
    ) -> StepOutcome | None:
        """Await someone else's run. None means it turned out unusable here."""
        waiter = self._wait_on(flight, plan.branch)
        result = await waiter.future
        if waiter.abandoned:
            return "abandoned"
        if not self._still_selected(plan, step):
            return "abandoned"
        if result is None or result.state != "succeeded" or flight.mat_id is None:
            return None
        if result.external:
            return None
        if result.identity_dependent and plan.branch != flight.origin:
            # Only knowable once it has run: the branch that asked for it under
            # its own name has to run it under its own name.
            return None
        self._record_hit(plan, step, key, flight.mat_id, actor=actor)
        return "cached"

    async def _start(
        self,
        plan: Plan,
        step: Step,
        key: str,
        inputs: dict[str, Bound],
        *,
        actor: str,
    ) -> StepOutcome:
        flight = _Flight(key=key, run_id=new_ulid(), origin=plan.branch, slug=step.slug)
        self._flights[flight.run_id] = flight
        waiter = self._wait_on(flight, plan.branch)
        # The run is the queue's, not the caller's: the caller may walk away
        # while other branches are still awaiting the same result.
        flight.task = asyncio.create_task(
            self._drive(flight, plan, step, inputs, actor=actor)
        )
        result = await waiter.future
        if waiter.abandoned:
            return "abandoned"
        if result is None or result.state == "cancelled":
            return "abandoned"
        return "executed" if result.state == "succeeded" else "failed"

    async def _drive(
        self,
        flight: _Flight,
        plan: Plan,
        step: Step,
        inputs: dict[str, Bound],
        *,
        actor: str,
    ) -> None:
        result: RunResult | None = None
        error: BaseException | None = None
        try:
            await self._acquire(plan.branch)
            try:
                if (
                    not flight.preempted
                    and flight.waiters
                    and self._still_selected(plan, step)
                ):
                    result = await self._run(flight, plan, step, inputs, actor=actor)
            finally:
                self._release()
        except BaseException as failure:  # noqa: B036 - relayed to every waiter
            error = failure
        if self._flights.get(flight.run_id) is flight:
            del self._flights[flight.run_id]
        self._settle(flight, result, error)

    def _still_selected(self, plan: Plan, step: Step) -> bool:
        selected = self._store.index.slice_versions(plan.branch_id).get(step.uid)
        return selected is not None and selected.version_id == step.version.version_id

    async def _run(
        self,
        flight: _Flight,
        plan: Plan,
        step: Step,
        inputs: dict[str, Bound],
        *,
        actor: str,
    ) -> RunResult:
        request = self._request(flight.run_id, plan, step, inputs)
        # Read before the run, not after it: an install landing mid-run moves
        # the lockfile, and the result still came out of the modules the kernel
        # had already imported.
        env_lock_hash = self._store.index.env_lock_hash()
        self._store.index.pin_values(
            flight.run_id,
            [bound.value_ref for bound in inputs.values() if bound.value_ref],
        )
        try:
            result = await self._executor.run(request)
            flight.mat_id = self._record_run(
                plan,
                step,
                flight,
                result,
                inputs,
                request.step,
                env_lock_hash=env_lock_hash,
                actor=actor,
            )
        finally:
            self._store.index.release_values(flight.run_id)
        return result

    def _request(
        self, run_id: str, plan: Plan, step: Step, inputs: dict[str, Bound]
    ) -> RunRequest:
        return RunRequest(
            run_id=run_id,
            flow=self._store.manifest.name,
            flow_id=self._store.manifest.flow_id,
            flow_path=str(self._store.flow_dir.resolve()),
            branch=plan.branch,
            step=self._store.next_step,
            uid=step.uid,
            slug=step.slug,
            version_id=step.version.version_id,
            source=self._store.objects.get(step.version.bound_source_ref).decode(
                "utf-8"
            ),
            produces=dict(step.version.manifest.produces),
            params=dict(step.version.manifest.params),
            inputs=dict(inputs),
        )

    def _record_run(
        self,
        plan: Plan,
        step: Step,
        flight: _Flight,
        result: RunResult,
        inputs: Mapping[str, Bound],
        started_step: int,
        *,
        env_lock_hash: str | None,
        actor: str,
    ) -> str:
        """Journal the materialization, pinning its bytes across the window
        between the kernel writing them and the transaction referencing them."""
        mat_id = new_ulid()
        self._store.index.pin_values(
            flight.run_id,
            [
                record.value_ref
                for record in result.outputs.values()
                if record.value_ref
            ],
        )
        outputs = _recorded_outputs(
            step,
            result,
            group=self._store.manifest.name,
            branch=plan.branch,
        )
        self._store.commit(
            [
                RunRecorded(
                    mat_id=mat_id,
                    uid=step.uid,
                    version_id=step.version.version_id,
                    branch_id=plan.branch_id,
                    memo_key=flight.key,
                    state=result.state,
                    inputs={
                        name: InputRef(
                            uid=bound.uid,
                            output=bound.output,
                            content_hash=bound.content_hash,
                            mat_id=bound.mat_id,
                        )
                        for name, bound in inputs.items()
                    },
                    outputs=outputs,
                    identity_dependent=result.identity_dependent,
                    external=result.external,
                    env_lock_hash=env_lock_hash,
                    cost_seconds=result.cost_seconds,
                    log_ref=result.log_ref,
                    experiment_id=result.experiment_id,
                    experiment_store=result.experiment_store,
                    sdk_version_warning=result.sdk_version_warning,
                    started_step=started_step,
                    finished_step=self._store.next_step,
                )
            ],
            intent=_run_intent(step.slug, result.state),
            actor=actor,
            branch=plan.branch_id,
        )
        if result.experiment_close_error is not None:
            self._record_unclosed_experiment(plan, step, result.experiment_close_error)
        return mat_id

    def _record_unclosed_experiment(
        self, plan: Plan, step: Step, sentence: str
    ) -> None:
        self._store.commit(
            [
                CellNoted(
                    uid=step.uid,
                    kind="experiment_unclosed",
                    sentence=sentence,
                    version_id=step.version.version_id,
                )
            ],
            intent=sentence,
            actor="system",
            branch=plan.branch_id,
        )

    def _record_hit(
        self, plan: Plan, step: Step, key: str, mat_id: str, *, actor: str
    ) -> None:
        """A hit is journaled and moves the baseline — it is not a 0-second run."""
        self._store.commit(
            [
                MemoHit(
                    branch_id=plan.branch_id,
                    uid=step.uid,
                    version_id=step.version.version_id,
                    memo_key=key,
                    mat_id=mat_id,
                )
            ],
            intent=f"reused a cached {step.slug}",
            actor=actor,
            branch=plan.branch_id,
        )

    def _wait_on(self, flight: _Flight, branch: str) -> _Waiter:
        waiter = _Waiter(
            branch=branch, future=asyncio.get_running_loop().create_future()
        )
        flight.waiters.append(waiter)
        self._announce(flight)
        return waiter

    def _announce(self, flight: _Flight) -> None:
        """Who is awaiting this run, as it changes.

        A run's lifecycle is not journaled, and the awaiter set moves between
        its start and its end — a fork joining, a branch leaving — so a surface
        that only heard `started` would word its stop button on the count at
        the moment nobody else had arrived yet.
        """
        if self._on_event is None:
            return
        self._on_event(
            "awaiting",
            {
                "run_id": flight.run_id,
                "slug": flight.slug,
                "awaiting": _awaiting(flight),
            },
        )

    def _settle(
        self, flight: _Flight, result: RunResult | None, error: BaseException | None
    ) -> None:
        for waiter in flight.waiters:
            if waiter.future.done():
                continue
            if error is not None:
                waiter.future.set_exception(error)
            else:
                waiter.future.set_result(result)

    async def _acquire(self, branch: str) -> None:
        if not self._busy:
            self._busy = True
            return
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._gate.append((branch, future))
        await future

    def _release(self) -> None:
        self._gate = [entry for entry in self._gate if not entry[1].done()]
        if not self._gate:
            self._busy = False
            return
        position = next(
            (
                index
                for index, (branch, _) in enumerate(self._gate)
                if branch == self._active
            ),
            0,
        )
        _, future = self._gate.pop(position)
        future.set_result(None)


def _awaiting(flight: _Flight) -> int:
    """Distinct branches awaiting this run — a branch counts once, not per ask."""
    return len({waiter.branch for waiter in flight.waiters if not waiter.abandoned})


def _validate_experiment_outputs(plan: Plan) -> None:
    for step in plan.steps:
        outputs = [
            name
            for name, spec in step.version.manifest.produces.items()
            if spec.type == "experiment"
        ]
        if len(outputs) > 1:
            raise FlowError(
                f"`{step.slug}` declares {len(outputs)} `experiment` outputs; "
                "a cell must declare exactly one `experiment` output"
            )


def _recorded_outputs(
    step: Step,
    result: RunResult,
    *,
    group: str,
    branch: str,
) -> dict[str, OutputRecord]:
    records = dict(result.outputs)
    if result.experiment_id is None or result.experiment_store is None:
        return records
    tracker_ref = TrackerRef(
        experiment_id=result.experiment_id,
        group=group,
        store=result.experiment_store,
        tags=[branch, step.slug],
    )
    for name, spec in step.version.manifest.produces.items():
        if spec.type == "experiment" and name in records:
            records[name] = records[name].model_copy(
                update={"tracker_ref": tracker_ref}
            )
    return records


def _run_intent(slug: str, state: MaterializationState) -> str:
    if state == "succeeded":
        return f"ran {slug}"
    if state == "cancelled":
        return f"cancelled {slug}"
    return f"{slug} failed"


def _names(names: tuple[str, ...]) -> str:
    return ", ".join(f"`{name}`" for name in names)
