"""No test ever writes to the user's real state directory, and no server a
test started outlives it."""

import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import client
from lumlflow.flow.daemon.workspace import STATE_DIR_ENV
from lumlflow.settings import get_tracker
from lumlflow.tracker import ThreadSafeTracker, TrackerProvider

from tests.servers import reap, stop_recorded

# What a test hands a server process it started by hand, to be ended with it.
Reap = Callable[["subprocess.Popen[Any]"], None]


@pytest.fixture(autouse=True)
def tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TrackerProvider]:
    store = tmp_path / "experiments"
    monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(store))
    monkeypatch.setenv("BACKEND_STORE_URI", str(store))
    provider = get_tracker()
    with provider.bind(ThreadSafeTracker(f"sqlite://{store}")):
        yield provider


@pytest.fixture(autouse=True)
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "state"
    monkeypatch.setenv(STATE_DIR_ENV, str(directory))
    return directory


@pytest.fixture(autouse=True)
def servers(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Reap]:
    """Every server a test starts dies with it, however the test ended.

    Two nets, because either alone has a hole. The discovery record names
    servers no test ever held a handle to — including ones a verb started three
    layers down — and the handles catch the ones whose record a test removed on
    purpose, which is the point of several of them.
    """
    spawned: list[subprocess.Popen[Any]] = []
    spawn = client._spawn

    def watched(root: Path, log: Path) -> "subprocess.Popen[bytes]":
        child = spawn(root, log)
        spawned.append(child)
        return child

    monkeypatch.setattr(client, "_spawn", watched)
    try:
        yield spawned.append
    finally:
        stop_recorded(state_dir)
        for child in spawned:
            reap(child)
