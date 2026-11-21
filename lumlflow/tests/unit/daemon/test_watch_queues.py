import threading
from pathlib import Path

from lumlflow.flow.daemon.watcher import _RootQueues

_TIMEOUT_S = 10.0


def test_one_roots_blocked_job_holds_up_neither_another_root_nor_its_order() -> None:
    queues = _RootQueues()
    first, second = Path("/a"), Path("/b")
    release = threading.Event()
    ran: list[str] = []
    try:
        blocked = queues.submit(
            first, lambda: (release.wait(_TIMEOUT_S), ran.append("a1"))
        )
        after = queues.submit(first, lambda: ran.append("a2"))
        other = queues.submit(second, lambda: ran.append("b1"))

        other.result(_TIMEOUT_S)
        waiting = (blocked.done(), after.done())
        release.set()
        after.result(_TIMEOUT_S)
    finally:
        release.set()
        queues.stop()

    assert waiting == (False, False)
    assert ran == ["b1", "a1", "a2"]


def test_stopping_cancels_what_is_queued_and_waits_for_what_runs() -> None:
    queues = _RootQueues()
    root = Path("/a")
    entered, release = threading.Event(), threading.Event()

    def running() -> None:
        entered.set()
        release.wait(_TIMEOUT_S)

    current = queues.submit(root, running)
    queued = queues.submit(root, lambda: None)
    assert entered.wait(_TIMEOUT_S)
    stopper = threading.Thread(target=queues.stop)
    stopper.start()
    release.set()
    stopper.join(_TIMEOUT_S)

    assert not stopper.is_alive()
    assert current.done() and not current.cancelled()
    assert queued.cancelled()
    assert queues.submit(root, lambda: None).cancelled()
    assert not [
        thread for thread in threading.enumerate() if thread.name == "lumlflow-watch"
    ]


def test_a_failing_job_does_not_stop_its_root_queue() -> None:
    queues = _RootQueues()
    root = Path("/a")

    def failing() -> None:
        raise RuntimeError("placement broke")

    try:
        broken = queues.submit(root, failing)
        after = queues.submit(root, lambda: None)
        after.result(_TIMEOUT_S)
    finally:
        queues.stop()

    assert isinstance(broken.exception(_TIMEOUT_S), RuntimeError)
