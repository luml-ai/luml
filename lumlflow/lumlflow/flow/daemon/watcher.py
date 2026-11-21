import asyncio
import contextlib
import logging
import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileClosedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch
from watchdog.utils import UnsupportedLibcError, platform

from lumlflow.flow.dsl.accept import CELL_SUFFIX
from lumlflow.flow.dsl.tree import WorkspaceExclusions
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, FLOW_SUFFIX

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import Hub

DEBOUNCE_S = 2.0

_JOIN_TIMEOUT_S = 2.0
_CELL_DEPTH = 3

Watched = Literal["cell", "code"]

# Only what can change a scan's result. Opens and reads are left out: a scan
# reads every file it hashes, so reacting to reads would wake the next scan.
_CHANGES: list[type[FileSystemEvent]] = [
    FileCreatedEvent,
    DirCreatedEvent,
    FileModifiedEvent,
    DirModifiedEvent,
    FileClosedEvent,
    FileMovedEvent,
    DirMovedEvent,
    FileDeletedEvent,
    DirDeletedEvent,
]


@dataclass(frozen=True)
class WatchSet:
    flow_dir: Path
    workspace_dir: Path

    @property
    def root(self) -> Path:
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
    The hooks only queue the work and hand back its future, in order, so
    `settled` waits for every hold and release made so far.
    """

    def __init__(self) -> None:
        self._held: Counter[Path] = Counter()
        self.observe: Callable[[Path], Future[None] | None] | None = None
        self.forget: Callable[[Path], Future[None] | None] | None = None
        self._pending: Future[None] | None = None

    def roots(self) -> list[Path]:
        return sorted(self._held)

    def hold(self, root: Path) -> None:
        self._held[root] += 1
        if self._held[root] == 1 and self.observe is not None:
            self._pending = self.observe(root)

    def release(self, root: Path) -> None:
        held = self._held[root]
        if not held:
            return
        if held > 1:
            self._held[root] = held - 1
            return
        del self._held[root]
        if self.forget is not None:
            self._pending = self.forget(root)

    def attach(
        self,
        observe: Callable[[Path], Future[None] | None],
        forget: Callable[[Path], Future[None] | None],
    ) -> None:
        self.observe, self.forget = observe, forget
        for root in self.roots():
            self._pending = observe(root)

    async def settled(self) -> None:
        # `wait`, not `await`: a stopping watcher cancels what it had queued,
        # and that must not read as this caller being cancelled.
        if self._pending is not None:
            await asyncio.wait([asyncio.wrap_future(self._pending)])


class Watcher:
    def __init__(self, hub: "Hub", *, debounce_s: float = DEBOUNCE_S) -> None:
        self.hub = hub
        self.debounce_s = debounce_s
        self._loop: asyncio.AbstractEventLoop | None = None
        # Placing watches walks the tree, so the placement runs on `_placer`'s
        # one thread, in the order it was asked for, and nowhere else.
        self._placement: _Placement | None = None
        self._placer: ThreadPoolExecutor | None = None
        self._stopping = threading.Event()
        self._woken: set[Path] = set()
        self._deadline: float | None = None
        self._timer: asyncio.Future[None] | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stopping.clear()
        self._placement = _placement(
            post=self._post,
            wake=self._post_wake,
            submit=self._submit,
            stopping=self._stopping,
        )
        self._placer = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="lumlflow-watch"
        )
        self.hub.watches.attach(self._schedule, self._unschedule)
        await self.hub.watches.settled()

    async def stop(self) -> None:
        self.hub.watches.observe = None
        self.hub.watches.forget = None
        self._stopping.set()
        placer, self._placer = self._placer, None
        if placer is not None:
            await asyncio.to_thread(
                partial(placer.shutdown, wait=True, cancel_futures=True)
            )
        placement, self._placement = self._placement, None
        if placement is not None:
            await asyncio.to_thread(placement.stop)
        timer, self._timer = self._timer, None
        self._deadline = None
        if timer is not None:
            timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timer

    def notice(self, path: Path) -> None:
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
        woken, self._woken = self._woken, set()
        for path in sorted(woken):
            session = self.hub.attached(path)
            if session is None:
                continue
            # One flow's broken file plane must not cost the rest of the batch
            # their wake: it is already swapped out and nothing re-delivers it.
            try:
                await self.hub.quiesce(session, tier="live")
            except Exception:
                logger.exception("reconciling %s after a file event failed", path)

    def _schedule(self, root: Path) -> Future[None] | None:
        if self._placer is None or self._placement is None:
            return None
        return self._placer.submit(self._placement.schedule, root)

    def _unschedule(self, root: Path) -> Future[None] | None:
        if self._placer is None or self._placement is None:
            return None
        return self._placer.submit(self._placement.unschedule, root)

    def _submit(self, work: Callable[[], None]) -> None:
        """Any thread → the placing thread, for the watches' own upkeep."""
        placer = self._placer
        if placer is not None:
            with contextlib.suppress(RuntimeError):
                placer.submit(work)

    def _wake(self, root: Path) -> None:
        woken = {
            session.ref.path
            for session in self.hub.opened()
            if session.watch.root == root
        }
        if woken:
            self._woken |= woken
            self._arm()

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
        """Watching threads → loop thread: the only way an event reaches it."""
        loop = self._loop
        if loop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self.notice, Path(path))

    def _post_wake(self, root: Path) -> None:
        loop = self._loop
        if loop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._wake, root)


class _Placement(Protocol):
    def schedule(self, root: Path) -> None: ...

    def unschedule(self, root: Path) -> None: ...

    def stop(self) -> None: ...


class _RecursiveWatches:
    """Where one recursive watch is cheap and one per directory is not
    (FSEvents, ReadDirectoryChangesW): the whole tree, with `classify`
    dropping what the scan prunes."""

    def __init__(self, post: Callable[[str], None]) -> None:
        self._post = post
        self._observer = Observer()
        self._observer.start()
        self._scheduled: dict[Path, ObservedWatch] = {}

    def schedule(self, root: Path) -> None:
        if root in self._scheduled:
            return
        try:
            self._scheduled[root] = self._observer.schedule(
                _Handler(self._post), str(root), recursive=True, event_filter=_CHANGES
            )
        except OSError as unwatchable:
            logger.warning("not watching %s: %s", root, unwatchable)

    def unschedule(self, root: Path) -> None:
        watch = self._scheduled.pop(root, None)
        if watch is None:
            return
        with contextlib.suppress(KeyError, OSError):
            self._observer.unschedule(watch)

    def stop(self) -> None:
        self._scheduled.clear()
        self._observer.stop()
        self._observer.join(_JOIN_TIMEOUT_S)


class _Handler(FileSystemEventHandler):
    def __init__(self, post: Callable[[str], None]) -> None:
        self._post = post

    def on_any_event(self, event: FileSystemEvent) -> None:
        for path in (event.src_path, getattr(event, "dest_path", None)):
            if path:
                self._post(str(path))


def _placement(
    *,
    post: Callable[[str], None],
    wake: Callable[[Path], None],
    submit: Callable[[Callable[[], None]], None],
    stopping: threading.Event,
) -> _Placement:
    if platform.is_linux():
        with contextlib.suppress(UnsupportedLibcError):
            from lumlflow.flow.daemon.inotify import InotifyTrees

            return InotifyTrees(post=post, wake=wake, submit=submit, stopping=stopping)
    return _RecursiveWatches(post)
