"""The filesystem watcher: latency, never truth — and scoped to the flow.

Events are how the UI learns about an agent's edit in a second rather than at
the next verb. Nothing depends on them arriving: every version-resolving op
reconciles first, so a dropped event, an editor that writes through a temp
file, or a platform whose notifications simply do not fire all cost the same
thing — a delay — and never a wrong version.

Watching belongs to the flow, not to the workspace. A workspace-wide watch that
woke every flow was wrong twice over: most of what changes under a workspace
cannot affect a given flow, and a flow opened by its own absolute path from
above the launch directory got no watching at all. So the scope is a session's,
and it follows the session — held while the flow is open, dropped when it
closes.

**What one flow session watches.** With `F` its flow directory and `W` the
workspace it runs under (its own, which for an outside flow is not the launch
directory):

- `F/cells/*.py` — its own cells, direct children only, because that is exactly
  what acceptance globs. A `.py` deeper under `cells/` is not a cell and is not
  shared code either, so nothing watches it.
- Every other `.py` under `W`, excluding environments, build output, ignored
  paths, caches and stores — its shared code, which is precisely the domain
  `scan_workspace` hashes. Any flow's `cells/` is cut out of it, so a
  *neighbour* flow's cell file is not this flow's anything.

Nothing else. In particular **data files are not watched**, whoever declares or
reads them: the store never versions them, a run that reaches one is marked
`external` and never memoized, and re-running is what the next verb does anyway
— so an event over one has no invalidation to cause. A cell can only reach an
external file through `ctx.workspace_dir` or `ctx.flow_dir`, and both of those
directories are already inside the scheduled tree; what the classification
decides is that a `.csv` under them wakes nobody.

`F` is always under `W`, so one recursive watch per workspace covers both
halves, and several flows in one workspace share it — the routing is per
session regardless. Observer callbacks arrive on watchdog's own thread and do
nothing but post the path to the daemon's loop. All store work stays on that one
thread, which is what makes a reconciliation atomic against the API calls it
races.
"""

import asyncio
import contextlib
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from lumlflow.flow.dsl.accept import CELL_SUFFIX
from lumlflow.flow.dsl.tree import WorkspaceExclusions
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, FLOW_SUFFIX

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import Hub

DEBOUNCE_S = 2.0

_JOIN_TIMEOUT_S = 2.0
# `<flow>/cells/<name>.py` — the depth acceptance globs at, and the only depth
# a cell file lives at.
_CELL_DEPTH = 3

Watched = Literal["cell", "code"]


@dataclass(frozen=True)
class WatchSet:
    """One flow session's plane: its own cells, and its workspace's shared code.

    A value, not a subscription — what a path *means to this flow*, which is the
    question both the observer's routing and any test about scoping ask.
    """

    flow_dir: Path
    workspace_dir: Path

    @property
    def root(self) -> Path:
        """The one directory an observer has to be scheduled on for this flow.

        The flow directory is always inside it: a flow the launch directory does
        not contain resolves its own workspace by walking up from its parent,
        and that parent holds it.
        """
        return self.workspace_dir

    def classify(self, path: Path) -> Watched | None:
        """Whose plane this path is on: this flow's cells, its shared code, or
        nothing this session watches.

        Classification is by directory, never by shape: `cells/` holds cells, a
        stray module inside a flow directory is shared code like any other, and
        a neighbour flow's cell file is neither.
        """
        if path.suffix != CELL_SUFFIX:
            return None
        try:
            relative = path.resolve().relative_to(self.workspace_dir)
        except (ValueError, OSError):
            return None
        parts = relative.parts
        for depth, part in enumerate(parts):
            if not part.endswith(FLOW_SUFFIX):
                continue
            if parts[depth + 1 : depth + 2] != (CELLS_DIRNAME,):
                break
            flow = self.workspace_dir.joinpath(*parts[: depth + 1])
            mine = flow == self.flow_dir and len(parts) == depth + _CELL_DEPTH
            return "cell" if mine else None
        if WorkspaceExclusions(self.workspace_dir).matches(path):
            return None
        return "code"


class Watches:
    """The directories the open sessions want watched, refcounted.

    Two flows in one workspace share its watch. Scheduling the same tree twice
    would take a second inotify registration per subdirectory and deliver every
    event twice for nothing — the routing is per session either way, so the
    duplicate buys no precision and costs a real kernel resource on the trees
    that are large enough for it to matter.

    The hub holds this and moves it; a watcher, when there is one, hangs its
    scheduling off the two hooks. A daemon with no watcher — every test that
    drives the API directly — moves the same counts and schedules nothing.
    """

    def __init__(self) -> None:
        self._held: Counter[Path] = Counter()
        self.observe: Callable[[Path], None] | None = None
        self.forget: Callable[[Path], None] | None = None

    def roots(self) -> list[Path]:
        return sorted(self._held)

    def hold(self, root: Path) -> None:
        self._held[root] += 1
        if self._held[root] == 1 and self.observe is not None:
            self.observe(root)

    def release(self, root: Path) -> None:
        held = self._held[root]
        if not held:
            return
        if held > 1:
            self._held[root] = held - 1
            return
        del self._held[root]
        if self.forget is not None:
            self.forget(root)


class Watcher:
    """One observer for the daemon, scheduled on whatever the open flows need.

    What it wakes is a session that is already open. Opening one because a file
    under it moved would spawn a store, a cold reconciliation and a kernel for a
    flow nobody asked about — and would buy nothing, since the cold-start tier
    is exactly what an unwatched directory's edits land as when someone does
    open it.
    """

    def __init__(self, hub: "Hub", *, debounce_s: float = DEBOUNCE_S) -> None:
        self.hub = hub
        self.debounce_s = debounce_s
        self._loop: asyncio.AbstractEventLoop | None = None
        self._observer: Any = None
        self._scheduled: dict[Path, Any] = {}
        self._woken: set[Path] = set()
        self._deadline: float | None = None
        self._timer: asyncio.Future[None] | None = None

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._observer = Observer()
        self._observer.start()
        self.hub.watches.observe = self._schedule
        self.hub.watches.forget = self._unschedule
        # Sessions opened before there was a watcher are already counted.
        for root in self.hub.watches.roots():
            self._schedule(root)

    async def stop(self) -> None:
        self.hub.watches.observe = None
        self.hub.watches.forget = None
        self._scheduled.clear()
        if self._observer is not None:
            self._observer.stop()
            await asyncio.to_thread(self._observer.join, _JOIN_TIMEOUT_S)
            self._observer = None
        timer, self._timer = self._timer, None
        self._deadline = None
        if timer is not None:
            timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timer

    def notice(self, path: Path) -> None:
        """Record a changed path against whichever sessions it belongs to, and
        arm the debounce. Loop thread only."""
        woken = {
            session.ref.path
            for session in self.hub.opened()
            if session.watch.classify(path) is not None
        }
        if not woken:
            return
        self._woken |= woken
        self._arm()

    async def flush(self) -> None:
        """Reconcile every woken session, as one burst.

        The quiet point is what groups an edit burst into one transaction.
        Every other door into reconciliation — a verb's quiesce, the end of an
        agent session — is a boundary that simply arrives sooner, and the flush
        that follows finds the files already level.
        """
        woken, self._woken = self._woken, set()
        for path in sorted(woken):
            session = self.hub.attached(path)
            # Closed between the event and the quiet point: nothing to wake, and
            # whatever moved is the next open's cold start to take up.
            if session is not None:
                await self.hub.quiesce(session, tier="live")

    def _schedule(self, root: Path) -> None:
        observer = self._observer
        if observer is None or root in self._scheduled:
            return
        try:
            self._scheduled[root] = observer.schedule(
                _Handler(self._post), str(root), recursive=True
            )
        except OSError as unwatchable:
            # Watching is a latency optimization; a tree the platform will not
            # notify on still reconciles on every verb.
            logger.warning("not watching %s: %s", root, unwatchable)

    def _unschedule(self, root: Path) -> None:
        watch = self._scheduled.pop(root, None)
        if watch is None or self._observer is None:
            return
        with contextlib.suppress(KeyError, OSError):
            self._observer.unschedule(watch)

    def _arm(self) -> None:
        """Push the quiet-point out, and start waiting for it if nobody is.

        The deadline moves rather than the task being replaced: cancelling a
        timer that had already begun flushing would tear a reconciliation in
        half, and a burst is exactly when the next event lands during one.
        """
        loop = asyncio.get_running_loop()
        self._deadline = loop.time() + self.debounce_s
        if self._timer is None or self._timer.done():
            self._timer = asyncio.ensure_future(self._after_quiet())

    async def _after_quiet(self) -> None:
        loop = asyncio.get_running_loop()
        while self._deadline is not None:
            while (remaining := self._deadline - loop.time()) > 0:
                await asyncio.sleep(remaining)
            self._deadline = None
            await self.flush()

    def _post(self, path: str) -> None:
        """Observer thread → loop thread. The only thread hop in the daemon."""
        loop = self._loop
        if loop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self.notice, Path(path))


class _Handler(FileSystemEventHandler):
    def __init__(self, post: Callable[[str], None]) -> None:
        self._post = post

    def on_any_event(self, event: FileSystemEvent) -> None:
        # A move is two facts: the name that left and the name that arrived.
        for path in (event.src_path, getattr(event, "dest_path", None)):
            if path:
                self._post(str(path))
