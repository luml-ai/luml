import asyncio
import errno
import json
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from lumlflow.flow.daemon import file_watcher, files, web
from lumlflow.flow.daemon.api import CLAIM_IDLE_S, Leases
from lumlflow.flow.daemon.main import QUIET_AFTER_S, Daemon
from lumlflow.flow.daemon.stream import Frame, Subscription
from lumlflow.flow.errors import FileLocked

from tests.helpers.daemon import make_workspace


@pytest.fixture
async def daemon(tmp_path: Path) -> AsyncIterator[Daemon]:
    daemon = Daemon(tmp_path)
    try:
        yield daemon
    finally:
        await daemon.api.file_watcher.stop()
        await daemon.hub.close()


async def _subscribe(
    daemon: Daemon, directory: Path, file: Path | None = None
) -> Subscription:
    subscription = daemon.streams.subscribe()
    message = {"subscribe": "files", "directory": str(directory)}
    if file is not None:
        message["file"] = str(file)
    subscription.replay(
        await web._subscribed(
            daemon.hub, daemon.api, daemon.streams, subscription, message
        )
    )
    return subscription


def _lease(daemon: Daemon, actor: str, label: str) -> Leases:
    leases: Leases = {(None, actor, label)}
    writer = Mock(spec=asyncio.StreamWriter)
    daemon.api.file_watcher.lease_starting(writer)
    daemon._client_leases[writer] = leases
    return leases


async def _frame(
    subscription: Subscription, kind: str, path: Path | None = None
) -> Frame:
    async with asyncio.timeout(4):
        while True:
            frame = await subscription.next()
            assert frame["channel"] == "files"
            if frame["type"] == kind and (path is None or frame["path"] == str(path)):
                return frame


async def _locks(subscription: Subscription) -> list[Frame]:
    frame = await _frame(subscription, "locks")
    assert frame["idle_after_s"] == 180.0
    return frame["locks"]


async def _snapshot(daemon: Daemon, directory: Path) -> list[Frame]:
    subscription = await _subscribe(daemon, directory)
    try:
        return await _locks(subscription)
    finally:
        subscription.close()


async def test_real_changes_reach_the_listing_and_open_files_parent(
    daemon: Daemon, tmp_path: Path
) -> None:
    listed = tmp_path / "listed"
    listed.mkdir()
    opened = tmp_path / "elsewhere" / "notes.md"
    opened.parent.mkdir()
    opened.touch()
    other = await _subscribe(daemon, listed)
    viewer = await _subscribe(daemon, listed, opened)
    assert await _locks(other) == await _locks(viewer) == []

    opened.write_text("outside the listing")
    changed = await _frame(viewer, "changed")
    assert (changed["directory"], changed["path"]) == (str(opened.parent), str(opened))
    assert await _snapshot(daemon, opened.parent) == []
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(other.next(), 0.05)

    other.close()
    new_file = listed / "table.csv"
    new_file.write_text("a,b")
    assert (await _frame(viewer, "changed"))["path"] == str(new_file)
    viewer.close()


async def test_resubscribe_and_close_release_each_shared_watch_after_its_last_user(
    daemon: Daemon, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    opened = right / "notes.md"
    opened.touch()

    observer = file_watcher.Observer()
    monkeypatch.setattr(file_watcher, "Observer", lambda: observer)

    def watches() -> set[tuple[str, bool]]:
        return {(str(e.watch.path), e.watch.is_recursive) for e in observer.emitters}

    first = await _subscribe(daemon, left, opened)
    second = await _subscribe(daemon, left)
    assert watches() == {(str(left), False), (str(right), False)}
    first.offer({"channel": "files", "type": "changed", "path": str(left / "old")})
    first.replay(
        await web._subscribed(
            daemon.hub,
            daemon.api,
            daemon.streams,
            first,
            {"subscribe": "files", "directory": str(right)},
        )
    )
    assert watches() == {(str(left), False), (str(right), False)}
    assert await _locks(first) == []
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.next(), 0.05)
    second.close()
    assert watches() == {(str(right), False)}
    first.close()
    assert watches() == set()


async def test_disk_writes_are_debounced_and_nested_files_are_ignored(
    daemon: Daemon, tmp_path: Path
) -> None:
    for name in ("nested", ".lumlflow", "analysis.flow"):
        (tmp_path / name).mkdir()
    subscription = await _subscribe(daemon, tmp_path)
    assert await _locks(subscription) == []
    _lease(daemon, "codex-1", "Codex")
    for name in ("nested", ".lumlflow", "analysis.flow"):
        (tmp_path / name / "data.csv").write_text("row")

    path = tmp_path / "report.md"
    path.write_text("first")
    path.write_text("second")
    frames = [await asyncio.wait_for(subscription.next(), 4) for _ in range(2)]
    changed, held = sorted(frames, key=lambda frame: frame["type"])
    assert (changed["type"], changed["path"]) == ("changed", str(path))
    assert held["type"] == "locks"
    assert [row["path"] for row in held["locks"]] == [str(path)]
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(subscription.next(), 0.4)
    subscription.close()


async def test_single_owner_lock_refuses_forced_save_and_lapses_from_last_write(
    daemon: Daemon, tmp_path: Path
) -> None:
    path = tmp_path / "notes.md"
    path.write_text("existing")
    api = daemon.api
    now = 1_000.0
    api.clock = lambda: now
    _lease(daemon, "codex-1", "Codex")
    subscription = await _subscribe(daemon, tmp_path)
    assert await _locks(subscription) == []

    api.file_watcher.notice(path, write=True)
    row = {
        "path": str(path),
        "actor": "codex-1",
        "label": "Codex",
        "last": int(now * 1000),
    }
    assert await _locks(subscription) == [row]
    assert await _snapshot(daemon, tmp_path) == [row]
    with pytest.raises(FileLocked) as refused:
        await api.methods["file.write_text"](
            {"path": str(path), "text": "overwritten", "mtime_ns": "0", "force": True}
        )
    assert refused.value.label == "Codex"
    assert path.read_text() == "existing"

    now += CLAIM_IDLE_S - 1
    api.file_watcher.notice(path, write=True)
    row["last"] = int(now * 1000)
    assert await _locks(subscription) == [row]
    now += CLAIM_IDLE_S - 1
    api.expire_claims()
    assert await _snapshot(daemon, tmp_path) == [row]
    now += 1
    api.expire_claims()
    assert await _locks(subscription) == []
    subscription.close()


@pytest.mark.parametrize("end", ["disconnect", "quiet"])
async def test_an_owned_lock_ends_when_its_agent_leaves_even_if_another_stays(
    daemon: Daemon, tmp_path: Path, end: str
) -> None:
    path = tmp_path / "notes.md"
    path.touch()
    first = _lease(daemon, "first", "First agent")
    subscription = await _subscribe(daemon, tmp_path)
    assert await _locks(subscription) == []
    daemon.api.file_watcher.notice(path, write=True)
    assert (await _locks(subscription))[0]["actor"] == "first"
    _lease(daemon, "second", "Second agent")

    if end == "disconnect":
        await daemon._release(first)
    else:
        daemon.clock = lambda: QUIET_AFTER_S
        daemon._last_call[(None, "first")] = 0.0
        await daemon.end_quiet()
    assert await _locks(subscription) == []
    assert daemon._leases() == {(None, "second", "Second agent")}
    subscription.close()


async def test_generic_lock_is_scoped_and_ends_when_the_last_agent_leaves(
    daemon: Daemon, tmp_path: Path
) -> None:
    path = tmp_path / "listed" / "notes.md"
    path.parent.mkdir()
    path.touch()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    first = _lease(daemon, "first", "First agent")
    second = _lease(daemon, "second", "Second agent")
    daemon.api.clock = lambda: 1_000.0
    viewer = await _subscribe(daemon, path.parent)
    other = await _subscribe(daemon, elsewhere)
    assert await _locks(viewer) == await _locks(other) == []
    daemon.api.file_watcher.notice(path, write=True)
    row = {"path": str(path), "actor": None, "label": "an agent", "last": 1_000_000}
    assert await _locks(viewer) == [row]
    assert await _snapshot(daemon, elsewhere) == []

    await daemon._release(first)
    assert await _snapshot(daemon, path.parent) == [row]
    await daemon._release(second)
    assert await _locks(viewer) == []
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(other.next(), 0.05)
    viewer.close()
    other.close()


async def test_daemon_save_refreshes_without_a_lock_then_an_external_save_locks(
    daemon: Daemon, tmp_path: Path
) -> None:
    path = tmp_path / "notes.md"
    path.write_text("original")
    _lease(daemon, "pair", "Pair")
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    rpc = daemon.api.methods
    original = await rpc["file.read_text"]({"path": str(path)})
    await rpc["file.write_text"]({**original, "path": str(path), "text": "my edit"})
    await _frame(viewer, "changed", path)
    assert await _snapshot(daemon, tmp_path) == []

    path.write_text("agent edit")
    locks = await _locks(viewer)
    assert [(row["path"], row["actor"]) for row in locks] == [(str(path), "pair")]
    viewer.close()


async def test_creating_renaming_and_moving_from_the_daemon_skips_agent_locks(
    daemon: Daemon, tmp_path: Path
) -> None:
    destination = tmp_path / "other"
    destination.mkdir()
    listing = await _subscribe(daemon, tmp_path)
    moved_listing = await _subscribe(daemon, destination)
    assert await _locks(listing) == await _locks(moved_listing) == []
    _lease(daemon, "pair", "Pair")
    rpc = daemon.api.methods

    created = await rpc["file.create"]({"directory": str(tmp_path), "name": "notes.md"})
    await _frame(listing, "changed", Path(created["path"]))
    assert await _snapshot(daemon, tmp_path) == []
    renamed = await rpc["file.rename"]({**created, "name": "log.md"})
    await _frame(listing, "changed", Path(renamed["path"]))
    assert await _snapshot(daemon, tmp_path) == []
    moved = await rpc["file.move"]({**renamed, "destination": str(destination)})
    await _frame(moved_listing, "changed", Path(moved["path"]))
    assert await _snapshot(daemon, destination) == []
    listing.close()
    moved_listing.close()


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_external_target_write_locks_its_open_symlink_for_edits(
    daemon: Daemon, tmp_path: Path
) -> None:
    listed = tmp_path / "listed"
    listed.mkdir()
    target = tmp_path / "external" / "report.md"
    target.parent.mkdir()
    target.write_text("before")
    link = listed / "latest.md"
    link.symlink_to(target)
    viewer = await _subscribe(daemon, listed, link)
    assert await _locks(viewer) == []
    _lease(daemon, "pair", "Pair")
    rpc = daemon.api.methods
    original = await rpc["file.read_text"]({"path": str(link)})
    target.write_text("edited outside")
    await _frame(viewer, "changed", link)
    locks = await _locks(viewer)
    assert (str(link), "pair", "Pair") in [
        (row["path"], row["actor"], row["label"]) for row in locks
    ]
    with pytest.raises(FileLocked):
        await rpc["file.write_text"](
            {
                "path": str(link),
                "text": "overwrite",
                "mtime_ns": original["mtime_ns"],
                "force": True,
            }
        )
    assert link.is_symlink()
    assert target.read_text() == "edited outside"
    viewer.close()


async def test_external_removal_announces_the_missing_file_and_clears_its_lock(
    daemon: Daemon, tmp_path: Path
) -> None:
    path = tmp_path / "notes.md"
    path.write_text("original")
    viewer = await _subscribe(daemon, tmp_path, path)
    assert await _locks(viewer) == []
    _lease(daemon, "pair", "Pair")
    path.write_text("external edit")
    assert [row["path"] for row in await _locks(viewer)] == [str(path)]

    path.unlink()
    await _frame(viewer, "changed", path)
    assert await _locks(viewer) == []
    reconnected = await _subscribe(daemon, tmp_path, path)
    assert await _locks(reconnected) == []
    reconnected.close()
    viewer.close()


async def test_edit_queued_before_socket_lease_stays_unlocked(daemon, tmp_path):
    path = tmp_path / "notes"
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    writer = Mock(spec=asyncio.StreamWriter)
    writer.drain = AsyncMock()
    leased = set()
    daemon._client_leases[writer] = leased
    # Complete registration before yielding to watchdog's queued events.
    daemon.api.methods["agent.begin"] = AsyncMock(
        return_value={
            "actor": "pair",
            "label": "Pair",
            "leased": True,
        }
    )
    path.write_text("my change")
    await daemon._handle(
        json.dumps(
            {
                "method": "agent.begin",
                "params": {"actor": "pair", "lease": True},
            }
        ).encode(),
        writer,
        leased,
    )
    await _frame(viewer, "changed", path)
    assert await _snapshot(daemon, tmp_path) == []
    path.write_text("a later agent edit")
    assert [row["actor"] for row in await _locks(viewer)] == ["pair"]


async def test_same_actor_on_two_sockets_has_distinct_lock_ownership(daemon, tmp_path):
    first = _lease(daemon, "agent", "Pair")
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    owned = tmp_path / "owned"
    owned.write_text("first session")
    assert [row["actor"] for row in await _locks(viewer)] == ["agent"]
    _lease(daemon, "agent", "Pair")
    shared = tmp_path / "shared"
    shared.write_text("two sessions")
    rows = await _locks(viewer)
    assert next(r for r in rows if r["path"] == str(shared))["label"] == "an agent"
    await daemon._release(first)
    assert [(r["path"], r["actor"]) for r in await _locks(viewer)] == [
        (str(shared), None)
    ]


async def test_continuous_writes_publish_while_the_writer_is_active(daemon, tmp_path):
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    _lease(daemon, "pair", "Pair")
    path = tmp_path / "running.log"

    async def append():
        while True:
            with path.open("a") as log:
                log.write("row\n")
            await asyncio.sleep(0.05)

    writer = asyncio.create_task(append())
    try:
        async with asyncio.timeout(1.5):
            await _frame(viewer, "changed", path)
            assert [row["path"] for row in await _locks(viewer)] == [str(path)]
    finally:
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)


@pytest.mark.skipif(
    sys.platform != "linux", reason="inotify distinguishes attrib from write"
)
async def test_touch_updates_viewer_without_locking(daemon, tmp_path):
    path = tmp_path / "notes"
    path.write_text("contents")
    viewer = await _subscribe(daemon, tmp_path, path)
    assert await _locks(viewer) == []
    _lease(daemon, "pair", "Pair")
    stamp = path.stat().st_mtime_ns + 2_000_000_000
    os.utime(path, ns=(stamp, stamp))
    await _frame(viewer, "changed", path)
    assert await _snapshot(daemon, tmp_path) == []


async def test_new_notebook_invalidates_its_directory(daemon, tmp_path):
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    notebook = tmp_path / "analysis.flow"
    notebook.mkdir()
    assert (await _frame(viewer, "changed"))["directory"] == str(tmp_path)
    (notebook / "cell").write_text("internal")
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(viewer.next(), 0.4)


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_retargeted_link_follows_only_the_new_file(daemon, tmp_path):
    left, right = [tmp_path / name / "notes" for name in ("left", "right")]
    for path in (left, right):
        path.parent.mkdir()
        path.touch()
    link = tmp_path / "latest"
    link.symlink_to(left)
    viewer = await _subscribe(daemon, tmp_path, link)
    assert await _locks(viewer) == []
    _lease(daemon, "pair", "Pair")
    left.write_text("locked")
    assert str(link) in {row["path"] for row in await _locks(viewer)}
    link.unlink()
    link.symlink_to(right)
    await _frame(viewer, "changed", link)
    assert await _locks(viewer) == []
    left.write_text("old file")
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(viewer.next(), 0.4)
    right.write_text("new file")
    await _frame(viewer, "changed", link)
    assert str(link) in {row["path"] for row in await _locks(viewer)}


async def test_existing_and_new_subscribers_watch_recreated_directory(daemon, tmp_path):
    directory = tmp_path / "output"
    directory.mkdir()
    first = await _subscribe(daemon, directory)
    assert await _locks(first) == []
    directory.rename(tmp_path / "old")
    directory.mkdir()
    second = await _subscribe(daemon, directory)
    path = directory / "result"
    path.touch()
    for viewer in (first, second):
        await _frame(viewer, "changed", path)


@pytest.mark.parametrize("cross_device", [False, True])
async def test_renamed_lock_follows_file_and_replacement_does_not_inherit_it(
    daemon, tmp_path, monkeypatch, cross_device
):
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    _lease(daemon, "pair", "Pair")
    path = tmp_path / "notes"
    path.write_text("agent edit")
    assert [row["path"] for row in await _locks(viewer)] == [str(path)]
    if cross_device:
        other = tmp_path / "destination"
        other.mkdir()
        rename = files._rename

        def cross_mount(source, target):
            if source == path:
                raise OSError(errno.EXDEV, "Cross-device link")
            rename(source, target)

        monkeypatch.setattr(files, "_rename", cross_mount)
        renamed = await daemon.api.file_move(
            {"path": str(path), "destination": str(other)}
        )
    else:
        renamed = await daemon.api.file_rename({"path": str(path), "name": "renamed"})
    parent = Path(renamed["path"]).parent
    with pytest.raises(FileLocked):
        await daemon.api.file_write_text(
            {**renamed, "mtime_ns": "0", "force": True, "text": "mine"}
        )
    assert [row["path"] for row in await _snapshot(daemon, parent)] == [renamed["path"]]
    viewer.close()
    replacement = Path(renamed["path"])
    replacement.unlink()
    replacement.write_text("unlocked")
    assert await _snapshot(daemon, parent) == []
    await daemon.api.file_write_text(
        {**renamed, "mtime_ns": "0", "force": True, "text": "mine"}
    )


async def test_second_save_stays_unlocked_when_its_event_arrives_after_first_refresh(
    daemon, tmp_path, monkeypatch
):
    path = tmp_path / "notes"
    path.touch()
    _lease(daemon, "pair", "Pair")
    watcher = daemon.api.file_watcher
    # Deliver the two write notices explicitly to control the observer's delay.
    monkeypatch.setattr(watcher, "on_any_event", lambda event: None)
    viewer = await _subscribe(daemon, tmp_path)
    assert await _locks(viewer) == []
    rpc = daemon.api
    edit = await rpc.file_read_text({"path": str(path)})
    first = await rpc.file_write_text({**edit, "path": str(path), "text": "first"})
    watcher.notice(path, write=True)
    await rpc.file_write_text({**first, "path": str(path), "text": "second"})
    await _frame(viewer, "changed", path)
    watcher.notice(path, write=True)
    await _frame(viewer, "changed", path)
    assert await _snapshot(daemon, tmp_path) == []
    assert path.read_text() == "second"


async def test_explicit_session_end_releases_another_connections_lock(daemon, tmp_path):
    root = make_workspace(tmp_path / "project")
    notebook = str(root / "churn.flow")
    path = root / "notes.md"
    path.touch()
    viewer = await _subscribe(daemon, root, path)
    assert await _locks(viewer) == []
    writer = Mock(spec=asyncio.StreamWriter)
    writer.drain = AsyncMock()
    leases = set()
    daemon._client_leases[writer] = leases
    await daemon._handle(
        json.dumps(
            {
                "method": "agent.begin",
                "params": {"actor": "pair", "flow": notebook, "lease": True},
            }
        ).encode(),
        writer,
        leases,
    )
    path.write_text("agent edit")
    assert (await _locks(viewer))[0]["actor"] == "pair"
    await daemon.api.agent_end({"flow": notebook})
    assert await _locks(viewer) == []
    edit = await daemon.api.file_read_text({"path": str(path)})
    await daemon.api.file_write_text({**edit, "path": str(path), "text": "saved"})
    path.write_text("external edit")
    await _frame(viewer, "changed", path)
    assert await _snapshot(daemon, root) == []
