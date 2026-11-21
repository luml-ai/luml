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
        submit=lambda root, work: placer.submit(work),
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
        submit=lambda root, work: None,
        stopping=threading.Event(),
    )
    try:
        assert isinstance(placement, InotifyTrees)
    finally:
        placement.stop()


class _Jobs:
    """A placing queue nobody drains until the test says so."""

    def __init__(self) -> None:
        self.queued: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    def submit(self, root: Path, work: Callable[[], None]) -> None:
        with self._lock:
            self.queued.append(work)

    def count(self, wanted: Callable[[], None]) -> int:
        with self._lock:
            return self.queued.count(wanted)

    def drain(self) -> None:
        while True:
            with self._lock:
                if not self.queued:
                    return
                work = self.queued.pop(0)
            work()


@pytest.fixture
def jobs() -> _Jobs:
    return _Jobs()


@pytest.fixture
def held(recorder: _Recorder, jobs: _Jobs) -> Iterator[Any]:
    from lumlflow.flow.daemon.inotify import InotifyTrees

    watching = InotifyTrees(
        post=recorder.post,
        wake=recorder.wake,
        submit=jobs.submit,
        stopping=threading.Event(),
    )
    yield watching
    watching.stop()


def test_upkeep_queued_before_a_release_puts_no_watch_back(
    root: Path, held: Any, jobs: _Jobs
) -> None:
    _workspace(root)
    held.schedule(root)
    tree = held.trees[root]
    (root / "src" / "fresh").mkdir()
    _until(lambda: bool(jobs.queued))
    tree.on_queue_overflow()

    held.unschedule(root)
    jobs.drain()

    assert tree.watched() == set()
    assert _kernel_watches(held) == 0


def test_a_burst_of_pruning_edits_queues_one_resync_and_one_more_while_it_runs(
    root: Path, held: Any, jobs: _Jobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(root)
    held.schedule(root)
    tree = held.trees[root]
    (root / ".gitignore").write_text("ignored/\nbuild/\n", encoding="utf-8")
    for _ in range(3):
        tree.on_queue_overflow()
    _until(lambda: jobs.count(tree.resync) >= 1)
    _barrier_queued(root, jobs)
    queued_by_burst = jobs.count(tree.resync)
    place = tree.place

    def triggering(top: str, *, announce: bool) -> None:
        tree.on_queue_overflow()
        tree.on_queue_overflow()
        place(top, announce=announce)

    monkeypatch.setattr(tree, "place", triggering)
    jobs.queued.remove(tree.resync)
    tree.resync()

    assert (queued_by_burst, jobs.count(tree.resync)) == (1, 1)


def _barrier_queued(root: Path, jobs: _Jobs) -> None:
    """Every event raised so far has been handled once a directory made now
    has queued its placement: the reader handles events in order."""
    before = len(jobs.queued)
    (root / "barrier").mkdir()
    _until(lambda: len(jobs.queued) > before)


def test_a_resync_drops_every_newly_ignored_directory_in_one_pass(
    root: Path, held: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lumlflow.flow.daemon.inotify import TreeWatch

    entered = _workspace(root)
    for index in range(50):
        (root / "generated" / f"run{index}" / "out").mkdir(parents=True)
    held.schedule(root)
    tree = held.trees[root]
    (root / ".gitignore").write_text("ignored/\ngenerated/\n", encoding="utf-8")
    drops: list[tuple[str, ...]] = []
    drop = TreeWatch.drop

    def counted(self: Any, *tops: str) -> None:
        drops.append(tops)
        drop(self, *tops)

    monkeypatch.setattr(TreeWatch, "drop", counted)

    tree.resync()

    assert drops == [(str(root / "generated"),)]
    assert tree.watched() == entered
    assert _kernel_watches(held) == len(entered)


def test_a_stopping_watcher_cuts_a_resync_short(
    root: Path, recorder: _Recorder, jobs: _Jobs
) -> None:
    from lumlflow.flow.daemon.inotify import InotifyTrees

    _workspace(root)
    stopping = threading.Event()
    watching = InotifyTrees(
        post=recorder.post, wake=recorder.wake, submit=jobs.submit, stopping=stopping
    )
    try:
        watching.schedule(root)
        tree = watching.trees[root]
        tree.drop(str(root / "src"))
        stopping.set()

        tree.resync()

        assert not any(path.is_relative_to(root / "src") for path in tree.watched())
        assert recorder.woken == []
    finally:
        watching.stop()


@pytest.mark.parametrize("target", ["src/node_modules", "../elsewhere"])
def test_moving_a_directory_away_wakes_the_root(
    root: Path, trees: Any, recorder: _Recorder, target: str
) -> None:
    _workspace(root)
    trees.schedule(root)

    (root / "lib").rename(root / target)

    _until(lambda: root in recorder.woken)
