import asyncio
import contextlib
import logging
import os
import shutil
import threading
import time
from collections.abc import AsyncGenerator, Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

from lumlflow.flow.daemon import envs, files, queries, workspace
from lumlflow.flow.daemon import reconcile as reconciliation
from lumlflow.flow.daemon.kernel_proc import (
    KERNEL_DIRNAME,
    KERNEL_STATE_EVENT,
    KernelProcess,
)
from lumlflow.flow.daemon.projections import Worktree
from lumlflow.flow.daemon.reactive import Reactor
from lumlflow.flow.daemon.reconcile import AcceptedFile, Reconciliation, Tier
from lumlflow.flow.daemon.stream import StateName, Streams
from lumlflow.flow.daemon.watcher import Watches, WatchSet
from lumlflow.flow.daemon.workspace import FlowRef
from lumlflow.flow.dsl.accept import Acceptance
from lumlflow.flow.dsl.tree import WorkspaceTree, scan_workspace
from lumlflow.flow.errors import (
    FlowAlreadyExists,
    FlowAmbiguous,
    FlowError,
    FlowNotFound,
    FlowOpen,
)
from lumlflow.flow.scheduler.planner import Planner, TrackerState
from lumlflow.flow.scheduler.queue import RunQueue
from lumlflow.flow.store.flowstore import (
    FLOW_SUFFIX,
    INDEX_NAME,
    FlowStore,
    store_dir,
)
from lumlflow.flow.store.models import AgentEnd, TrackerRef
from lumlflow.tracker import TrackerProvider

logger = logging.getLogger(__name__)


class FlowSession:
    def __init__(
        self,
        ref: FlowRef,
        store: FlowStore,
        workspace_dir: Path,
        *,
        key: Path,
        tracker: TrackerProvider,
        streams: Streams | None = None,
    ) -> None:
        self.session_id = uuid4().hex
        self.ref = ref
        # The notebook on disk, whichever spelling `ref` reached it by.
        self.key = key
        self.store = store
        self.workspace_dir = workspace_dir
        self.tracker = tracker
        self.experiment_states: queries.ExperimentStates = queries.ExperimentStates(
            tracker
        )
        self.watch = WatchSet(flow_dir=ref.path, workspace_dir=workspace_dir)
        self.streams = streams
        self.touched: float = time.monotonic()
        self.touched_at: float = time.time()
        self.ran: float = self.touched
        if streams is not None:
            store.listeners.append(
                lambda entry: streams.transaction(ref.address, entry)
            )
        self.kernel = KernelProcess(
            flow_dir=ref.path,
            workspace_dir=workspace_dir,
            tracker_store=tracker.store_path,
            fail_experiment=tracker.fail_experiment,
            on_event=self._observed,
        )
        self.kernel_epoch_step: int = store.next_step
        self.planner = Planner(
            store,
            tracker_state=self._tracker_state,
            refresh_epoch=lambda: self.kernel_epoch_step,
        )
        self.queue = RunQueue(
            store,
            self.kernel,
            planner=self.planner,
            on_event=self._observed,
        )
        self.acceptance = Acceptance(store)
        self.reactor = Reactor(self)
        self.accepted_files: dict[str, AcceptedFile] = {}
        self.worktree = Worktree(store)
        # Every directory, root-relative ("" for the root), holding a file of
        # the last workspace tree applied: what a vanished path is checked
        # against without reading the tree back.
        self.tracked_dirs: frozenset[str] = frozenset()
        self._tracked_hash: str | None = None

    def _tracker_state(self, ref: TrackerRef) -> tuple[TrackerState, str]:
        state = queries.experiment_state(self, ref)
        return state.state, state.sentence

    @property
    def branch(self) -> str:
        return self.worktree.branch

    def touch(self) -> None:
        self.touched = time.monotonic()
        self.touched_at = time.time()

    def _observed(self, event: str, params: dict[str, Any]) -> None:
        # A kernel stopping is not work: counting it would restart the idle
        # clock the sweep that stopped it is reading.
        if event != KERNEL_STATE_EVENT:
            self.touch()
            self.ran = self.touched
        elif params.get("state") == "running":
            self.ran = time.monotonic()
        if self.streams is not None:
            self.streams.kernel(
                self.ref.address, event, params, step=self.store.next_step - 1
            )

    def track(self, tree: WorkspaceTree) -> None:
        if tree.tree_hash == self._tracked_hash:
            return
        parents = {name.rpartition("/")[0] for name in tree.files}
        tracked: set[str] = set()
        for parent in parents:
            while parent not in tracked:
                tracked.add(parent)
                if not parent:
                    break
                parent = parent.rpartition("/")[0]
        self.tracked_dirs = frozenset(tracked)
        self._tracked_hash = tree.tree_hash

    def reconcile(
        self, *, tier: Tier = "quiesce", actor: str | None = None
    ) -> Reconciliation:
        return reconciliation.reconcile(self, tier=tier, actor=actor)

    async def close(self) -> None:
        try:
            await self.reactor.stop()
            await self.kernel.stop()
        finally:
            self.store.close()


class Hub:
    def __init__(
        self,
        *,
        tracker: TrackerProvider | None = None,
        streams: Streams | None = None,
        drop_leases: Callable[[str], None] | None = None,
    ) -> None:
        if tracker is None:
            from lumlflow.settings import get_tracker

            tracker = get_tracker()
        self.tracker = tracker
        self._streams = streams
        self._drop_leases = drop_leases
        self.ui_directories: set[Path] = set()
        self._reserved: set[Path] = set()
        self._sessions: dict[Path, FlowSession] = {}
        self._known: dict[Path, FlowRef] = {}
        # Flows a listing came across: findable by name, but never opened.
        self._found: dict[Path, FlowRef] = {}
        self._loop: asyncio.AbstractEventLoop | None = _running_loop()
        self._closed: bool = False
        self._unsubscribe_tracker = tracker.on_experiment_deleted(
            self._experiment_deleted
        )
        self.watches = Watches()
        # A scan runs on `_scanner`'s threads and touches nothing but the disk;
        # what it found is applied here, on the loop, under the workspace's lock.
        self._scanner = ThreadPoolExecutor(thread_name_prefix="lumlflow-scan")
        self._scan_locks: dict[Path, asyncio.Lock] = {}
        self._stopping = threading.Event()
        self._scan_stops: set[threading.Event] = set()
        self._opening: dict[Path, asyncio.Event] = {}

    def flows(self) -> list[FlowRef]:
        return sorted(
            self._known.values(),
            key=lambda ref: str(ref.path),
        )

    def listing(
        self, root: Path, *, show_hidden: bool = False
    ) -> workspace.DirectoryListing:
        listing = workspace.list_directory(root, show_hidden=show_hidden)
        for ref in listing.flows:
            self._found[ref.path] = ref
        return listing

    def reported(self, root: Path) -> list[FlowRef]:
        """`root`'s own flows and the open ones beneath it, which a listing
        one level deep would otherwise drop from a report."""
        root = root.resolve()
        refs = {ref.path: ref for ref in self.listing(root).flows}
        for session in self._sessions.values():
            if session.ref.path.is_relative_to(root):
                refs.setdefault(session.ref.path, _relative_to(session.ref, root))
        return sorted(refs.values(), key=lambda ref: ref.relpath)

    def lookup(self, name: str, directory: Path) -> FlowRef | None:
        """The open-then-known flow `name` means among those inside
        `directory`, found without listing."""
        directory = directory.resolve()
        wanted = name.removesuffix(FLOW_SUFFIX).strip("/")
        if not wanted:
            return None
        opened = [session.ref for session in self._sessions.values()]
        opened_paths = {ref.path for ref in opened}
        known = [
            ref
            for path, ref in (self._found | self._known).items()
            if path not in opened_paths
        ]
        groups = [
            [
                ref
                for ref in refs
                if _answers(ref, wanted, directory)
                and _inside(ref.path, directory)
                and ref.path.is_dir()
            ]
            for refs in (opened, known)
        ]
        found = next((group for group in groups if group), [])
        if not found:
            return None
        if len(found) > 1:
            paths = ", ".join(f"`{ref.address}`" for ref in found)
            raise FlowAmbiguous(
                f"`{name}` names more than one flow: {paths}. use the path to say which"
            )
        return _relative_to(found[0], directory)

    def session(self, name: str | None = None) -> FlowSession:
        sessions = list(self._sessions.values())
        if name is None:
            if len(sessions) == 1:
                return sessions[0]
            raise FlowNotFound("no open flow was named")
        asked = Path(name)
        matches = [
            session
            for session in sessions
            if (
                (asked.is_absolute() and session.key == _session_key(asked))
                or name
                in {
                    session.ref.name,
                    session.ref.relpath,
                    f"{session.ref.name}{FLOW_SUFFIX}",
                }
            )
        ]
        if not matches:
            refs = [
                ref
                for ref in (self._found | self._known).values()
                if (
                    (asked.is_absolute() and ref.path == asked.resolve())
                    or name in {ref.name, ref.relpath, f"{ref.name}{FLOW_SUFFIX}"}
                )
                and _is_flow(ref.path)
            ]
            if len(refs) == 1:
                raise FlowNotFound(f"`{name}` is not open")
            if len(refs) > 1:
                # Not found rather than ambiguous: a caller with a directory to
                # resolve against can still tell these apart.
                paths = ", ".join(f"`{ref.path}`" for ref in refs)
                raise FlowNotFound(f"`{name}` names more than one known flow: {paths}")
        if not matches:
            raise FlowNotFound(f"no open flow called `{name}`")
        if len(matches) > 1:
            paths = ", ".join(f"`{session.ref.path}`" for session in matches)
            raise FlowError(f"`{name}` names more than one open flow: {paths}")
        return matches[0]

    async def open(self, ref: FlowRef, *, actor: str | None = None) -> FlowSession:
        self._remember_loop()
        # One session per notebook on disk, whichever spelling reached it: two
        # stores on the same journal would each hand out the same next step.
        key = _session_key(ref.path)
        self.check_available(ref.path, key)
        waited = False
        while (session := self._sessions.get(key)) is not None:
            session.touch()
            if (opening := self._opening.get(key)) is None:
                return session
            # Looked up again after: a first sync that did not finish takes
            # its session with it, and this open starts over.
            await opening.wait()
            waited = True
        # A delete waiting behind the same first open may have gone first.
        if waited and not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        store = (
            FlowStore.open(ref.path)
            if store_dir(ref.path).is_dir()
            else FlowStore.init(ref.path)
        )
        # Before the session serves anything: each lane gets its own copy of
        # its order, and flow.yaml starts mirroring the root lane's.
        store.ensure_lane_orders_fixed()
        session = self._session(ref, store, key)
        async with self._first_scan(session) as tree:
            reconciliation.sync_workspace_code(tree, [session])
            envs.sync(session.workspace_dir, [session])
            session.reconcile(tier="cold", actor=actor)
            session.reactor.arm()
        return session

    def attached(self, path: Path) -> FlowSession | None:
        return self._sessions.get(_session_key(path))

    def opened(
        self, *, here: bool = False, directory: Path | None = None
    ) -> list[FlowSession]:
        return [
            session
            for session in self._sessions.values()
            if not here or session.workspace_dir == directory
        ]

    def running(self) -> int:
        if self._streams is None:
            return 0
        return sum(
            len(self._streams.running(session.ref.address))
            for session in self._sessions.values()
        )

    def push_state(
        self,
        session: FlowSession,
        state: StateName,
        *,
        lane: str | None = None,
        cell: str | None = None,
    ) -> None:
        if self._streams is None:
            return
        self._streams.state(
            session.ref.address,
            state,
            step=session.store.next_step - 1,
            lane=lane,
            cell=cell,
        )

    async def quiesce(
        self,
        session: FlowSession,
        *,
        tier: Tier = "quiesce",
        actor: str | None = None,
    ) -> None:
        """The pre-op contract: no version resolves against a stale file plane.

        Shared code first — a helper edit changes every cell's behaviour hash,
        and the kernel has to forget the old module before the next
        materialization imports it, or the cache is poisoned with a value
        computed from code the hash no longer describes.
        """
        for _, failure in await self.quiesce_workspace(
            [session], tier=tier, actor=actor
        ):
            raise failure

    async def quiesce_workspace(
        self,
        sessions: list[FlowSession],
        *,
        tier: Tier = "quiesce",
        actor: str | None = None,
    ) -> list[tuple[FlowSession, Exception]]:
        """`quiesce` for several sessions of one workspace, off one scan of it.

        What a session's own reconciliation raises is handed back rather than
        raised, so it costs the others nothing; a failed scan is raised.
        """
        for session in sessions:
            if (opening := self._opening.get(session.key)) is not None:
                await opening.wait()
        live = [session for session in sessions if self._live(session)]
        if not live:
            return []
        workspace_dir = live[0].workspace_dir
        failures: list[tuple[FlowSession, Exception]] = []
        async with self._scan_lock(workspace_dir):
            tree = await self._scan(workspace_dir)
            for session in live:
                # Closed while the scan ran: its store is no longer there.
                if not self._live(session):
                    continue
                try:
                    _reconcile_against(session, tree, tier=tier, actor=actor)
                except Exception as failure:
                    failures.append((session, failure))
        return failures

    async def init_flow(self, directory: Path, name: str) -> FlowSession:
        ref = _new_flow_ref(directory.resolve(), name)
        self.check_available(ref.path)
        if ref.path.exists() or ref.path.is_symlink():
            raise FlowAlreadyExists(f"`{ref.relpath}` already exists")
        store = FlowStore.init(ref.path, name=ref.name)
        session = self._session(ref, store, _session_key(ref.path))
        async with self._first_scan(session) as tree:
            reconciliation.sync_workspace_code(tree, [session])
        return session

    @contextlib.asynccontextmanager
    async def _first_scan(self, session: FlowSession) -> AsyncGenerator[WorkspaceTree]:
        """A new session's first look at its workspace, once its watch is in
        place; anyone opening or closing it meanwhile waits for the look to
        finish. A session whose first sync does not finish — cancelled, or
        failed — is let go of before anyone waiting is let in, so the next
        open does the whole first sync again."""
        key = session.key
        opening = self._opening[key] = asyncio.Event()
        try:
            async with self._scan_lock(session.workspace_dir):
                await self.watches.settled(session.watch.root)
                yield await self._scan(session.workspace_dir)
        except BaseException:
            await self._discard(session)
            raise
        finally:
            del self._opening[key]
            opening.set()

    async def _discard(self, session: FlowSession) -> None:
        try:
            await session.close()
        finally:
            if self._live(session):
                del self._sessions[session.key]
                self.watches.release(session.watch.root)

    def _live(self, session: FlowSession) -> bool:
        return self._sessions.get(session.key) is session

    def _scan_lock(self, workspace_dir: Path) -> asyncio.Lock:
        return self._scan_locks.setdefault(workspace_dir, asyncio.Lock())

    async def _scan(self, workspace_dir: Path) -> WorkspaceTree:
        """The workspace as the scan thread found it.

        A cancelled caller is told nothing until the thread has let go of the
        tree: it holds the workspace's lock until then, so a retry cannot put
        a second scan of the same tree beside the first. The scan is told to
        stop, so that wait is short.
        """
        stop = threading.Event()
        if self._stopping.is_set():
            stop.set()
        self._scan_stops.add(stop)
        try:
            submitted = self._scanner.submit(
                scan_workspace, workspace_dir, stopping=stop
            )
            scanning = asyncio.wrap_future(submitted)
            try:
                return await asyncio.shield(scanning)
            except asyncio.CancelledError:
                stop.set()
                submitted.cancel()
                await _finished(scanning)
                raise
        finally:
            self._scan_stops.discard(stop)

    def _session(self, ref: FlowRef, store: FlowStore, key: Path) -> FlowSession:
        self._remember_loop()
        session = FlowSession(
            ref,
            store,
            self._workspace_of(ref),
            key=key,
            tracker=self.tracker,
            streams=self._streams,
        )
        self._sessions[key] = session
        self._known[ref.path] = ref
        self.watches.hold(session.watch.root)
        return session

    def _workspace_of(self, ref: FlowRef) -> Path:
        return ref.path.parent

    async def close_session(
        self,
        session: FlowSession,
        *,
        still: Callable[[FlowSession], bool] | None = None,
        forced: bool = False,
    ) -> bool:
        """Let go of an open flow, and keep knowing where it is.

        Everything that awaits happens while the session is still the one
        attached, so a request arriving mid-close reuses it instead of opening
        a second store on the same files; `still` is asked again after them.
        """
        key = session.key

        def kept() -> bool:
            return self._sessions.get(key) is not session or (
                still is not None and not still(session)
            )

        # A slow first open finishes, or is let go of, before anything closes
        # it: otherwise its scan would land on the store this closes.
        while (opening := self._opening.get(key)) is not None:
            await opening.wait()
        if self._sessions.get(key) is not session:
            return False
        if forced:
            session.queue.close()
        await session.reactor.stop()
        if kept():
            session.reactor.arm()
            return False
        await session.kernel.stop()
        if kept():
            session.reactor.arm()
            return False
        if forced:
            await session.queue.drained()
            ended = [
                AgentEnd(actor=agent.actor, label=agent.label)
                for agent in session.store.index.agent_sessions()
            ]
            if ended:
                session.store.commit(ended, intent="Close notebook", actor="user")
            if self._drop_leases is not None:
                self._drop_leases(session.ref.address)
        del self._sessions[key]
        self.watches.release(session.watch.root)
        session.store.close()
        return True

    def check_available(self, *paths: Path) -> None:
        for path in paths:
            if any(_inside(path, held) for held in self._reserved):
                raise FlowError(f"`{path}` is busy with a filesystem operation")

    async def change_path(
        self,
        source: Path,
        target: Path | None,
        *,
        close_open: bool | list[str],
        written: Callable[[Path, os.stat_result, os.stat_result], None] | None = None,
    ) -> None:
        """Mutate a directory entry after checking all sessions affected by it."""
        files.check_protected(source, self.ui_directories)
        paths = (source,) if target is None else (source, target)
        self.check_available(*paths)
        with files.os_errors():
            if target is not None:
                files.check_destination(source, target)
            affected = [
                session
                for session in self.opened()
                if session.ref.path.is_relative_to(source)
            ]
            if close_open is not True and any(
                not isinstance(close_open, list) or s.session_id not in close_open
                for s in affected
            ):
                flows = sorted(
                    (
                        {
                            "name": s.ref.name,
                            "path": s.ref.address,
                            "session_id": s.session_id,
                        }
                        for s in affected
                    ),
                    key=lambda flow: flow["path"],
                )
                names = ", ".join(flow["name"] for flow in flows)
                raise FlowOpen(f"close the open notebooks first: {names}", flows=flows)
            self._reserved.update(paths)
            try:
                await files.finish_operation(
                    self._apply_path_change(source, target, affected, written)
                )
            finally:
                self._reserved.difference_update(paths)

    async def _apply_path_change(
        self,
        source: Path,
        target: Path | None,
        affected: list[FlowSession],
        written: Callable[[Path, os.stat_result, os.stat_result], None] | None,
    ) -> None:
        for session in affected:
            await self.close_session(session, forced=True)
        if target is None:
            await asyncio.to_thread(files.remove, source)
        else:
            info = await asyncio.to_thread(files.move, source, target)
            if written is not None and info is not None:
                written(target, *info)
        for refs in (self._known, self._found):
            for path in list(refs):
                if path.is_relative_to(source):
                    del refs[path]
                    if target is not None:
                        moved = target / path.relative_to(source)
                        self._found[moved] = FlowRef(
                            moved.name.removesuffix(FLOW_SUFFIX), moved, moved.name
                        )

    async def delete_flow(
        self, ref: FlowRef, *, close_open: bool | list[str] = False
    ) -> None:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        await self.change_path(ref.path, None, close_open=close_open)

    async def rename_flow(
        self, ref: FlowRef, name: str, *, close_open: bool | list[str] = False
    ) -> FlowRef:
        files.valid_name(name.strip().removesuffix(FLOW_SUFFIX))
        renamed = _new_flow_ref(ref.path.parent, name)
        if renamed.path == ref.path:
            files.check_protected(ref.path, self.ui_directories)
            return ref
        return await self.move_flow(ref, renamed, close_open=close_open)

    async def move_flow(
        self, ref: FlowRef, target: FlowRef, *, close_open: bool | list[str] = False
    ) -> FlowRef:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        await self.change_path(ref.path, target.path, close_open=close_open)
        self._found[target.path] = target
        return target

    async def duplicate_flow(self, ref: FlowRef, name: str) -> FlowRef:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        duplicated = _new_flow_ref(ref.path.parent, name)
        self.check_available(ref.path, ref.path.resolve(), duplicated.path)
        if duplicated.path == ref.path:
            raise FlowError(f"`{name}` is the same name as `{ref.name}`")
        if duplicated.path.exists():
            raise FlowAlreadyExists(f"`{duplicated.relpath}` already exists")
        try:
            shutil.copytree(
                ref.path, duplicated.path, ignore=_duplicate_skips(ref.path)
            )
        except BaseException:
            shutil.rmtree(duplicated.path, ignore_errors=True)
            raise
        self._found[duplicated.path] = duplicated
        return duplicated

    async def close(self) -> None:
        self._closed = True
        self._stopping.set()
        for stop in self._scan_stops:
            stop.set()
        await asyncio.to_thread(
            partial(self._scanner.shutdown, wait=True, cancel_futures=True)
        )
        # With the scans stopped, an open in flight ends promptly; it closes
        # its own session when it fails, and must not have it closed twice.
        openings = [opening.wait() for opening in self._opening.values()]
        if openings:
            await asyncio.gather(*openings)
        self._unsubscribe_tracker()
        for session in list(self._sessions.values()):
            self.watches.release(session.watch.root)
            try:
                await session.close()
            except Exception:
                logger.exception("flow session failed to close")
        self._sessions.clear()

    def _remember_loop(self) -> None:
        loop = _running_loop()
        if loop is not None:
            self._loop = loop

    def _experiment_deleted(self, experiment_id: str) -> None:
        if self._closed:
            return
        loop = self._loop
        if loop is not None and _running_loop() is loop:
            self._apply_experiment_deleted(experiment_id)
            return
        if loop is not None and loop.is_running() and not loop.is_closed():
            loop.call_soon_threadsafe(self._apply_experiment_deleted, experiment_id)
            return
        self._apply_experiment_deleted(experiment_id)

    def _apply_experiment_deleted(self, experiment_id: str) -> None:
        if self._closed:
            return
        for session in tuple(self._sessions.values()):
            session.experiment_states.invalidate(experiment_id)
            for lane, cell in queries.experiment_locations(session, experiment_id):
                self.push_state(
                    session,
                    "experiment_removed",
                    lane=lane,
                    cell=cell,
                )


def _duplicate_skips(flow_dir: Path) -> Callable[[str, list[str]], set[str]]:
    """What a flow's copy leaves behind: the live kernel's socket and token,
    and the index. The source session holds its index open in WAL mode, so its
    files on disk need not be a consistent database; the journal is."""
    kernel_dir = store_dir(flow_dir) / KERNEL_DIRNAME
    index_files = {INDEX_NAME + suffix for suffix in ("", "-wal", "-shm")}

    def skips(directory: str, names: list[str]) -> set[str]:
        if Path(directory) == kernel_dir:
            return set(names)
        if Path(directory) == store_dir(flow_dir):
            return index_files & set(names)
        return set()

    return skips


def _session_key(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        # A symlink loop raises RuntimeError before Python 3.13.
        return path.absolute()


def _new_flow_ref(root: Path, name: str) -> FlowRef:
    relative = Path(name.strip().strip("/"))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise FlowError(f"`{name}` is not a name a flow can have")
    stem = relative.name.removesuffix(FLOW_SUFFIX)
    path = root / relative.parent / f"{stem}{FLOW_SUFFIX}"
    return FlowRef(
        name=stem,
        path=files.entry_path(path, strict=False),
        relpath=path.relative_to(root).as_posix(),
    )


def _answers(ref: FlowRef, wanted: str, directory: Path) -> bool:
    if wanted == ref.name:
        return True
    if not ref.path.is_relative_to(directory):
        return False
    relpath = ref.path.relative_to(directory).as_posix()
    return wanted == relpath.removesuffix(FLOW_SUFFIX)


def _inside(path: Path, directory: Path) -> bool:
    return path.is_relative_to(directory) or directory.is_relative_to(path)


def _relative_to(ref: FlowRef, directory: Path) -> FlowRef:
    """The ref named relative to `directory` where it lies beneath it."""
    if ref.path != directory and ref.path.is_relative_to(directory):
        relpath = ref.path.relative_to(directory).as_posix()
    elif directory.is_relative_to(ref.path):
        relpath = ref.path.name
    else:
        relpath = ref.path.as_posix()
    return FlowRef(name=ref.name, path=ref.path, relpath=relpath)


def _reconcile_against(
    session: FlowSession, tree: WorkspaceTree, *, tier: Tier, actor: str | None
) -> None:
    workspace_changed = bool(reconciliation.sync_workspace_code(tree, [session]))
    if workspace_changed:
        session.kernel.evict_workspace_modules()
    # For a cell that did not opt in, the env is recorded, never acted on: a
    # run that starts after an install records the pins it ran under, and the
    # kernel keeps the modules it already imported until somebody restarts it.
    # An env-sensitive cell is the exception: it goes stale.
    env_changed = envs.sync(session.workspace_dir, [session])
    moved = session.reconcile(tier=tier, actor=actor).moved
    if workspace_changed or env_changed or moved:
        session.reactor.arm()


def _is_flow(path: Path) -> bool:
    return path.is_dir() and (
        store_dir(path).is_dir() or path.resolve().name.endswith(FLOW_SUFFIX)
    )


async def _finished(future: "asyncio.Future[Any]") -> None:
    """Wait for `future` to finish, through any further cancellation; what it
    ended with is nobody's to hear."""
    while not future.done():
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait([future])
    if not future.cancelled():
        future.exception()


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None
