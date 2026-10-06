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
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class Abandoned:
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
    key: str
    run_id: str
    origin: str
    asked_step: int
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
        return self._busy

    def focus(self, branch: str | None) -> None:
        self._active = branch

    async def submit(
        self, target: str, *, branch: str, actor: str = "user", force: bool = False
    ) -> RunOutcome:
        plan = self._planner.plan(target, branch=branch)
        return await self.submit_plan(plan, actor=actor, force=force)

    def check(self, plan: Plan) -> None:
        _validate_experiment_outputs(plan)
        unresolvable = self._planner.unresolvable(plan)
        if unresolvable is not None:
            raise InputUnavailable(unresolvable)

    async def submit_plan(
        self,
        plan: Plan,
        *,
        actor: str = "user",
        force: bool = False,
        keep_going: bool = False,
    ) -> RunOutcome:
        """With `keep_going`, a failure skips only the steps downstream of it."""
        _validate_experiment_outputs(plan)
        done: dict[str, list[str]] = {"executed": [], "cached": [], "pruned": []}
        failures: list[str] = []
        blocked: set[str] = set()
        abandoned = False
        for step in plan.steps:
            if blocked.intersection(step.producers):
                blocked.add(step.uid)
                continue
            outcome = await self._advance(plan, step, actor=actor, force=force)
            if outcome == "abandoned":
                abandoned = True
                break
            if outcome == "failed":
                failures.append(step.slug)
                blocked.add(step.uid)
                if keep_going:
                    continue
                break
            done[outcome].append(step.slug)
        return RunOutcome(
            branch=plan.branch,
            target=plan.target,
            executed=tuple(done["executed"]),
            cached=tuple(done["cached"]),
            pruned=tuple(done["pruned"]),
            failed=failures[0] if failures else None,
            abandoned=abandoned,
            failures=tuple(failures),
        )

    def abandon(self, branch: str) -> Abandoned:
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
        waiter = self._wait_on(flight, plan.branch)
        result = await waiter.future
        if waiter.abandoned:
            return "abandoned"
        if not self._still_selected(plan, step):
            return "abandoned"
        if result is None or result.state != "succeeded" or flight.mat_id is None:
            return None
        if _external(step, result):
            return None
        if result.identity_dependent and plan.branch != flight.origin:
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
        flight = _Flight(
            key=key,
            run_id=new_ulid(),
            origin=plan.branch,
            asked_step=self._store.next_step,
            slug=step.slug,
        )
        self._flights[flight.run_id] = flight
        waiter = self._wait_on(flight, plan.branch)
        # The run is the queue's, not the caller's: the caller may walk away
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
        ran = False
        try:
            await self._acquire(plan.branch)
            try:
                if (
                    not flight.preempted
                    and flight.waiters
                    and self._still_selected(plan, step)
                ):
                    ran = True
                    result = await self._run(flight, plan, step, inputs, actor=actor)
            finally:
                self._release()
        except BaseException as failure:  # noqa: B036 - relayed to every waiter
            error = failure
        if self._flights.get(flight.run_id) is flight:
            del self._flights[flight.run_id]
        if not ran:
            # The kernel never saw this run, so nothing else ends its queued state
            self._emit_awaiting(flight, 0)
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
    ) -> RunResult | None:
        request = self._request(flight.run_id, plan, step, inputs)
        # Read before the run, not after it: an install landing mid-run moves
        env_lock_hash = self._store.index.env_lock_hash()
        self._store.index.pin_values(
            flight.run_id,
            [bound.value_ref for bound in inputs.values() if bound.value_ref],
        )
        try:
            result = await self._executor.run(request)
            if self._rewound_since(plan.branch_id, flight.asked_step):
                # Even a cancelled record is a change, and would move the lane
                return None
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

    def _rewound_since(self, branch_id: str, step: int) -> bool:
        branch = self._store.index.branch_by_id(branch_id)
        return (
            branch is not None
            and branch.rewound_step is not None
            and branch.rewound_step >= step
        )

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
                    external=_external(step, result),
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
        self._emit_awaiting(flight, _awaiting(flight))

    def _emit_awaiting(self, flight: _Flight, awaiting: int) -> None:
        if self._on_event is None:
            return
        self._on_event(
            "awaiting",
            {"run_id": flight.run_id, "slug": flight.slug, "awaiting": awaiting},
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


def _external(step: Step, result: RunResult) -> bool:
    return result.external or step.version.manifest.volatility == "external"


def _awaiting(flight: _Flight) -> int:
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
