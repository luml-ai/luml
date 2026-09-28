"""The daemon's path-keyed flow sessions, one kernel each.

A flow session is opened once and kept. The daemon is the single writer of
every `.lumlflow/` store beneath the workspace, and two sessions over one store
would race on the journal — so sessions are cached by path, and a second
request for a flow gets the session that is already open.

Nothing here survives a restart, and nothing needs to: the store is the state.
A session is a store handle, a planner, a queue, and a kernel that has not been
spawned yet.

The current API still carries a launch directory for name resolution and
listings. It is not a daemon boundary: sessions are keyed by each flow's
absolute path and a flow elsewhere opens in the same hub.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import envs, queries
from lumlflow.flow.daemon import reconcile as reconciliation
from lumlflow.flow.daemon.kernel_proc import KernelProcess
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
        # What a file event has to be on for this flow to care: its own cells,
        # and the shared code of the workspace it runs under. Monitoring belongs
        # to the flow — an event outside this set is not this session's news.
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
        # Reactivity's sweep. Armed by whatever moved a verdict, never by its
        # own runs — see `reactive`.
        self.reactor = Reactor(self)
        # Cell files as acceptance last found them level with the branch head,
        # so a burst of verbs re-parses only what actually moved. Session-lived:
        # a daemon that just started knows nothing and reads everything.
        self.accepted_files: dict[str, AcceptedFile] = {}
        self.worktree = Worktree(store)

    def _tracker_state(self, ref: TrackerRef) -> tuple[TrackerState, str]:
        state = queries.experiment_state(self, ref)
        return state.state, state.sentence

    @property
    def branch(self) -> str:
        """The branch this session answers for: what the worktree is bound to.

        Reconciliation always runs against this one, whichever branch the op
        that asked for it names: the files are one branch's slice, and
        accepting them onto another would hand that branch an edit it never
        asked for — pin-at-fork says a fork takes updates by adopt or not at
        all.
        """
        return self.worktree.branch

    def _observed(self, event: str, params: dict[str, Any]) -> None:
        """A kernel event on its way to whoever is watching this flow.

        Stamped with the last committed step: a run's lifecycle is not itself
        journaled, and without a position a client could not order it against
        the transactions it lands between.
        """
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
            # A kernel that will not die is no reason to leak the store handle.
            self.store.close()


class Hub:
    """Every flow the daemon hosts, opened on demand and closed together."""

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
        # The trees the open sessions need watched, refcounted so several flows
        # in one workspace share its watch. Moved here whether or not a watcher
        # is listening: the hub is what knows when a session begins and ends.
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
        """Attach to a flow. A clone carries `flow.yaml` but no store; opening
        it roots a fresh history under the identity git carried.

        The first attach is the cold-start tier of reconciliation: whatever
        happened to the files while no daemon was watching lands now, as the
        one coarse offline transaction it honestly is.
        """
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
        # Opening is where reactivity catches up on a workspace nobody was
        # watching: the offline edits have just landed, and cells left unsynced
        # by the last session are unsynced still. Armed whatever the cold start
        # found, because "nothing changed on disk" is not "nothing to refresh".
        session.reactor.arm()
        return session

    def attached(self, path: Path) -> FlowSession | None:
        """The session already open over this flow directory, or None.

        Never opens one. What the watcher is for is waking a flow somebody is
        watching; a flow nobody opened has no session to wake, and whatever
        moved under it while nobody was looking is the cold-start tier's to take
        up when someone does.
        """
        return self._sessions.get(path)

    def opened(
        self, *, here: bool = False, directory: Path | None = None
    ) -> list[FlowSession]:
        """The flows this daemon currently holds open — the ones with a kernel.

        `here` narrows to the ones this workspace's env governs: a flow opened
        from above the launch directory runs under its own, so an install here
        neither reaches it nor is anything it should be reported against.
        """
        return [
            session
            for session in self._sessions.values()
            if not here or session.workspace_dir == directory
        ]

    def running(self) -> int:
        """Runs in flight across every flow this process holds open.

        What makes the difference between plumbing that may be replaced and a
        process carrying work somebody is waiting on.
        """
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
        """Push an ephemeral state hint at this flow's current journal step."""
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
        # The env is recorded, never acted on: a run that starts after an
        # install records the pins it ran under, and the kernel keeps the
        # modules it already imported until somebody restarts it.
        env_changed = envs.sync(session.workspace_dir, [session])
        moved = session.reconcile(tier=tier, actor=actor).moved
        if workspace_changed or env_changed or moved:
            # A cell, shared-code, or environment fact moved, so a previously
            # declined refresh may now be safe to try.
            session.reactor.arm()

    def init_flow(self, directory: Path, name: str) -> FlowSession:
        """Scaffold a new flow in the workspace, unbound.

        Binding the worktree and projecting `main` into `cells/` is the
        checkout, which `lumlflow init` and the browser's init-here gesture
        perform on top of this; the API path leaves the flow unbound.
        """
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
        """The containing directory whose code and environment the flow uses."""
        return ref.path.parent

    async def delete_flow(self, ref: FlowRef) -> None:
        """Remove the flow and everything it owns — its store included."""
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        session = self._sessions.pop(ref.path, None)
        self._known.pop(ref.path, None)
        if session is not None:
            self.watches.release(session.watch.root)
            await session.close()
        shutil.rmtree(ref.path)

    async def close(self) -> None:
        self._closed = True
        self._unsubscribe_tracker()
        for session in list(self._sessions.values()):
            self.watches.release(session.watch.root)
            try:
                await session.close()
            except Exception:
                # One flow that will not close is not a reason to leave the
                # rest of the workspace open.
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


def _new_flow_ref(root: Path, name: str) -> FlowRef:
    """Where `flow init churn` puts the directory, and what it is called."""
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
