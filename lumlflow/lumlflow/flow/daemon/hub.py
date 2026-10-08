import asyncio
import logging
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import envs, queries, workspace
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
from lumlflow.flow.errors import (
    FlowAlreadyExists,
    FlowAmbiguous,
    FlowError,
    FlowNotFound,
)
from lumlflow.flow.scheduler.planner import Planner, TrackerState
from lumlflow.flow.scheduler.queue import RunQueue
from lumlflow.flow.store.flowstore import (
    FLOW_SUFFIX,
    INDEX_NAME,
    FlowStore,
    store_dir,
)
from lumlflow.flow.store.models import TrackerRef
from lumlflow.tracker import TrackerProvider

logger = logging.getLogger(__name__)


class FlowSession:
    def __init__(
        self,
        ref: FlowRef,
        store: FlowStore,
        workspace_dir: Path,
        *,
        tracker: TrackerProvider,
        streams: Streams | None = None,
    ) -> None:
        self.ref = ref
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
    ) -> None:
        if tracker is None:
            from lumlflow.settings import get_tracker

            tracker = get_tracker()
        self.tracker = tracker
        self._streams = streams
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

    def flows(self) -> list[FlowRef]:
        return sorted(
            self._known.values(),
            key=lambda ref: str(ref.path),
        )

    def listing(self, root: Path) -> workspace.DirectoryListing:
        listing = workspace.list_directory(root)
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
        known = [
            ref
            for path, ref in (self._found | self._known).items()
            if path not in self._sessions
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
                (asked.is_absolute() and session.ref.path == asked.resolve())
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
                return self.open(refs[0])
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

    def open(self, ref: FlowRef, *, actor: str | None = None) -> FlowSession:
        self._remember_loop()
        session = self._sessions.get(ref.path)
        if session is not None:
            session.touch()
            return session
        store = (
            FlowStore.open(ref.path)
            if store_dir(ref.path).is_dir()
            else FlowStore.init(ref.path)
        )
        session = self._session(ref, store)
        reconciliation.sync_workspace_code(session.workspace_dir, [session])
        envs.sync(session.workspace_dir, [session])
        session.reconcile(tier="cold", actor=actor)
        session.reactor.arm()
        return session

    def attached(self, path: Path) -> FlowSession | None:
        return self._sessions.get(path)

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
        workspace_changed = bool(
            reconciliation.sync_workspace_code(session.workspace_dir, [session])
        )
        if workspace_changed:
            session.kernel.evict_workspace_modules()
        # For a cell that did not opt in, the env is recorded, never acted on:
        # a run that starts after an install records the pins it ran under, and
        # the kernel keeps the modules it already imported until somebody
        # restarts it. An env-sensitive cell is the exception: it goes stale.
        env_changed = envs.sync(session.workspace_dir, [session])
        moved = session.reconcile(tier=tier, actor=actor).moved
        if workspace_changed or env_changed or moved:
            session.reactor.arm()

    def init_flow(self, directory: Path, name: str) -> FlowSession:
        ref = _new_flow_ref(directory.resolve(), name)
        if ref.path.exists():
            raise FlowAlreadyExists(f"`{ref.relpath}` already exists")
        store = FlowStore.init(ref.path, name=ref.name)
        session = self._session(ref, store)
        reconciliation.sync_workspace_code(session.workspace_dir, [session])
        return session

    def _session(self, ref: FlowRef, store: FlowStore) -> FlowSession:
        self._remember_loop()
        session = FlowSession(
            ref,
            store,
            self._workspace_of(ref),
            tracker=self.tracker,
            streams=self._streams,
        )
        self._sessions[ref.path] = session
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
    ) -> bool:
        """Let go of an open flow, and keep knowing where it is.

        Everything that awaits happens while the session is still the one
        attached, so a request arriving mid-close reuses it instead of opening
        a second store on the same files; `still` is asked again after them.
        """
        path = session.ref.path

        def kept() -> bool:
            return self._sessions.get(path) is not session or (
                still is not None and not still(session)
            )

        if self._sessions.get(path) is not session:
            return False
        await session.reactor.stop()
        if kept():
            session.reactor.arm()
            return False
        await session.kernel.stop()
        if kept():
            session.reactor.arm()
            return False
        del self._sessions[path]
        self.watches.release(session.watch.root)
        session.store.close()
        return True

    async def delete_flow(self, ref: FlowRef) -> None:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        self._known.pop(ref.path, None)
        self._found.pop(ref.path, None)
        while (session := self._sessions.get(ref.path)) is not None:
            await self.close_session(session)
        shutil.rmtree(ref.path)

    async def rename_flow(self, ref: FlowRef, name: str) -> FlowRef:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        renamed = _new_flow_ref(ref.path.parent, name)
        if renamed.path == ref.path:
            return ref
        if renamed.path.exists():
            raise FlowAlreadyExists(f"`{renamed.relpath}` already exists")
        self._known.pop(ref.path, None)
        self._found.pop(ref.path, None)
        while (session := self._sessions.get(ref.path)) is not None:
            await self.close_session(session)
        ref.path.rename(renamed.path)
        self._found[renamed.path] = renamed
        return renamed

    async def duplicate_flow(self, ref: FlowRef, name: str) -> FlowRef:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        duplicated = _new_flow_ref(ref.path.parent, name)
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


def _new_flow_ref(root: Path, name: str) -> FlowRef:
    relative = Path(name.strip().strip("/"))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise FlowError(f"`{name}` is not a name a flow can have")
    stem = relative.name.removesuffix(FLOW_SUFFIX)
    path = root / relative.parent / f"{stem}{FLOW_SUFFIX}"
    return FlowRef(name=stem, path=path, relpath=path.relative_to(root).as_posix())


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


def _is_flow(path: Path) -> bool:
    return path.is_dir() and (
        store_dir(path).is_dir() or path.name.endswith(FLOW_SUFFIX)
    )


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None
