import logging
import os
import sys
from itertools import count
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="inotify is Linux only"
)


class _FakeInotifyFD:
    def __init__(self) -> None:
        self._descriptors = count(1)

    def add_callback(self, path: bytes, mask: Any, callback: Any, id: Any) -> int:
        return next(self._descriptors)

    def remove_callbacks(self, callbacks: Any) -> None:
        pass


def _group(root: Path) -> Any:
    from lumlflow.flow.daemon.inotify import TolerantWatchGroup

    return TolerantWatchGroup(
        _FakeInotifyFD(),  # type: ignore[arg-type]
        os.fsencode(root),
        is_recursive=True,
    )


def test_a_directory_that_appears_before_its_watch_is_left_to_its_own_event(
    tmp_path: Path,
) -> None:
    group = _group(tmp_path)
    flow = tmp_path / "sales.flow"
    flow.mkdir()
    group._add_callback(os.fsencode(flow))
    (flow / ".lumlflow" / "previews").mkdir(parents=True)
    (flow / ".lumlflow" / "previews" / "cell.png").write_bytes(b"")

    events = group._recursive_simulate(os.fsencode(flow))

    assert [event.name for event in events] == [b".lumlflow"]


def test_a_tree_gone_before_it_is_walked_simulates_nothing(tmp_path: Path) -> None:
    group = _group(tmp_path)

    assert group._recursive_simulate(os.fsencode(tmp_path / "gone")) == []


def test_a_failing_event_is_logged_and_not_raised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from watchdog.observers.inotify import InotifyWatchGroup
    from watchdog.observers.inotify_c import InotifyConstants, InotifyEvent

    def fail(self: Any, event: Any) -> None:
        raise KeyError(b"previews")

    monkeypatch.setattr(InotifyWatchGroup, "on_event", fail)
    group = _group(tmp_path)

    with caplog.at_level(logging.ERROR):
        group.on_event(InotifyEvent(1, InotifyConstants.IN_CREATE, 0, b"cell.py"))

    assert "dropped an inotify event" in caplog.text


def test_the_watcher_uses_the_tolerant_observer() -> None:
    from lumlflow.flow.daemon.inotify import TolerantInotifyObserver
    from lumlflow.flow.daemon.watcher import _observer

    assert isinstance(_observer(), TolerantInotifyObserver)
