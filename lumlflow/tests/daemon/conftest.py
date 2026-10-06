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
