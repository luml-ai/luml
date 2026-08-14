"""Reactivity's other half: the sweep that runs what `auto` decided.

The planner answers *what* should refresh itself; nothing there runs anything.
This is the loop that does — armed by the things that can make a cell newly
worth running (an edit landing by verb or by watcher, a flow opening, a run
finishing, the setting itself being turned on) and quiet the rest of the time.

Two properties it has to keep. It settles first, so a burst of edits is one
sweep rather than one per keystroke — the watcher's debounce covers files, and
this covers the browser and an agent. And it never re-arms itself: a run
commits transactions, and an arm on those would be a flow that recomputes
forever. Everything that arms it is something a person or an agent did.

A sweep is latency, never truth. Cancelling one, losing one to a daemon
restart, or never running one at all leaves the store exactly as correct as
before — the same cells are unsynced, and the run button says so.
"""

import asyncio
import contextlib
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

#: Who a run nobody asked for is attributed to. A first-class actor beside
#: `user` and an agent's name, because the journal is read back as *who did
#: this* and answering `user` for a run the user never asked for is a lie the
#: timeline would then render.
AUTO_ACTOR = "auto"

# How long a sweep waits for the dust to settle before planning anything. An
# edit burst from a browser or an agent arrives over milliseconds, and a
# closure planned mid-burst is a closure the next keystroke invalidates.
SETTLE_S = 0.25
# How many times one sweep re-plans after running something. Each pass runs a
# whole closure, so the second pass is normally empty; the bound is against a
# flow whose verdicts somehow will not converge, not against normal work.
_MAX_PASSES = 4


class Reactor:
    """One flow's auto-materialization sweep. Loop thread only, like the store."""

    def __init__(self, session: "FlowSession", *, settle_s: float = SETTLE_S) -> None:
        self._session = session
        self._settle_s = settle_s
        self._task: asyncio.Task[None] | None = None
        self._armed = False

    @property
    def sweeping(self) -> bool:
        return self._task is not None and not self._task.done()

    def arm(self) -> None:
        """Something moved — sweep once it is quiet again.

        Cheap enough to call from anywhere that might have changed a verdict:
        `lazy` returns here, and a sweep that finds nothing to do costs one
        staleness derivation the surfaces were going to ask for anyway.
        """
        if self._session.store.manifest.settings.reactivity == "lazy":
            return
        self._armed = True
        if self.sweeping:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # A verb-shaped process with no loop of its own — the CLI talking
            # to a store directly. There is nothing to sweep on.
            return
        self._task = loop.create_task(self._sweep())

    async def settled(self) -> None:
        """Wait out the sweep in flight, if there is one.

        What a test uses where a person would wait a second and look. The sweep
        swallows its own failures, so the only thing that reaches here is a
        cancellation.
        """
        task = self._task
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def stop(self) -> None:
        task, self._task = self._task, None
        self._armed = False
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _sweep(self) -> None:
        try:
            while self._armed:
                self._armed = False
                await asyncio.sleep(self._settle_s)
                if self._armed:
                    # Still arriving. Wait for the quiet point rather than
                    # planning against a slice that is still moving.
                    continue
                for _ in range(_MAX_PASSES):
                    if not await self._advance():
                        break
        except asyncio.CancelledError:
            raise
        except Exception:
            # A flow whose sweep cannot run is a flow whose cells stay unsynced
            # — which is a state the workbench already renders. It is never a
            # reason to take the daemon down with it.
            traceback.print_exc()
        finally:
            self._task = None

    async def _advance(self) -> bool:
        """Run one round of what reactivity wants. True if anything moved.

        Targets are re-planned each round rather than run from one list: the
        first closure rematerializes parents the rest were waiting on, and a
        list taken before that would run cells whose plans it no longer
        describes.
        """
        session = self._session
        branch = session.branch
        targets = session.planner.auto_targets(branch)
        if not targets:
            return False
        moved = False
        for target in targets:
            outcome = await session.queue.submit(
                target, branch=branch, actor=AUTO_ACTOR
            )
            if outcome.abandoned:
                # Somebody stopped it, or the branch edited out from under it.
                # Either way this sweep is answering a question nobody is
                # asking any more.
                return False
            moved = moved or bool(outcome.executed or outcome.cached)
        return moved
