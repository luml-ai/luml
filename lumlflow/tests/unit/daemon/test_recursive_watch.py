import pytest
from lumlflow.flow.daemon.watcher import _Handler
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
