import asyncio
import contextlib
import logging
import threading
from collections import Counter, deque
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from watchdog.events import (
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MOVED,
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
    from lumlflow.flow.daemon.hub import FlowSession, Hub

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
    The hooks only queue the work and hand back its future, in order per
    root, so `settled` waits for every hold and release of a root made so far.
    """

    def __init__(self) -> None:
        self._held: Counter[Path] = Counter()
        self.observe: Callable[[Path], Future[None] | None] | None = None
        self.forget: Callable[[Path], Future[None] | None] | None = None
        self._pending: dict[Path, Future[None]] = {}

    def roots(self) -> list[Path]:
        return sorted(self._held)

    def hold(self, root: Path) -> None:
        self._forget_settled()
        self._held[root] += 1
        if self._held[root] == 1 and self.observe is not None:
            self._queued(root, self.observe(root))

    def release(self, root: Path) -> None:
        self._forget_settled()
        held = self._held[root]
        if not held:
            return
        if held > 1:
            self._held[root] = held - 1
            return
        del self._held[root]
        if self.forget is not None:
            self._queued(root, self.forget(root))

    def attach(
        self,
        observe: Callable[[Path], Future[None] | None],
        forget: Callable[[Path], Future[None] | None],
    ) -> None:
        self.observe, self.forget = observe, forget
        for root in self.roots():
            self._queued(root, observe(root))

    async def settled(self, root: Path | None = None) -> None:
        """Wait for `root`'s watch work queued so far, or every root's."""
        pending = (
            list(self._pending.values())
            if root is None
            else [self._pending[root]]
            if root in self._pending
            else []
        )
        # `wait`, not `await`: a stopping watcher cancels what it had queued,
        # and that must not read as this caller being cancelled. A job that
        # failed was logged where it ran; its error is read here only so the
        # wrapper does not log it a second time.
        if pending:
            waited = [asyncio.wrap_future(future) for future in pending]
            await asyncio.wait(waited)
            for future in waited:
                if not future.cancelled():
                    future.exception()
        self._forget_settled()

    def _queued(self, root: Path, future: Future[None] | None) -> None:
        if future is not None:
            self._pending[root] = future

    def _forget_settled(self) -> None:
        for root, future in list(self._pending.items()):
            if root not in self._held and future.done():
                del self._pending[root]


class Watcher:
    def __init__(self, hub: "Hub", *, debounce_s: float = DEBOUNCE_S) -> None:
        self.hub = hub
        self.debounce_s = debounce_s
        self._loop: asyncio.AbstractEventLoop | None = None
        # Placing watches walks the tree, so the placement runs on `_placer`'s
        # threads, each root's in the order it was asked for, and nowhere else.
        self._placement: _Placement | None = None
        self._placer: _RootQueues | None = None
        self._stopping = threading.Event()
        self._woken: set[Path] = set()
        self._deadline: float | None = None
        self._timer: asyncio.Future[None] | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stopping.clear()
        self._placement = _placement(
            post=self._post,
            vanished=self._post_vanished,
            wake=self._post_wake,
            submit=self._submit,
            stopping=self._stopping,
        )
        self._placer = _RootQueues()
        self.hub.watches.attach(self._schedule, self._unschedule)
        await self.hub.watches.settled()

    async def stop(self) -> None:
        self.hub.watches.observe = None
        self.hub.watches.forget = None
        self._stopping.set()
        placer, self._placer = self._placer, None
        if placer is not None:
            await asyncio.to_thread(placer.stop)
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

    def vanished(self, path: Path) -> None:
        """A path deleted or moved away. Where it was a directory, the files
        it held may raise no event of their own — ReadDirectoryChangesW does
        not even say it was a directory — so the flows whose last scan had
        files below it are woken for another."""
        woken = {
            session.ref.path
            for session in self.hub.opened()
            if session.ref.path not in self._woken and _tracked_below(session, path)
        }
        if woken:
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
        return self._placer.submit(root, partial(self._placement.schedule, root))

    def _unschedule(self, root: Path) -> Future[None] | None:
        if self._placer is None or self._placement is None:
            return None
        return self._placer.submit(root, partial(self._placement.unschedule, root))

    def _submit(self, root: Path, work: Callable[[], None]) -> None:
        """Any thread → `root`'s placing queue, for the watches' own upkeep."""
        placer = self._placer
        if placer is not None:
            placer.submit(root, work)

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

    def _post_vanished(self, path: str) -> None:
        loop = self._loop
        if loop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self.vanished, Path(path))

    def _post_wake(self, root: Path) -> None:
        loop = self._loop
        if loop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._wake, root)


class _RootQueues:
    """Watch work, one queue per root: a root's jobs run one at a time, in
    the order they were asked for, on a thread that lives while its queue has
    work. Roots do not wait for each other, so a long walk of one tree never
    holds up the watch an open of another is waiting for."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: dict[Path, deque[tuple[Callable[[], None], Future[None]]]] = {}
        self._threads: set[threading.Thread] = set()
        self._stopped = False

    def submit(self, root: Path, work: Callable[[], None]) -> Future[None]:
        done: Future[None] = Future()
        with self._lock:
            if self._stopped:
                done.cancel()
                return done
            queue = self._queues.get(root)
            if queue is not None:
                queue.append((work, done))
                return done
            self._queues[root] = deque([(work, done)])
            thread = threading.Thread(
                target=self._drain, args=(root,), name="lumlflow-watch", daemon=True
            )
            self._threads.add(thread)
            thread.start()
        return done

    def stop(self) -> None:
        """Cancel what is queued and wait for what is running, which the
        watcher's stop flag cuts short."""
        with self._lock:
            self._stopped = True
            for queue in self._queues.values():
                for _, done in queue:
                    done.cancel()
                queue.clear()
            threads = list(self._threads)
        for thread in threads:
            thread.join()

    def _drain(self, root: Path) -> None:
        while True:
            with self._lock:
                queue = self._queues[root]
                if not queue:
                    del self._queues[root]
                    self._threads.discard(threading.current_thread())
                    return
                work, done = queue.popleft()
            if not done.set_running_or_notify_cancel():
                continue
            try:
                work()
            except Exception as failed:
                logger.exception("watching %s failed", root)
                done.set_exception(failed)
            else:
                done.set_result(None)


class _Placement(Protocol):
    def schedule(self, root: Path) -> None: ...

    def unschedule(self, root: Path) -> None: ...

    def stop(self) -> None: ...


class _RecursiveWatches:
    """Where one recursive watch is cheap and one per directory is not
    (FSEvents, ReadDirectoryChangesW): the whole tree, with `classify`
    dropping what the scan prunes."""

    def __init__(
        self, post: Callable[[str], None], vanished: Callable[[str], None]
    ) -> None:
        self._post = post
        self._vanished = vanished
        self._observer = Observer()
        self._observer.start()
        self._scheduled: dict[Path, ObservedWatch] = {}

    def schedule(self, root: Path) -> None:
        if root in self._scheduled:
            return
        try:
            self._scheduled[root] = self._observer.schedule(
                _Handler(self._post, self._vanished),
                str(root),
                recursive=True,
                event_filter=_CHANGES,
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
    def __init__(
        self, post: Callable[[str], None], vanished: Callable[[str], None]
    ) -> None:
        self._post = post
        self._vanished = vanished

    def on_any_event(self, event: FileSystemEvent) -> None:
        for path in (event.src_path, getattr(event, "dest_path", None)):
            if path:
                self._post(str(path))
        # By event type, not class: a removed directory comes as a file
        # deletion on Windows. A cell file's own event already wakes its flow.
        source = str(event.src_path)
        if event.event_type in (EVENT_TYPE_DELETED, EVENT_TYPE_MOVED) and not (
            source.endswith(CELL_SUFFIX)
        ):
            self._vanished(source)


def _placement(
    *,
    post: Callable[[str], None],
    vanished: Callable[[str], None],
    wake: Callable[[Path], None],
    submit: Callable[[Path, Callable[[], None]], None],
    stopping: threading.Event,
) -> _Placement:
    if platform.is_linux():
        # The per-directory watches lean on watchdog internals that may move
        # within a major version; one recursive watch still sees every change.
        try:
            from lumlflow.flow.daemon.inotify import InotifyTrees

            return InotifyTrees(post=post, wake=wake, submit=submit, stopping=stopping)
        except (ImportError, AttributeError, UnsupportedLibcError) as unusable:
            logger.warning(
                "watching each workspace with one recursive watch, excluded "
                "directories included: per-directory watches are unavailable (%s)",
                unusable,
            )
    return _RecursiveWatches(post, vanished)


def _tracked_below(session: "FlowSession", path: Path) -> bool:
    # One set lookup: `rm -rf node_modules` on a recursive watch sends one
    # event per entry, and each lands here, on the loop.
    if not path.is_relative_to(session.workspace_dir):
        return False
    relative = path.relative_to(session.workspace_dir)
    return (relative.as_posix() if relative.parts else "") in session.tracked_dirs
