"""The fan-out behind the workbench's two channels.

Channel 1 is durable and replayable — the journal is behind it, so what matters
here is what a client is told and in what order. Channel 2 is not: a run's
chunks exist only while somebody is watching, and the ring buffer is the whole
promise made to a tab opened halfway through one.
"""

import asyncio
from base64 import b64encode
from typing import Any

import pytest
from lumlflow.flow.daemon.stream import QUEUE_DEPTH, Streams, Subscription
from lumlflow.flow.store.models import Transaction

Frame = dict[str, Any]


def transaction(step: int, *, intent: str = "edited score") -> Transaction:
    return Transaction(
        step=step, ts="2026-01-01T00:00:00Z", actor="user", intent=intent, ops=[]
    )


def start(run_id: str, slug: str = "train") -> dict[str, Any]:
    return {"run_id": run_id, "slug": slug}


def log(run_id: str, seq: int, text: str, stream: str = "stdout") -> dict[str, Any]:
    return {
        "run_id": run_id,
        "seq": seq,
        "stream": stream,
        "bytes": b64encode(text.encode("utf-8")).decode("ascii"),
    }


async def frames(subscription: Subscription, count: int) -> list[Frame]:
    """The next `count` frames. A frame that never comes fails rather than
    hangs — dropping one is the failure these tests are looking for."""
    return [await asyncio.wait_for(subscription.next(), 5) for _ in range(count)]


async def quiet(subscription: Subscription) -> None:
    """Nothing else is coming — the difference between filtering and delaying."""
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(subscription.next(), 0.05)


async def test_a_journal_subscriber_gets_the_flow_it_asked_for():
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")

    streams.transaction("churn.flow", transaction(4))

    frame = await watching.next()
    assert frame["channel"] == "journal"
    assert (frame["type"], frame["step"]) == ("transaction", 4)
    assert frame["transaction"]["intent"] == "edited score"


async def test_two_flows_on_one_daemon_do_not_cross():
    """One daemon hosts N flows; a tab open on one is not a tab on the other."""
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")
    watching.runs.add(("churn.flow", "run-1"))

    streams.transaction("churn.flow", transaction(2))
    streams.transaction("sweep.flow", transaction(1))
    streams.kernel("sweep.flow", "log", log("run-1", 0, "elsewhere"), step=1)

    frame = await watching.next()
    assert (frame["flow"], frame["step"]) == ("churn.flow", 2)
    await quiet(watching)


async def test_a_late_joiner_is_served_the_tail_of_a_run():
    """The chunks are off the wire by the time the tab opens. The ring is what
    stands between that and an empty console."""
    streams = Streams()
    for seq, text in enumerate(("epoch 1\n", "epoch 2\n", "epoch 3\n")):
        streams.kernel("churn.flow", "log", log("run-1", seq, text), step=7)

    tail = streams.tail("churn.flow", "run-1")

    assert [frame["text"] for frame in tail] == ["epoch 1\n", "epoch 2\n", "epoch 3\n"]
    assert [frame["seq"] for frame in tail] == [0, 1, 2]
    assert {frame["run_id"] for frame in tail} == {"run-1"}


async def test_the_tail_is_bounded_and_keeps_the_end_of_the_run():
    """A run that prints for an hour must not grow the daemon for an hour."""
    streams = Streams(ring=3)
    for seq in range(10):
        streams.kernel("churn.flow", "log", log("run-1", seq, f"line {seq}\n"), step=1)

    assert [frame["seq"] for frame in streams.tail("churn.flow", "run-1")] == [7, 8, 9]


async def test_only_the_most_recent_runs_keep_a_tail():
    streams = Streams(runs=2)
    for number in range(3):
        streams.kernel("churn.flow", "log", log(f"run-{number}", 0, "x"), step=1)

    assert streams.tail("churn.flow", "run-0") == []
    assert [frame["text"] for frame in streams.tail("churn.flow", "run-2")] == ["x"]


async def test_a_live_watcher_gets_the_chunks_as_they_land():
    streams = Streams()
    watching = streams.subscribe()
    watching.runs.add(("churn.flow", "run-1"))

    streams.kernel("churn.flow", "log", log("run-1", 0, "\x1b[32mok\x1b[0m"), step=3)

    frame = await watching.next()
    # ANSI is preserved: the console renders it, and the stored artifact keeps
    # the same bytes.
    assert (frame["channel"], frame["text"]) == ("logs", "\x1b[32mok\x1b[0m")
    assert (frame["stream"], frame["seq"]) == ("stdout", 0)


async def test_run_lifecycle_rides_channel_one_and_observations_do_not():
    """A client learns a run's `run_id` from channel 1 — which is what it needs
    to subscribe to that run's logs. What the store recorded, it reads back."""
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")

    started = {"run_id": "run-1", "slug": "score"}
    streams.kernel("churn.flow", "started", started, step=6)
    streams.kernel(
        "churn.flow",
        "preview",
        {"run_id": "run-1", "output": "summary", "preview_ref": "0" * 64},
        step=6,
    )
    streams.kernel(
        "churn.flow",
        "materialized",
        {"run_id": "run-1", "state": "succeeded", "cost_seconds": 0.5},
        step=6,
    )

    lifecycle = await frames(watching, 2)
    assert [frame["event"] for frame in lifecycle] == ["started", "materialized"]
    assert (lifecycle[0]["slug"], lifecycle[0]["step"]) == ("score", 6)
    assert lifecycle[1]["cost_seconds"] == 0.5
    assert "preview_ref" not in str(lifecycle)
    await quiet(watching)


async def test_the_kernel_process_state_reaches_the_flows_watchers():
    """The kernel coming up is on channel 1 because nothing journals it.

    A tab is handed the kernel's state once, when it opens, and a kernel starts
    lazily — so without this the workbench keeps saying "kernel not started"
    over a flow whose cells it has watched run.
    """
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")
    elsewhere = streams.subscribe()
    elsewhere.journals.add("sweep.flow")

    streams.kernel("churn.flow", "kernel_state", {"state": "running"}, step=9)
    streams.kernel("churn.flow", "kernel_state", {"state": "stopped"}, step=9)

    said = await frames(watching, 2)
    assert [frame["event"] for frame in said] == ["kernel_state", "kernel_state"]
    assert [frame["kernel"] for frame in said] == ["running", "stopped"]
    assert said[0]["type"] == "kernel"
    assert (said[0]["flow"], said[0]["step"]) == ("churn.flow", 9)
    # One flow's kernel is not another's, and it retires no run.
    await quiet(elsewhere)
    assert streams.running("churn.flow") == []


async def test_a_kernel_state_event_leaves_the_runs_in_flight_alone():
    """It is beside the run lifecycle, not part of it: a kernel announcing
    itself must not look like a run starting or ending."""
    streams = Streams()

    streams.kernel("churn.flow", "started", start("run-1"), step=3)
    streams.kernel("churn.flow", "kernel_state", {"state": "running"}, step=3)

    assert streams.running("churn.flow") == [
        {"run_id": "run-1", "slug": "train", "awaiting": 1}
    ]


async def test_a_catch_up_longer_than_the_queue_still_arrives_whole():
    """Replay is the remedy for lag, so it cannot itself be dropped for lag.

    An overnight return is a client whose cursor is thousands of steps back —
    the case the cursor exists for. Telling it `lagged` would leave it asking
    for the same catch-up forever, and the spec's latency event would become a
    data one.
    """
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")
    behind = QUEUE_DEPTH * 2

    watching.replay(
        streams.journal_frame("churn.flow", transaction(step))
        for step in range(1, behind + 1)
    )

    caught_up = await frames(watching, behind)
    assert [frame["step"] for frame in caught_up] == list(range(1, behind + 1))
    await quiet(watching)


async def test_what_lands_during_a_long_catch_up_follows_it():
    """The client is holding a cursor; frames may not arrive out of order."""
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")

    watching.replay(
        streams.journal_frame("churn.flow", transaction(step))
        for step in range(1, QUEUE_DEPTH + 1)
    )
    streams.transaction("churn.flow", transaction(QUEUE_DEPTH + 1))

    delivered = await frames(watching, QUEUE_DEPTH + 1)
    assert [frame["step"] for frame in delivered] == list(range(1, QUEUE_DEPTH + 2))


async def test_the_runs_in_flight_are_nameable_after_they_started():
    """A run's lifecycle is never journaled, so replay cannot reach it. Without
    this a tab opened mid-run has no `run_id` to ask the ring buffer with."""
    streams = Streams()

    streams.kernel("churn.flow", "started", start("run-1"), step=3)
    streams.kernel("sweep.flow", "started", start("run-2", "score"), step=1)

    assert streams.running("churn.flow") == [
        {"run_id": "run-1", "slug": "train", "awaiting": 1}
    ]

    streams.kernel("churn.flow", "materialized", {"run_id": "run-1"}, step=4)

    assert streams.running("churn.flow") == []
    assert streams.running("sweep.flow") == [
        {"run_id": "run-2", "slug": "score", "awaiting": 1}
    ]


async def test_a_run_that_failed_is_no_longer_in_flight():
    streams = Streams()
    streams.kernel("churn.flow", "started", start("run-1"), step=1)

    streams.kernel(
        "churn.flow", "failed", {"run_id": "run-1", "state": "failed"}, step=2
    )

    assert streams.running("churn.flow") == []


async def test_runs_whose_end_was_never_reported_do_not_pile_up():
    """A kernel that dies mid-run reports no ending — bounded like the tails."""
    streams = Streams(runs=2)
    for number in range(3):
        streams.kernel(
            "churn.flow", "started", {"run_id": f"run-{number}"}, step=number
        )

    assert [entry["run_id"] for entry in streams.running("churn.flow")] == [
        "run-1",
        "run-2",
    ]


async def test_a_client_that_falls_behind_is_told_to_replay_rather_than_torn():
    """Its cursor is still good. Delivering the tail of a sequence it is about
    to ask for again would only arrive twice."""
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")

    for step in range(1, QUEUE_DEPTH + 3):
        streams.transaction("churn.flow", transaction(step))

    assert await watching.next() == {"channel": "journal", "type": "lagged"}

    # Drained: what it was holding is stale by the time it is told to replay.
    streams.transaction("churn.flow", transaction(QUEUE_DEPTH + 3))
    assert (await watching.next())["step"] == QUEUE_DEPTH + 3


async def test_a_closed_subscription_stops_being_delivered_to():
    streams = Streams()
    watching = streams.subscribe()
    watching.journals.add("churn.flow")
    watching.close()

    streams.transaction("churn.flow", transaction(1))

    await quiet(watching)
