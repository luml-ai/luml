import asyncio
import logging
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import envs, queries
from lumlflow.flow.daemon import reconcile as reconciliation
from lumlflow.flow.daemon.kernel_proc import KERNEL_DIRNAME, KernelProcess
from lumlflow.flow.daemon.projections import Worktree
from lumlflow.flow.daemon.reactive import Reactor
from lumlflow.flow.daemon.reconcile import AcceptedFile, Reconciliation, Tier
from lumlflow.flow.daemon.stream import StateName, Streams
from lumlflow.flow.daemon.watcher import Watches, WatchSet
from lumlflow.flow.daemon.workspace import FlowRef
from lumlflow.flow.dsl.accept import Acceptance
from lumlflow.flow.errors import FlowAlreadyExists, FlowError, FlowNotFound
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
        if streams is not None:
            store.listeners.append(
                lambda entry: streams.transaction(ref.address, entry)
            )
        self.kernel = KernelProcess(
            flow_dir=ref.path,
            workspace_dir=workspace_dir,
            tracker_store=tracker.store_path,
            fail_experiment=tracker.fail_experiment,
            on_event=self._observed if streams is not None else None,
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
            on_event=self._observed if streams is not None else None,
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

    def _observed(self, event: str, params: dict[str, Any]) -> None:
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
                for ref in self._known.values()
                if (
                    (asked.is_absolute() and ref.path == asked.resolve())
                    or name in {ref.name, ref.relpath, f"{ref.name}{FLOW_SUFFIX}"}
                )
            ]
            if len(refs) == 1:
                return self.open(refs[0])
            if len(refs) > 1:
                paths = ", ".join(f"`{ref.path}`" for ref in refs)
                raise FlowError(f"`{name}` names more than one known flow: {paths}")
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

    async def delete_flow(self, ref: FlowRef) -> None:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        session = self._sessions.pop(ref.path, None)
        self._known.pop(ref.path, None)
        if session is not None:
            self.watches.release(session.watch.root)
            await session.close()
        shutil.rmtree(ref.path)

    async def rename_flow(self, ref: FlowRef, name: str) -> FlowRef:
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        renamed = _new_flow_ref(ref.path.parent, name)
        if renamed.path == ref.path:
            return ref
        if renamed.path.exists():
            raise FlowAlreadyExists(f"`{renamed.relpath}` already exists")
        session = self._sessions.pop(ref.path, None)
        self._known.pop(ref.path, None)
        if session is not None:
            self.watches.release(session.watch.root)
            await session.close()
        ref.path.rename(renamed.path)
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


def _is_flow(path: Path) -> bool:
    return path.is_dir() and (
        store_dir(path).is_dir() or path.name.endswith(FLOW_SUFFIX)
    )


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None
