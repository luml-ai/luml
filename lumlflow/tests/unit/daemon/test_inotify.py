import errno
import logging
import os
import shutil
import sys
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="inotify is Linux only"
)

_TIMEOUT_S = 10.0
_EXCLUDED = (
    "node_modules",
    ".venv",
    ".git",
    ".tox",
    "__pycache__",
    "build",
    "dist",
    "env",
    "venv",
    "lib/site-packages",
    "churn.flow/.lumlflow",
    "ignored",
    "custom-env",
)


class _Recorder:
    def __init__(self) -> None:
        self.posted: list[Path] = []
        self.woken: list[Path] = []
        self._lock = threading.Lock()

    def post(self, path: str) -> None:
        with self._lock:
            self.posted.append(Path(path))

    def wake(self, root: Path) -> None:
        with self._lock:
            self.woken.append(root)

    def saw(self, path: Path) -> bool:
        with self._lock:
            return path in self.posted


@pytest.fixture
def root(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


@pytest.fixture
def recorder() -> _Recorder:
    return _Recorder()


@pytest.fixture
def trees(recorder: _Recorder) -> Iterator[Any]:
    from lumlflow.flow.daemon.inotify import InotifyTrees

    placer = ThreadPoolExecutor(max_workers=1)
    watching = InotifyTrees(
        post=recorder.post,
        wake=recorder.wake,
        submit=placer.submit,
        stopping=threading.Event(),
    )
    yield watching
    placer.shutdown(wait=True)
    watching.stop()


def _workspace(root: Path, *, fanout: int = 4) -> set[Path]:
    """A workspace whose excluded directories are each deep and wide; returns
    the directories a scan of it enters."""
    entered = {root, root / "lib", root / "churn.flow" / "cells"}
    for top in ("src", "churn.flow"):
        for index in range(fanout):
            leaf = root / top / f"part{index}" / "inner"
            leaf.mkdir(parents=True)
            entered |= {root / top, leaf.parent, leaf}
    for directory in entered:
        directory.mkdir(parents=True, exist_ok=True)
    for excluded in _EXCLUDED:
        for index in range(fanout):
            (root / excluded / f"deep{index}" / "deeper").mkdir(parents=True)
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (root / "custom-env" / "pyvenv.cfg").write_text("home = /x\n", encoding="utf-8")
    return entered


def _kernel_watches(trees: Any) -> int:
    fdinfo = Path(f"/proc/self/fdinfo/{trees._inotify._inotify_fd}")
    return sum(line.startswith("inotify") for line in fdinfo.read_text().splitlines())


def _incomplete(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "incomplete" in record.getMessage()
    ]


def _until(ready: Callable[[], bool]) -> None:
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        if ready():
            return
        time.sleep(0.01)
    raise AssertionError("the watches never got there")


def _barrier(recorder: _Recorder, root: Path) -> None:
    """Events reach the recorder in order: once a write made now is posted,
    everything before it has been."""
    marker = root / f"barrier-{len(recorder.posted)}.txt"
    marker.write_text("-", encoding="utf-8")
    _until(lambda: recorder.saw(marker))


def test_only_the_directories_the_scan_enters_are_watched(
    root: Path, trees: Any
) -> None:
    entered = _workspace(root, fanout=20)

    trees.schedule(root)

    assert trees.trees[root].watched() == entered
    assert _kernel_watches(trees) == len(entered)


def test_an_excluded_directory_raises_no_event(
    root: Path, trees: Any, recorder: _Recorder
) -> None:
    _workspace(root)
    trees.schedule(root)

    for excluded in _EXCLUDED:
        (root / excluded / "deep0" / "module.py").write_text("X = 1\n")
    _barrier(recorder, root)

    assert [path for path in recorder.posted if path.suffix == ".py"] == []


def test_a_directory_made_after_scheduling_is_watched_and_its_files_posted(
    root: Path, trees: Any, recorder: _Recorder
) -> None:
    _workspace(root)
    trees.schedule(root)

    made = root / "src" / "fresh" / "nested"
    made.mkdir(parents=True)
    (made / "early.py").write_text("X = 1\n")
    _until(lambda: made in trees.trees[root].watched())
    (made / "late.py").write_text("Y = 1\n")

    _until(lambda: recorder.saw(made / "early.py") and recorder.saw(made / "late.py"))


def test_a_deleted_subtree_takes_its_watches_with_it(root: Path, trees: Any) -> None:
    entered = _workspace(root)
    trees.schedule(root)

    shutil.rmtree(root / "src")
    left = {path for path in entered if not path.is_relative_to(root / "src")}

    _until(lambda: trees.trees[root].watched() == left)
    _until(lambda: _kernel_watches(trees) == len(left))


def test_renaming_into_and_out_of_an_excluded_name_moves_the_watches(
    root: Path, trees: Any
) -> None:
    _workspace(root)
    trees.schedule(root)
    tree = trees.trees[root]
    part = root / "src" / "part0"
    hidden = root / "src" / "node_modules"

    part.rename(hidden)
    _until(lambda: not any(path.is_relative_to(part) for path in tree.watched()))
    under_hidden = {path for path in tree.watched() if path.is_relative_to(hidden)}
    hidden.rename(part)
    _until(lambda: {part, part / "inner"} <= tree.watched())

    assert under_hidden == set()


def test_releasing_a_root_removes_every_watch(root: Path, trees: Any) -> None:
    _workspace(root)
    trees.schedule(root)

    trees.unschedule(root)

    assert _kernel_watches(trees) == 0
    assert trees.trees == {}


def test_nested_roots_share_watches_and_keep_their_own(
    root: Path, trees: Any, recorder: _Recorder
) -> None:
    entered = _workspace(root)
    inner = root / "src"
    trees.schedule(root)
    trees.schedule(inner)
    shared = _kernel_watches(trees)

    trees.unschedule(inner)
    (inner / "part1" / "helpers.py").write_text("X = 1\n")

    _until(lambda: recorder.saw(inner / "part1" / "helpers.py"))
    assert shared == len(entered)
    assert _kernel_watches(trees) == len(entered)
    assert trees.trees[root].watched() == entered


def test_an_overflow_restores_the_watches_and_wakes_the_root(
    root: Path, trees: Any, recorder: _Recorder
) -> None:
    entered = _workspace(root)
    trees.schedule(root)
    tree = trees.trees[root]
    tree.drop(str(root / "src"))

    tree.on_queue_overflow()

    _until(lambda: recorder.woken == [root])
    assert tree.watched() == entered


def test_running_out_of_watches_warns_once_and_keeps_what_it_placed(
    root: Path,
    trees: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from watchdog.observers.inotify_c import InotifyFD

    _workspace(root, fanout=10)
    allowed = 5
    add = InotifyFD.add_callback

    def limited(self: Any, *args: Any) -> Any:
        if _kernel_watches(trees) >= allowed:
            raise OSError(errno.ENOSPC, "inotify watch limit reached")
        return add(self, *args)

    monkeypatch.setattr(InotifyFD, "add_callback", limited)

    with caplog.at_level(logging.WARNING):
        trees.schedule(root)

    assert len(trees.trees[root].watched()) == allowed
    (warning,) = _incomplete(caplog)
    assert str(root) in warning
    assert "inotify watch limit reached" in warning


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads every directory")
def test_an_unreadable_directory_warns_once_and_is_left_out(
    root: Path, trees: Any, caplog: pytest.LogCaptureFixture
) -> None:
    entered = _workspace(root)
    locked = {root / "src" / "part0", root / "src" / "part1"}
    for directory in locked:
        directory.chmod(0)
    try:
        with caplog.at_level(logging.WARNING):
            trees.schedule(root)
    finally:
        for directory in locked:
            directory.chmod(0o755)

    left_out = locked | {path for path in entered if path.parent in locked}
    assert trees.trees[root].watched() == entered - left_out
    assert len(_incomplete(caplog)) == 1


def test_the_watcher_places_per_directory_watches_on_linux() -> None:
    from lumlflow.flow.daemon.inotify import InotifyTrees
    from lumlflow.flow.daemon.watcher import _placement

    placement = _placement(
        post=lambda path: None,
        wake=lambda root: None,
        submit=lambda work: None,
        stopping=threading.Event(),
    )
    try:
        assert isinstance(placement, InotifyTrees)
    finally:
        placement.stop()
