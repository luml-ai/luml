"""The two channels a browser watches a workspace through.

*Channel 1 is the journal*: every transaction a hosted flow commits, plus the
kernel's run lifecycle, each stamped with the flow-global `step`. A client
holds that step as its cursor, so catching up is replay from it — a reconnect,
or a laptop opened the next morning, is a latency event and never a data one.
Frames carry their step precisely so a client can ignore what it already has.

*Channel 2 is ephemeral*: the fd-captured chunks of a live run, keyed by
`run_id`. Nothing here is durable — the journal never records chunk streams,
and the capped log artifact on the materialization is what the logs tab
replays. What a ring buffer per run buys is the late joiner: opening a tab
halfway through a ten-minute run shows the tail, not an empty console.

A subscriber that stops reading is not allowed to grow the daemon's memory
until it does. Its live queue is bounded, and a client that overruns it is told
it fell behind rather than served a torn sequence: its cursor is still good,
and replay is what it is for. The replay itself is not bounded that way — the
remedy for falling behind cannot be the thing that gets dropped for being long.
"""

import asyncio
from base64 import b64decode
from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
from typing import Any

from lumlflow.flow.store.models import Transaction

Frame = dict[str, Any]

# Chunks held per run, and runs whose tail is still worth holding. A late
# joiner gets the tail of what it missed, never the whole run — that is the
# log artifact's job, and it is on the materialization already.
RING_CHUNKS = 512
RUNS_KEPT = 8
# How far behind a client may fall before it is told to replay instead.
QUEUE_DEPTH = 1024

# The kernel's run lifecycle, as channel 1 carries it. The observation events
# beside these — previews, inferred kinds, identity and external access — are
# facts about the store that a surface reads back through `asset.preview` and
# `status`; streaming their refs would put content hashes on the wire for no
# reader.
# `awaiting` is the queue's own, not the kernel's: how many branches are
# waiting on the run, which moves while it executes and decides whether a stop
# gesture stops it or only leaves it.
_LIFECYCLE = ("started", "progress", "materialized", "failed", "awaiting")
_LIFECYCLE_FIELDS = ("run_id", "slug", "state", "cost_seconds", "awaiting")
# The kernel process itself coming up or going down. Beside the run lifecycle
# rather than in it: it retires no run and starts none, and a client applies it
# to the flow's state instead of to a run's.
_KERNEL_STATE = "kernel_state"


class Subscription:
    """One connection's view: some flows' journals, some runs' logs, one order.

    Both channels share that order, which is what keeps a connection's frames
    as the daemon produced them and lets one `await` serve a client watching
    two flows at once.

    A catch-up waits apart from the live frames, because the two are bounded by
    opposite facts: the live queue is bounded against a client that stopped
    reading, and a catch-up is what a client that just started is owed in full.
    Draining it first is still that one order — a replay is read the moment its
    channel is attached, so everything live happened after it.
    """

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
        """Hand over a frame, or record that this client is behind."""
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
        """The next frame, or the one that says there is a gap before it."""
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
        """The next frame to send, or None while there is nothing to send.

        What is dropped on lag is everything still queued: the client is about
        to replay from its cursor, and delivering the tail of a sequence it is
        going to ask for again would only arrive twice.
        """
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
    """Every subscriber the daemon fans out to, and the live runs' tails."""

    def __init__(self, *, ring: int = RING_CHUNKS, runs: int = RUNS_KEPT) -> None:
        self._subscribers: list[Subscription] = []
        self._tails: OrderedDict[tuple[str, str], deque[Frame]] = OrderedDict()
        # The runs seen to start and not seen to end, and the cell each is
        # materializing: what a tab that opened mid-run has to be told, since
        # a lifecycle nobody journaled is a lifecycle no cursor replays.
        self._live: OrderedDict[tuple[str, str], str] = OrderedDict()
        # Branches awaiting each run. Kept beside `_live` rather than in it
        # because the queue announces the first waiter before the kernel says
        # the run started, and a count nobody could attach yet is still true.
        self._awaiting: dict[tuple[str, str], int] = {}
        self._ring = ring
        self._runs = runs

    @property
    def watchers(self) -> int:
        """How many connections are being fanned out to right now."""
        return len(self._subscribers)

    def subscribe(self) -> Subscription:
        subscription = Subscription(self)
        self._subscribers.append(subscription)
        return subscription

    def drop(self, subscription: Subscription) -> None:
        if subscription in self._subscribers:
            self._subscribers.remove(subscription)

    def transaction(self, flow: str, transaction: Transaction) -> None:
        """A commit, as channel 1 carries it. The store calls this itself."""
        self._deliver(
            lambda subscription: flow in subscription.journals,
            self.journal_frame(flow, transaction),
        )

    def kernel(
        self, flow: str, event: str, params: dict[str, Any], *, step: int
    ) -> None:
        """A kernel event: log chunks to channel 2, the run's lifecycle to 1."""
        if event == "log":
            self._chunk(flow, params)
            return
        if event == _KERNEL_STATE:
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
        """What a late joiner missed of a run, as far back as the ring holds."""
        return list(self._tails.get((flow, run_id)) or ())

    def running(self, flow: str) -> list[dict[str, Any]]:
        """The runs in flight on a flow, oldest first.

        The `run_id` here is what makes the ring reachable: a client that was
        not connected when the run started learns of it from its catch-up
        rather than from an event it was not there for.
        """
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

    def _track(self, flow: str, event: str, params: dict[str, Any]) -> None:
        """Follow a run from `started` to whichever way it ended.

        Bounded like the tails are, because a kernel that dies mid-run reports
        no ending at all: an entry nobody retired ages out rather than staying
        as long as the daemon does.
        """
        key = (flow, str(params.get("run_id") or ""))
        if event in ("materialized", "failed"):
            self._live.pop(key, None)
            self._awaiting.pop(key, None)
            return
        if event == "awaiting":
            waiting = int(params.get("awaiting") or 0)
            # Nobody left waiting means the flight is being preempted, and it
            # may never reach a kernel event that would have retired it.
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
    """The chunk as a console renders it, ANSI and all.

    Decoded the way the stored log artifact is read back, so the live console
    and the logs tab of the same run say the same thing.
    """
    if not isinstance(payload, str):
        return ""
    return b64decode(payload.encode("ascii")).decode("utf-8", errors="replace")
