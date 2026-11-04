import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from lumlflow.flow.errors import FlowError
from lumlflow.flow.store.models import AUTO_ACTOR, CellNoted

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

__all__ = ["AUTO_ACTOR", "Reactor"]

logger = logging.getLogger(__name__)

SETTLE_S = 0.25
_MAX_PASSES = 4


class Reactor:
    def __init__(self, session: "FlowSession", *, settle_s: float = SETTLE_S) -> None:
        self._session = session
        self._settle_s = settle_s
        self._task: asyncio.Task[None] | None = None
        self._armed = False

    @property
    def sweeping(self) -> bool:
        return self._task is not None and not self._task.done()

    def arm(self) -> None:
        if self._session.store.manifest.settings.reactivity == "lazy":
            return
        self._armed = True
        if self.sweeping:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._task = loop.create_task(self._sweep())

    async def settled(self) -> None:
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
                    continue
                for _ in range(_MAX_PASSES):
                    if not await self._advance():
                        break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("reactive sweep failed")
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
        moved = False
        for branch in session.store.index.branches():
            # A rewound lane keeps its promise that nothing recomputes until
            # its next change clears `head_step`.
            if branch.archived or branch.head_step is not None:
                continue
            moved = await self._advance_lane(branch.name) or moved
        return moved

    async def _advance_lane(self, branch: str) -> bool:
        session = self._session
        targets = session.planner.auto_targets(branch)
        if not targets:
            return False
        moved = False
        for target in targets:
            verdict = next(
                (
                    candidate
                    for candidate in session.planner.auto_verdicts(branch).values()
                    if candidate.slug == target
                ),
                None,
            )
            if verdict is None or not verdict.taken:
                continue
            self._push_refreshing(branch, target)
            try:
                outcome = await session.queue.submit(
                    target, branch=branch, actor=AUTO_ACTOR
                )
            except Exception as error:
                self._record_refresh_failure(branch, target, error)
                continue
            if outcome.abandoned:
                break
            moved = moved or bool(outcome.executed or outcome.cached)
        return moved

    def _push_refreshing(self, branch: str, target: str) -> None:
        session = self._session
        if session.streams is None:
            return
        session.streams.state(
            session.ref.address,
            "refreshing",
            step=session.store.next_step - 1,
            lane=branch,
            cell=target,
        )

    def _record_refresh_failure(
        self, branch: str, target: str, error: Exception
    ) -> None:
        session = self._session
        try:
            branch_id = session.store.branches.get(branch).branch_id
            uid = session.store.branches.resolve(branch, target)
        except FlowError:
            return
        version = session.store.index.slice_versions(branch_id).get(uid)
        if version is None:
            return
        detail = " ".join(str(error).split()) or type(error).__name__
        sentence = f"could not refresh: {detail}"
        session.store.commit(
            [
                CellNoted(
                    uid=uid,
                    kind="refresh_failed",
                    sentence=sentence,
                    version_id=version.version_id,
                )
            ],
            intent=sentence,
            actor="system",
            branch=branch_id,
        )
