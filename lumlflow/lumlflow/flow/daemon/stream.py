import asyncio
from base64 import b64decode
from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
from typing import Any, Literal

from lumlflow.flow.store.models import Transaction

Frame = dict[str, Any]
StateName = Literal["experiment_removed", "refreshing", "order_changed"]

RING_CHUNKS = 512
RUNS_KEPT = 8
QUEUE_DEPTH = 1024

_LIFECYCLE = ("started", "progress", "materialized", "failed", "awaiting")
_LIFECYCLE_FIELDS = ("run_id", "slug", "state", "cost_seconds", "awaiting")
_KERNEL_STATE = "kernel_state"


class Subscription:
    def __init__(self, streams: "Streams", *, depth: int = QUEUE_DEPTH) -> None:
        self.journals: set[str] = set()
        self.runs: set[tuple[str, str]] = set()
        self._streams = streams
        self._depth = depth
        self._live: deque[Frame] = deque()
        self._caught_up: deque[Frame] = deque()
        self._arrived = asyncio.Event()
        self._lagged = False

    def offer(self, frame: Frame) -> None:
        if len(self._live) >= self._depth:
            self._lagged = True
        else:
            self._live.append(frame)
        self._arrived.set()

    def replay(self, frames: Iterable[Frame]) -> None:
        """Hold a catch-up, however long it is.

        Dropping one for its length would answer the overnight cursor — the
        case a cursor exists for — with `lagged`, whose only remedy is the
        replay that was just refused. The frames are the journal read the
        caller already has in hand, so holding them costs nothing that was not
        already spent.
        """
        self._caught_up.extend(frames)
        self._arrived.set()

    async def next(self) -> Frame:
        while True:
            frame = self._take()
            if frame is not None:
                return frame
            # Cleared before the wait and only when both are empty, with
            # nothing awaited in between: a frame offered from the loop's one
            # thread cannot land in the gap and go unnoticed.
            self._arrived.clear()
            await self._arrived.wait()

    def close(self) -> None:
        self._streams.drop(self)

    def _take(self) -> Frame | None:
        if self._caught_up:
            return self._caught_up.popleft()
        if not self._live:
            return None
        frame = self._live.popleft()
        if not self._lagged:
            return frame
        self._lagged = False
        self._live.clear()
        return {"channel": "journal", "type": "lagged"}


class Streams:
    def __init__(self, *, ring: int = RING_CHUNKS, runs: int = RUNS_KEPT) -> None:
        self._subscribers: list[Subscription] = []
        self._tails: OrderedDict[tuple[str, str], deque[Frame]] = OrderedDict()
        self._live: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._awaiting: dict[tuple[str, str], int] = {}
        self._activity: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        self._claims: dict[str, list[dict[str, Any]]] = {}
        self._claim_idle_s: float = 0.0
        self._ring = ring
        self._runs = runs

    @property
    def watchers(self) -> int:
        return len(self._subscribers)

    def subscribers(self, flow: str) -> int:
        return sum(
            1
            for subscription in self._subscribers
            if flow in subscription.journals
            or any(on_flow == flow for on_flow, _ in subscription.runs)
        )

    def subscribe(self) -> Subscription:
        subscription = Subscription(self)
        self._subscribers.append(subscription)
        return subscription

    def drop(self, subscription: Subscription) -> None:
        if subscription in self._subscribers:
            self._subscribers.remove(subscription)

    def transaction(self, flow: str, transaction: Transaction) -> None:
        self._deliver(
            lambda subscription: flow in subscription.journals,
            self.journal_frame(flow, transaction),
        )

    def state(
        self,
        flow: str,
        state: StateName,
        *,
        step: int,
        lane: str | None = None,
        cell: str | None = None,
    ) -> None:
        frame: Frame = {
            "channel": "journal",
            "type": "state",
            "state": state,
            "flow": flow,
            "step": step,
        }
        if lane is not None:
            frame["lane"] = lane
        if cell is not None:
            frame["cell"] = cell
        self._deliver(lambda subscription: flow in subscription.journals, frame)

    def agents(self, flow: str, sessions: list[dict[str, Any]], *, step: int) -> None:
        self._deliver(
            lambda subscription: flow in subscription.journals,
            {
                "channel": "journal",
                "type": "agents",
                "flow": flow,
                "step": step,
                "sessions": sessions,
            },
        )

    def activity(
        self,
        flow: str,
        *,
        actor: str,
        label: str,
        tool: str,
        slug: str | None,
        phase: Literal["started", "ended"],
        step: int,
    ) -> None:
        key = (flow, actor)
        if phase == "started":
            self._activity[key] = {
                "actor": actor,
                "label": label,
                "tool": tool,
                "slug": slug,
            }
            self._activity.move_to_end(key)
        else:
            self._activity.pop(key, None)
        frame: Frame = {
            "channel": "journal",
            "type": "activity",
            "flow": flow,
            "step": step,
            "phase": phase,
            "actor": actor,
            "label": label,
            "tool": tool,
            "slug": slug,
        }
        self._deliver(lambda subscription: flow in subscription.journals, frame)

    def claims(
        self,
        flow: str,
        claims: list[dict[str, Any]],
        *,
        step: int,
        idle_after_s: float,
    ) -> None:
        self._claims[flow] = [dict(claim) for claim in claims]
        self._claim_idle_s = idle_after_s
        self._deliver(
            lambda subscription: flow in subscription.journals,
            {
                "channel": "journal",
                "type": "claims",
                "flow": flow,
                "step": step,
                "claims": claims,
                "idle_after_s": idle_after_s,
            },
        )

    def claimed(self, flow: str) -> list[dict[str, Any]]:
        return [dict(claim) for claim in self._claims.get(flow, [])]

    @property
    def claim_idle_s(self) -> float:
        return self._claim_idle_s

    def active(self, flow: str, actor: str) -> dict[str, Any] | None:
        return self._activity.get((flow, actor))

    def activities(self, flow: str) -> list[dict[str, Any]]:
        return [
            dict(entry)
            for (on_flow, _), entry in self._activity.items()
            if on_flow == flow
        ]

    def kernel(
        self, flow: str, event: str, params: dict[str, Any], *, step: int
    ) -> None:
        if event == "log":
            self._chunk(flow, params)
            return
        if event == _KERNEL_STATE:
            if params.get("state") == "stopped":
                self._retire_live(flow, step=step)
            self._deliver(
                lambda subscription: flow in subscription.journals,
                {
                    "channel": "journal",
                    "type": "kernel",
                    "flow": flow,
                    "event": _KERNEL_STATE,
                    "step": step,
                    "kernel": str(params.get("state") or "stopped"),
                },
            )
            return
        if event not in _LIFECYCLE:
            return
        self._track(flow, event, params)
        frame: Frame = {
            "channel": "journal",
            "type": "kernel",
            "flow": flow,
            "event": event,
            "step": step,
        }
        frame.update(
            {
                name: params[name]
                for name in _LIFECYCLE_FIELDS
                if params.get(name) is not None
            }
        )
        if event == "started":
            frame["awaiting"] = self._awaiting.get(
                (flow, str(params.get("run_id") or "")), 1
            )
        self._deliver(lambda subscription: flow in subscription.journals, frame)

    def tail(self, flow: str, run_id: str) -> list[Frame]:
        return list(self._tails.get((flow, run_id)) or ())

    def running(self, flow: str) -> list[dict[str, Any]]:
        return [
            {
                "run_id": run_id,
                "slug": slug,
                "awaiting": self._awaiting.get((on_flow, run_id), 1),
            }
            for (on_flow, run_id), slug in self._live.items()
            if on_flow == flow
        ]

    def journal_frame(self, flow: str, transaction: Transaction) -> Frame:
        return {
            "channel": "journal",
            "type": "transaction",
            "flow": flow,
            "step": transaction.step,
            "transaction": transaction.model_dump(mode="json"),
        }

    def _retire_live(self, flow: str, *, step: int) -> None:
        # A kernel that dies mid-run never reports an ending for it.
        for on_flow, run_id in [key for key in self._live if key[0] == flow]:
            slug = self._live[(on_flow, run_id)]
            self.kernel(
                flow,
                "failed",
                {"run_id": run_id, "slug": slug, "state": "failed"},
                step=step,
            )

    def _track(self, flow: str, event: str, params: dict[str, Any]) -> None:
        key = (flow, str(params.get("run_id") or ""))
        if event in ("materialized", "failed"):
            self._live.pop(key, None)
            self._awaiting.pop(key, None)
            return
        if event == "awaiting":
            waiting = int(params.get("awaiting") or 0)
            if waiting:
                self._awaiting[key] = waiting
            else:
                self._awaiting.pop(key, None)
            return
        if event != "started":
            return
        self._live[key] = str(params.get("slug") or "")
        self._live.move_to_end(key)
        while len(self._live) > self._runs:
            retired, _ = self._live.popitem(last=False)
            self._awaiting.pop(retired, None)

    def _chunk(self, flow: str, params: dict[str, Any]) -> None:
        run_id = str(params.get("run_id") or "")
        frame: Frame = {
            "channel": "logs",
            "flow": flow,
            "run_id": run_id,
            "seq": int(params.get("seq") or 0),
            "stream": str(params.get("stream") or "stdout"),
            "text": _text(params.get("bytes")),
        }
        self._remember(flow, run_id, frame)
        self._deliver(
            lambda subscription: (flow, run_id) in subscription.runs,
            frame,
        )

    def _remember(self, flow: str, run_id: str, frame: Frame) -> None:
        key = (flow, run_id)
        tail = self._tails.get(key)
        if tail is None:
            tail = deque(maxlen=self._ring)
            self._tails[key] = tail
        self._tails.move_to_end(key)
        tail.append(frame)
        while len(self._tails) > self._runs:
            self._tails.popitem(last=False)

    def _deliver(self, wanted: Callable[[Subscription], bool], frame: Frame) -> None:
        for subscription in list(self._subscribers):
            if wanted(subscription):
                subscription.offer(frame)


def _text(payload: Any) -> str:
    if not isinstance(payload, str):
        return ""
    return b64decode(payload.encode("ascii")).decode("utf-8", errors="replace")
