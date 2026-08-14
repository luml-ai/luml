"""A flow to schedule against: real cell files, real acceptance, a stub kernel.

Cells go through the acceptance pipeline rather than being faked into the
index, so bindings, `definition_hash`es and bound sources are the real ones the
scheduler keys on. Only the kernel is stubbed — the scheduler's contract is
about what it asks to run, not about what running means.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumlflow.flow.dsl.accept import Acceptance, AcceptedCell
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.scheduler import staleness
from lumlflow.flow.scheduler.planner import Planner, Preflight
from lumlflow.flow.scheduler.queue import RunOutcome, RunQueue, RunRequest, RunResult
from lumlflow.flow.scheduler.staleness import Verdict
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, FlowStore
from lumlflow.flow.store.models import OutputRecord


def write_cell(
    store: FlowStore,
    slug: str,
    *,
    consumes: dict[str, str] | None = None,
    produces: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    env_sensitive: bool = False,
    edit: str = "",
    docstring: str | None = None,
) -> Path:
    """Write `cells/<slug>.py`. `edit` is a body line that moves the hash."""
    path = store.flow_dir / CELLS_DIRNAME / f"{slug}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _source(
            slug,
            consumes=consumes or {},
            produces=produces if produces is not None else {"data": "asset"},
            params=params or {},
            env_sensitive=env_sensitive,
            edit=edit,
            docstring=docstring,
        ),
        encoding="utf-8",
    )
    return path


def accept_cell(
    store: FlowStore, slug: str, *, branch: str = MAIN_BRANCH
) -> AcceptedCell:
    acceptance = Acceptance(store)
    return acceptance.accept_path(acceptance.cell_path(slug), branch=branch)


def _source(
    slug: str,
    *,
    consumes: dict[str, str],
    produces: dict[str, Any],
    params: dict[str, Any],
    env_sensitive: bool,
    edit: str,
    docstring: str | None,
) -> str:
    name = "".join(part.title() for part in slug.split("_"))
    lines = [f"class {name}:", f'    """{docstring or slug}."""']
    if consumes:
        lines.append(f"    consumes = {consumes!r}")
    lines.append(f"    produces = {produces!r}")
    if params:
        lines.append(f"    params = {params!r}")
    if env_sensitive:
        lines.append("    env_sensitive = True")
    signature = ", ".join(["self", "ctx", *consumes])
    lines.append("")
    lines.append(f"    def materialize({signature}):")
    if edit:
        lines.append(f"        edit = {edit!r}")
    lines.append(f"        return {{{', '.join(f'{key!r}: 1' for key in produces)}}}")
    return "\n".join(lines) + "\n"


@dataclass
class StubExecutor:
    """A kernel that writes whatever it is told to and never imports anything.

    Output content defaults to a function of the cell's version and its inputs,
    the way a real cell's would. `content` pins an output against that — which
    is how early cutoff gets something to cut off.
    """

    store: FlowStore
    requests: list[RunRequest] = field(default_factory=list)
    content: dict[tuple[str, str], bytes] = field(default_factory=dict)
    costs: dict[str, float] = field(default_factory=dict)
    identity: set[str] = field(default_factory=set)
    external: set[str] = field(default_factory=set)
    failing: set[str] = field(default_factory=set)
    holding: set[str] = field(default_factory=set)
    cancelled: list[str] = field(default_factory=list)
    started: asyncio.Event = field(default_factory=asyncio.Event)
    _release: asyncio.Event = field(default_factory=asyncio.Event)
    _live: dict[str, asyncio.Event] = field(default_factory=dict)

    @property
    def slugs(self) -> list[str]:
        return [request.slug for request in self.requests]

    def release(self) -> None:
        self._release.set()

    def cancel(self, run_id: str) -> None:
        self.cancelled.append(run_id)
        stop = self._live.get(run_id)
        if stop is not None:
            stop.set()

    async def run(self, request: RunRequest) -> RunResult:
        self.requests.append(request)
        self.started.set()
        if request.slug in self.holding and not await self._wait(request.run_id):
            return RunResult(state="cancelled")
        cost = self.costs.get(request.slug, 0.1)
        if request.slug in self.failing:
            return RunResult(state="failed", cost_seconds=cost)
        return RunResult(
            state="succeeded",
            outputs=self._outputs(request),
            identity_dependent=request.slug in self.identity,
            external=request.slug in self.external,
            cost_seconds=cost,
        )

    async def _wait(self, run_id: str) -> bool:
        """Block until released or cancelled. False means cancelled."""
        stop = asyncio.Event()
        self._live[run_id] = stop
        waits = [
            asyncio.create_task(self._release.wait()),
            asyncio.create_task(stop.wait()),
        ]
        try:
            await asyncio.wait(waits, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in waits:
                task.cancel()
            self._live.pop(run_id, None)
        return not stop.is_set()

    def _outputs(self, request: RunRequest) -> dict[str, OutputRecord]:
        outputs = {}
        for name, spec in request.produces.items():
            body = self.content.get((request.slug, name), _derived(request, name))
            if not spec.persist:
                outputs[name] = OutputRecord(
                    content_hash=hash_bytes(f"{request.run_id}/{name}".encode()),
                    kind="frame",
                    kind_source="matcher",
                    size=0,
                    value_ref=None,
                    persisted=False,
                )
                continue
            outputs[name] = OutputRecord(
                content_hash=hash_bytes(body),
                kind="frame",
                kind_source="matcher",
                size=len(body),
                value_ref=self.store.values.put(body),
            )
        return outputs


def _derived(request: RunRequest, output: str) -> bytes:
    """What a cell that actually computed something would produce: a function of
    its own code and of everything it read."""
    consumed = sorted(
        f"{name}={bound.content_hash}" for name, bound in request.inputs.items()
    )
    return "/".join([request.version_id, output, *consumed]).encode()


async def settle(turns: int = 20) -> None:
    """Let every runnable coroutine reach its next await."""
    for _ in range(turns):
        await asyncio.sleep(0)


class Flow:
    """A store, a planner and a queue over one stub kernel."""

    def __init__(self, flow_dir: Path) -> None:
        self.store = FlowStore.init(flow_dir)
        self.executor = StubExecutor(self.store)
        self.planner = Planner(self.store)
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.queue = RunQueue(
            self.store,
            self.executor,
            planner=self.planner,
            on_event=lambda event, params: self.events.append((event, params)),
        )
        self._declared: dict[str, dict[str, Any]] = {}

    def add(
        self, slug: str, *, branch: str = MAIN_BRANCH, **declarations: Any
    ) -> AcceptedCell:
        self._declared[slug] = declarations
        write_cell(self.store, slug, **declarations)
        return accept_cell(self.store, slug, branch=branch)

    def note(
        self, slug: str, text: str = "A note.", *, branch: str = MAIN_BRANCH
    ) -> AcceptedCell:
        path = self.store.flow_dir / CELLS_DIRNAME / f"{slug}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        name = "".join(part.title() for part in slug.split("_"))
        path.write_text(f'class {name}:\n    """{text}"""\n', encoding="utf-8")
        return accept_cell(self.store, slug, branch=branch)

    def edit(
        self, slug: str, marker: str, *, branch: str = MAIN_BRANCH
    ) -> AcceptedCell:
        """Change the cell's behavior without changing what it declares."""
        write_cell(self.store, slug, edit=marker, **self._declared[slug])
        return accept_cell(self.store, slug, branch=branch)

    async def run(
        self, target: str, *, branch: str = MAIN_BRANCH, force: bool = False
    ) -> RunOutcome:
        return await self.queue.submit(target, branch=branch, force=force)

    def verdicts(self, branch: str = MAIN_BRANCH) -> dict[str, Verdict]:
        branch_id = self.store.branches.get(branch).branch_id
        return {
            verdict.slug: verdict
            for verdict in staleness.derive_all(self.store.index, branch_id).values()
        }

    def preflight(self, target: str, *, branch: str = MAIN_BRANCH) -> Preflight:
        return self.planner.preflight(target, branch=branch)

    def ops(self, kind: type) -> list[Any]:
        return [
            op
            for transaction in self.store.journal.replay()
            for op in transaction.ops
            if isinstance(op, kind)
        ]
