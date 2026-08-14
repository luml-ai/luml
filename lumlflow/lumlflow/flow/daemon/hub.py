"""The daemon's object graph: one workspace, N flows, one kernel each.

A flow session is opened once and kept. The daemon is the single writer of
every `.lumlflow/` store beneath the workspace, and two sessions over one store
would race on the journal — so sessions are cached by path, and a second
request for a flow gets the session that is already open.

Nothing here survives a restart, and nothing needs to: the store is the state.
A session is a store handle, a planner, a queue, and a kernel that has not been
spawned yet.

The launch directory is the workspace this daemon is registered for and locked
to. A flow the browser reached by climbing above it is hosted here too, but
under the workspace it belongs to: one venv and one set of helpers per workspace
holds whoever happens to be hosting — and watching follows that, not the launch
directory, so an outside flow is watched over its own workspace rather than not
at all.
"""

import contextlib
import shutil
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumlflow.flow.daemon import docs, envs, secrets, workspace
from lumlflow.flow.daemon import reconcile as reconciliation
from lumlflow.flow.daemon.kernel_proc import KernelProcess
from lumlflow.flow.daemon.projections import Worktree
from lumlflow.flow.daemon.reactive import Reactor
from lumlflow.flow.daemon.reconcile import AcceptedFile, Reconciliation, Tier
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.daemon.uploads import NATIVE_TYPES, Uploader, Uploads
from lumlflow.flow.daemon.watcher import Watches, WatchSet
from lumlflow.flow.daemon.workspace import FlowRef
from lumlflow.flow.dsl.accept import Acceptance
from lumlflow.flow.errors import (
    EnvError,
    FlowAlreadyExists,
    FlowError,
    FlowNotFound,
)
from lumlflow.flow.scheduler.planner import Planner
from lumlflow.flow.scheduler.queue import RunQueue
from lumlflow.flow.store.flowstore import (
    FLOW_SUFFIX,
    FlowStore,
    store_dir,
)


@dataclass(frozen=True)
class Focus:
    """Where the user is looking, as the browser last reported it.

    Reported, never inferred: a brief that guessed at a focus nobody has would
    point an agent at whatever happens to be first. Absent a report there is
    none, and the brief simply omits it.
    """

    branch: str | None = None
    asset: str | None = None
    compare: tuple[str, ...] = ()


class FlowSession:
    def __init__(
        self,
        ref: FlowRef,
        store: FlowStore,
        workspace_dir: Path,
        *,
        uploader: Uploader | None = None,
        streams: Streams | None = None,
    ) -> None:
        self.ref = ref
        self.store = store
        self.workspace_dir = workspace_dir
        # What a file event has to be on for this flow to care: its own cells,
        # and the shared code of the workspace it runs under. Monitoring belongs
        # to the flow — an event outside this set is not this session's news.
        self.watch = WatchSet(flow_dir=ref.path, workspace_dir=workspace_dir)
        self.streams = streams
        if streams is not None:
            store.listeners.append(
                lambda entry: streams.transaction(ref.relpath, entry)
            )
        self.kernel = KernelProcess(
            flow_dir=ref.path,
            workspace_dir=workspace_dir,
            sandbox_setting=store.manifest.settings.sandbox,
            on_event=self._observed if streams is not None else None,
            # `ctx.secret` reaches this flow's keychain entries and nothing
            # else: the kernel holds no secrets of its own, and the value it is
            # handed never comes back across this line.
            ask_secret=lambda name: secrets.get(ref.path, name),
        )
        self.planner = Planner(store)
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
        self.uploads = Uploads(store, flow=ref.name, uploader=uploader)
        # Whether this flow has been looked at for native outputs yet: the
        # scaffolding question is asked once per session, and again whenever
        # acceptance moves something.
        self.sdk_checked = False
        # Cell files as acceptance last found them level with the branch head,
        # so a burst of verbs re-parses only what actually moved. Session-lived:
        # a daemon that just started knows nothing and reads everything.
        self.accepted_files: dict[str, AcceptedFile] = {}
        self.worktree = Worktree(store)
        # A surface's report, not a fact about the store: it lives as long as
        # the daemon does and no longer.
        self.focus: Focus | None = None

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
                self.ref.relpath, event, params, step=self.store.next_step - 1
            )

    def reconcile(
        self, *, tier: Tier = "quiesce", actor: str | None = None
    ) -> Reconciliation:
        return reconciliation.reconcile(self, tier=tier, actor=actor)

    def declares_native(self) -> bool:
        """Does this flow publish anything — a `model`, `dataset`, `experiment`?"""
        branch = self.store.index.branch(self.branch)
        if branch is None:
            return False
        return any(
            spec.type in NATIVE_TYPES
            for version in self.store.index.slice_versions(branch.branch_id).values()
            for spec in version.manifest.produces.values()
        )

    async def close(self) -> None:
        try:
            await self.reactor.stop()
            await self.uploads.close()
            await self.kernel.stop()
        finally:
            # A kernel that will not die is no reason to leak the store handle.
            self.store.close()


class Hub:
    """Every flow the daemon hosts, opened on demand and closed together."""

    def __init__(
        self,
        root: Path,
        *,
        uploader: Uploader | None = None,
        streams: Streams | None = None,
    ) -> None:
        self.root = root.resolve()
        self._uploader = uploader
        self._streams = streams
        self._sessions: dict[Path, FlowSession] = {}
        # The trees the open sessions need watched, refcounted so several flows
        # in one workspace share its watch. Moved here whether or not a watcher
        # is listening: the hub is what knows when a session begins and ends.
        self.watches = Watches()
        # The workspace env is a singleton, so the SDK is added to it once —
        # whichever of the hosted flows turns out to publish first. Keyed by
        # workspace, because a flow opened from above the launch directory runs
        # under its own.
        self._sdk_scaffolded: set[Path] = set()

    def flows(self) -> list[FlowRef]:
        return workspace.find_flows(self.root)

    def select(self, name: str | None = None) -> FlowRef:
        return workspace.select_flow(self.root, name=name)

    def session(self, name: str | None = None) -> FlowSession:
        return self.open(self.select(name))

    def open(self, ref: FlowRef) -> FlowSession:
        """Attach to a flow. A clone carries `flow.yaml` but no store; opening
        it roots a fresh history under the identity git carried.

        The first attach is the cold-start tier of reconciliation: whatever
        happened to the files while no daemon was watching lands now, as the
        one coarse offline transaction it honestly is.
        """
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
        session.reconcile(tier="cold")
        self.document(session)
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

    def opened(self, *, here: bool = False) -> list[FlowSession]:
        """The flows this daemon currently holds open — the ones with a kernel.

        `here` narrows to the ones this workspace's env governs: a flow opened
        from above the launch directory runs under its own, so an install here
        neither reaches it nor is anything it should be reported against.
        """
        return [
            session
            for session in self._sessions.values()
            if not here or session.workspace_dir == self.root
        ]

    def running(self) -> int:
        """Runs in flight across every flow this process holds open.

        What makes the difference between plumbing that may be replaced and a
        process carrying work somebody is waiting on.
        """
        if self._streams is None:
            return 0
        return sum(
            len(self._streams.running(session.ref.relpath))
            for session in self._sessions.values()
        )

    async def quiesce(self, session: FlowSession, *, tier: Tier = "quiesce") -> None:
        """The pre-op contract: no version resolves against a stale file plane.

        Shared code first — a helper edit changes every cell's behaviour hash,
        and the kernel has to forget the old module before the next
        materialization imports it, or the cache is poisoned with a value
        computed from code the hash no longer describes.
        """
        if reconciliation.sync_workspace_code(session.workspace_dir, [session]):
            await session.kernel.evict_workspace_modules()
        # The env is recorded, never acted on: a run that starts after an
        # install records the pins it ran under, and the kernel keeps the
        # modules it already imported until somebody restarts it.
        envs.sync(session.workspace_dir, [session])
        moved = session.reconcile(tier=tier).moved
        if moved:
            # An edit landed — by verb, by agent, or by the watcher noticing a
            # file. Whichever door it came through, reactivity's question has a
            # new answer.
            session.reactor.arm()
        if moved or not session.sdk_checked:
            session.sdk_checked = True
            await self._scaffold_sdk(session)
        self.document(session)

    async def _scaffold_sdk(self, session: FlowSession) -> None:
        """Declaring a published output is what pulls the SDK into the env.

        A workspace that cannot be synced is not a reason to refuse the op that
        asked — the scaffolding is a convenience over a dependency the user can
        add themselves, and the upload path runs daemon-side either way.
        """
        here = session.workspace_dir
        if here in self._sdk_scaffolded or not session.declares_native():
            return
        # Claimed before the await: two flows declaring a native output in the
        # same breath must not both shell out to uv over one pyproject.
        self._sdk_scaffolded.add(here)
        with contextlib.suppress(EnvError, OSError):
            await envs.ensure_sdk(here)

    def document(self, session: FlowSession | None = None) -> None:
        """Keep the generated docs current — the agent that only reads files
        learns where it is from these, so they follow the state, not a verb.

        A workspace nobody can write to is not a reason to refuse the op that
        asked; the docs are a convenience over facts the store already holds.
        """
        with contextlib.suppress(OSError):
            docs.refresh_workspace(self.root, [ref.name for ref in self.flows()])
            if session is not None:
                docs.refresh_checkout(session)

    def init_flow(self, name: str) -> FlowSession:
        """Scaffold a new flow in the workspace, unbound.

        Binding the worktree and projecting `main` into `cells/` is the
        checkout, which `lumlflow init` and the browser's init-here gesture
        perform on top of this; the API path leaves the flow unbound.
        """
        ref = _new_flow_ref(self.root, name)
        if ref.path.exists():
            raise FlowAlreadyExists(f"`{ref.relpath}` already exists")
        store = FlowStore.init(ref.path, name=ref.name)
        session = self._session(ref, store)
        reconciliation.sync_workspace_code(self.root, [session])
        self.document(session)
        return session

    def _session(self, ref: FlowRef, store: FlowStore) -> FlowSession:
        session = FlowSession(
            ref,
            store,
            self._workspace_of(ref),
            uploader=self._uploader,
            streams=self._streams,
        )
        self._sessions[ref.path] = session
        self.watches.hold(session.watch.root)
        return session

    def _workspace_of(self, ref: FlowRef) -> Path:
        """Which workspace a flow runs under — one venv, one set of helpers.

        A flow the browser opened from above the launch directory belongs to
        its own workspace, not to this one: running it here would hand it an
        environment nobody installed for it and hide the `helpers.py` sitting
        beside it. This daemon still hosts it — the record, the lock, the port
        and the watched tree remain the launch directory's.
        """
        if ref.path.is_relative_to(self.root):
            return self.root
        return workspace.resolve_root(ref.path.parent)

    async def delete_flow(self, ref: FlowRef) -> None:
        """Remove the flow and everything it owns — its store included."""
        if not _is_flow(ref.path):
            raise FlowNotFound(f"`{ref.relpath}` is not a flow")
        session = self._sessions.pop(ref.path, None)
        if session is not None:
            self.watches.release(session.watch.root)
            await session.close()
        shutil.rmtree(ref.path)
        self.document()

    async def close(self) -> None:
        for session in list(self._sessions.values()):
            self.watches.release(session.watch.root)
            try:
                await session.close()
            except Exception:
                # One flow that will not close is not a reason to leave the
                # rest of the workspace open.
                traceback.print_exc()
        self._sessions.clear()


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
