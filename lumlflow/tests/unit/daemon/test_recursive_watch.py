import asyncio
import logging
from concurrent.futures import Future
from pathlib import Path

import pytest
from lumlflow.flow.daemon.watcher import Watches, _Handler
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
)

# The shapes each platform's recursive watch gives a directory leaving the
# tree: ReadDirectoryChangesW cannot tell a removed directory from a file.
_VANISHING = {
    "windows_removed_directory": FileDeletedEvent("/w/lib"),
    "fsevents_moved_out": DirDeletedEvent("/w/lib"),
    "inotify_moved_out": DirDeletedEvent("/w/lib"),
    "moved_within": DirMovedEvent("/w/lib", "/w/node_modules"),
    "renamed_data_file": FileMovedEvent("/w/lib", "/w/lib.old"),
}
_STAYING: dict[str, FileSystemEvent] = {
    "deleted_cell_file": FileDeletedEvent("/w/lib/io.py"),
    "moved_cell_file": FileMovedEvent("/w/lib/io.py", "/w/lib/old.py"),
    "modified": FileModifiedEvent("/w/lib"),
    "created_directory": DirCreatedEvent("/w/lib"),
    "created_file": FileCreatedEvent("/w/raw.csv"),
}


def _handled(event: FileSystemEvent) -> tuple[list[str], list[str]]:
    posted: list[str] = []
    vanished: list[str] = []
    _Handler(posted.append, vanished.append).dispatch(event)
    return posted, vanished


@pytest.mark.parametrize("shape", sorted(_VANISHING))
def test_a_path_leaving_the_tree_is_reported_as_vanished(shape: str) -> None:
    event = _VANISHING[shape]

    posted, vanished = _handled(event)

    assert vanished == [event.src_path]
    assert event.src_path in posted


@pytest.mark.parametrize("shape", sorted(_STAYING))
def test_other_events_report_nothing_vanished(shape: str) -> None:
    event = _STAYING[shape]

    posted, vanished = _handled(event)

    assert vanished == []
    assert event.src_path in posted


async def test_a_failed_watch_job_is_not_reported_again_by_its_waiter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = Path("/w")
    failed: Future[None] = Future()
    failed.set_exception(OSError("placement broke"))
    watches = Watches()
    watches.attach(lambda root: failed, lambda root: None)
    watches.hold(root)

    with caplog.at_level(logging.ERROR, logger="asyncio"):
        await asyncio.wait_for(watches.settled(root), 1.0)
        await asyncio.sleep(0)

    assert [record for record in caplog.records if record.name == "asyncio"] == []


def test_a_released_root_is_forgotten_once_its_work_is_done() -> None:
    first, second = Path("/a"), Path("/b")
    jobs: list[Future[None]] = []

    def queued(root: Path) -> Future[None]:
        jobs.append(Future())
        return jobs[-1]

    watches = Watches()
    watches.attach(queued, queued)
    watches.hold(first)
    watches.release(first)
    while_running = set(watches._pending)
    for job in jobs:
        job.set_result(None)
    watches.hold(second)

    assert while_running == {first}
    assert set(watches._pending) == {second}
