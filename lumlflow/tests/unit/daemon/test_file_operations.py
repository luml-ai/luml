import asyncio
import errno
import os
import struct
import sys
import threading
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import httpx2
import pytest
from lumlflow.cli import app
from lumlflow.flow import cli
from lumlflow.flow.daemon import files, web
from lumlflow.flow.daemon.client import _raised
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.errors import (
    AlreadyExists,
    FlowError,
    FlowOpen,
    NotAFile,
    OsError,
    Protected,
)
from typer.testing import CliRunner

from tests.helpers.daemon import daemon_api, make_workspace


async def test_file_operations_work_outside_the_start_directory(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await api.methods["file.mkdir"]({"directory": str(tmp_path), "name": "plots"})
        result = await api.methods["file.create"](
            {"directory": str(tmp_path), "name": "plot.txt"}
        )
        assert result == {"path": str(tmp_path / "plot.txt")}
        assert Path(result["path"]).read_bytes() == b""
        path = tmp_path / "report.txt"
        assert await api.file_rename({**result, "name": path.name}) == {
            "path": str(path)
        }
        path.write_text("hello")
        moved = await api.file_move(
            {"path": str(path), "destination": str(tmp_path / "plots")}
        )
        assert moved == {"path": str(tmp_path / "plots" / "report.txt")}
        assert not path.exists()
        assert Path(moved["path"]).read_text() == "hello"
        assert await api.file_delete({"path": str(tmp_path / "plots")}) == {
            "path": str(tmp_path / "plots")
        }
        assert not (tmp_path / "plots").exists()


async def test_collisions_invalid_names_and_recursive_moves_leave_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.write_text("original")
    occupied = tmp_path / "taken"
    occupied.write_text("existing")
    folder = tmp_path / "folder"
    (folder / "child").mkdir(parents=True)
    async with daemon_api(tmp_path) as api:
        for method, params in [
            ("file.create", {"directory": str(tmp_path), "name": "taken"}),
            ("file.mkdir", {"directory": str(tmp_path), "name": "taken"}),
            ("file.rename", {"path": str(source), "name": "taken"}),
            ("file.move", {"path": str(occupied), "destination": str(tmp_path)}),
        ]:
            with pytest.raises(AlreadyExists, match='^"taken" already exists$'):
                await api.methods[method](params)
        for name in ["../x", "a/b", r"a\b", "", ".", ".."]:
            with pytest.raises(FlowError):
                await api.file_rename({"path": str(source), "name": name})
        for invalid in [42, ["name"], {"path": "/tmp"}]:
            with pytest.raises(FlowError):
                await api.file_create({"directory": str(tmp_path), "name": invalid})
            with pytest.raises(FlowError):
                await api.file_rename({"path": str(source), "name": invalid})
            with pytest.raises(FlowError):
                await api.file_delete({"path": invalid})
        for destination in [folder, folder / "child"]:
            with pytest.raises(FlowError):
                await api.file_move(
                    {"path": str(folder), "destination": str(destination)}
                )
        with pytest.raises(FlowError, match="absolute"):
            await api.file_delete({"path": "relative"})
    assert source.read_text() == "original"
    assert occupied.read_text() == "existing"


async def test_os_refusals_preserve_the_os_message(tmp_path: Path) -> None:
    path = tmp_path / "data"
    path.touch()
    async with daemon_api(tmp_path) as api:
        with patch.object(
            Path,
            "unlink",
            side_effect=PermissionError(errno.EACCES, "Permission denied"),
        ):
            with pytest.raises(OsError, match="^Permission denied$"):
                await api.file_delete({"path": str(path)})
    assert path.exists()


async def test_root_home_and_ui_directory_are_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    root = make_workspace(home / "project")
    async with daemon_api(root) as api:
        for protected in (Path(root.anchor), root, home, tmp_path, root / ".."):
            for method, params in [
                ("file.delete", {}),
                ("file.move", {"destination": str(tmp_path)}),
                ("file.rename", {"name": "changed"}),
            ]:
                with pytest.raises(Protected):
                    await api.methods[method]({"path": str(protected), **params})


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_symlink_mutations_apply_to_the_entry_even_when_broken(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    target = make_workspace(root / "actual")
    link = root / "data"
    link.symlink_to(target, target_is_directory=True)
    dangling = root / "missing"
    dangling.symlink_to("nonexistent")
    async with daemon_api(root) as api:
        # This open notebook is outside the symlink entry being removed.
        await api.flow_open({"flow": str(target / "churn.flow")})
        with pytest.raises(AlreadyExists):
            await api.file_rename({"path": str(link), "name": dangling.name})
        await api.file_delete({"path": str(link)})
        assert not link.is_symlink()
        assert (target / "churn.flow").is_dir()
        renamed = await api.file_rename({"path": str(dangling), "name": "other"})
        moved = await api.file_move({**renamed, "destination": str(target)})
        assert Path(moved["path"]).readlink() == Path("nonexistent")
        await api.file_delete(moved)
        assert len(api.hub.opened()) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_file_namespace_and_preview_follow_different_symlinks(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    notebook = root / "churn.flow"
    store = root / ".lumlflow"
    store.mkdir()
    directory_link = root / "alias"
    directory_link.symlink_to(notebook, target_is_directory=True)
    data = root / "data"
    data.write_text("public")
    published = root / "published"
    published.symlink_to(data)
    assert files.regular_file(str(published)) == published
    async with daemon_api(root) as api:
        for path in [notebook, store, notebook / "cells", directory_link / "cells"]:
            with pytest.raises(NotAFile):
                await api.file_delete({"path": str(path)})
        for parent in (notebook, store, directory_link):
            with pytest.raises(NotAFile):
                await api.file_create({"directory": str(parent), "name": "report"})
            with pytest.raises(NotAFile):
                await api.file_move({"path": str(data), "destination": str(parent)})
        for parent in (notebook, store):
            private = parent / "private"
            private.touch()
            link = root / "private"
            link.symlink_to(private)
            with pytest.raises(NotAFile):
                files.regular_file(str(link))
            await api.file_delete({"path": str(link)})
            assert private.exists()


@pytest.mark.parametrize("operation", ["file.rename", "file.move", "file.delete"])
async def test_directory_changes_report_and_close_only_affected_notebooks(
    tmp_path: Path, operation: str
) -> None:
    root = make_workspace(tmp_path / "project")
    folder = make_workspace(root / "folder", flows=("a", "b"))
    dest = root / "dest"
    dest.mkdir()
    params = {"path": str(folder), "destination": str(dest), "name": "renamed"}
    async with daemon_api(root) as api:
        for path in (root / "churn.flow", folder / "a.flow", folder / "b.flow"):
            await api.flow_open({"flow": str(path)})
        with pytest.raises(FlowOpen) as error:
            await api.methods[operation](params)
        assert error.value.flows == [
            {"name": name, "path": str(folder / f"{name}.flow"), "session_id": ANY}
            for name in ("a", "b")
        ]
        assert len(api.hub.opened()) == 3
        assert folder.exists()
        await api.methods[operation]({**params, "close_open": True})
        assert [s.ref.name for s in api.hub.opened()] == ["churn"]
        assert not folder.exists()
        if operation != "file.delete":
            location = (
                dest / folder.name if operation == "file.move" else root / "renamed"
            )
            assert (location / "a.flow").is_dir()
            assert api.resolve("a").path == location / "a.flow"


async def test_close_confirmation_excludes_new_sessions(tmp_path: Path) -> None:
    folder = make_workspace(tmp_path / "group", flows=("first", "second"))
    params = {"path": str(folder)}
    async with daemon_api(tmp_path) as api:
        await api.flow_open({"flow": str(folder / "first.flow")})
        with pytest.raises(FlowOpen) as first:
            await api.file_delete(params)
        await api.flow_open({"flow": str(folder / "second.flow")})
        with pytest.raises(FlowOpen) as second:
            await api.file_delete(
                {**params, "close_open": [first.value.flows[0]["session_id"]]}
            )
        assert [row["name"] for row in second.value.flows] == ["first", "second"]
        assert len(api.hub.opened()) == 2
        assert folder.is_dir()
        await api.file_delete(
            {**params, "close_open": [row["session_id"] for row in second.value.flows]}
        )
        assert not folder.exists()


@pytest.mark.parametrize("operation", ["flow.move", "flow.rename", "flow.delete"])
async def test_notebook_operations_require_confirmation(
    tmp_path: Path, operation: str
) -> None:
    root = make_workspace(tmp_path / "project")
    path = root / "churn.flow"
    dest = tmp_path / "dest"
    dest.mkdir()
    params = {"flow": str(path), "destination": str(dest), "name": "sales"}
    async with daemon_api(root) as api:
        await api.flow_open({"flow": str(path)})
        with pytest.raises(FlowOpen) as error:
            await api.methods[operation](params)
        assert error.value.flows == [
            {"name": "churn", "path": str(path), "session_id": ANY}
        ]
        result = await api.methods[operation]({**params, "close_open": True})
        if operation != "flow.delete":
            assert (Path(result["path"]) / ".lumlflow").is_dir()
        assert not path.exists()
        assert not api.hub.opened()


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_notebook_alias_uses_one_session_and_moves_only_link(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    notebook = root / "churn.flow"
    link = root / "alias.flow"
    link.symlink_to(notebook, target_is_directory=True)
    async with daemon_api(root) as api:
        await api.flow_open({"flow": str(link)})
        await api.flow_open({"flow": str(notebook)})
        assert len(api.hub.opened()) == 1
        # The session was opened through the link, so renaming it closes it.
        with pytest.raises(FlowOpen):
            await api.flow_rename({"flow": str(link), "name": "alias2"})
        await api.flow_rename({"flow": str(link), "name": "alias2", "close_open": True})
        assert (root / "alias2.flow").readlink() == notebook
        assert api.hub.opened() == []
        destination = root / "destination"
        destination.mkdir()
        moved = await api.flow_move(
            {"flow": str(root / "alias2.flow"), "destination": str(destination)}
        )
        assert Path(moved["path"]).readlink() == notebook
        with pytest.raises(FlowError, match="is a link"):
            await api.flow_delete({"flow": moved["path"]})
        assert notebook.is_dir()
        assert Path(moved["path"]).is_symlink()


@pytest.mark.parametrize("fail", [False, True])
async def test_cross_device_moves_stage_then_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    root = make_workspace(tmp_path / "project")
    source = root / "data"
    source.mkdir()
    (source / "table").write_text("rows")
    dest = root / "dest"
    dest.mkdir()
    rename = files._rename

    def cross_device(src: Path, target: Path) -> None:
        if src == source:
            raise OSError(errno.EXDEV, os.strerror(errno.EXDEV))
        rename(src, target)

    monkeypatch.setattr(files, "_rename", cross_device)
    async with daemon_api(root) as api:
        if fail:

            def partial_copy(src: Path, target: Path, **kwargs: object) -> None:
                target.mkdir()
                (target / "partial").touch()
                raise OSError(errno.ENOSPC, "No space left on device")

            monkeypatch.setattr(files.shutil, "copytree", partial_copy)
            with pytest.raises(OsError, match="No space left"):
                await api.file_move({"path": str(source), "destination": str(dest)})
            assert not list(dest.iterdir())
            assert (source / "table").read_text() == "rows"
        else:
            await api.file_move({"path": str(source), "destination": str(dest)})
            assert (dest / "data" / "table").read_text() == "rows"
            assert not source.exists()


@pytest.mark.parametrize(
    "flags, answers, confirmations", [([], "y\n", 1), (["--yes"], "", 0)]
)
def test_cli_delete_explicitly_closes_an_open_notebook(flags, answers, confirmations):
    with patch.object(
        cli, "_call", return_value={"deleted": "exp", "path": "/exp.flow"}
    ) as rpc:
        invoked = CliRunner().invoke(
            app, ["flow", "delete", "exp", *flags], input=answers
        )
        assert invoked.exit_code == 0, invoked.output
        assert (
            invoked.output.count("delete `exp` and everything it recorded?")
            == confirmations
        )
        rpc.assert_called_once_with(
            "flow.delete", {"close_open": True}, flow="exp", as_json=False
        )


def test_socket_client_retains_the_open_notebooks() -> None:
    flows = [{"name": "n", "path": "/n.flow"}]
    error = _raised(
        {"message": "close n", "data": {"kind": "FlowOpen", "flows": flows}}
    )
    assert isinstance(error, FlowOpen)
    assert error.flows == flows


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_links_in_a_loop_can_be_removed_and_refuse_reads(tmp_path: Path) -> None:
    loop = tmp_path / "loop"
    loop.symlink_to("loop")
    async with daemon_api(tmp_path) as api:
        with pytest.raises(OsError):
            files.regular_file(str(loop))
        with pytest.raises(OsError):
            await api.file_create({"directory": str(loop), "name": "file"})
        with pytest.raises(OsError):
            await api.file_delete({"path": str(loop / "data")})
        with pytest.raises(OsError):
            await api.flow_move(
                {"flow": str(loop / "data.flow"), "destination": str(tmp_path)}
            )
        await api.file_delete({"path": str(loop)})
    assert not loop.is_symlink()


async def test_http_refusal_names_the_open_notebook(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        app = web.build_app(
            api.hub, api, Streams(), token="local", session_token="ui", static=root
        )
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            response = await client.post(
                web.RPC_PATH,
                headers={web.TOKEN_HEADER: "local"},
                json={"method": "flow.delete", "params": {"flow": "churn"}},
            )
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["kind"] == "FlowOpen"
        assert error["flows"] == [
            {"name": "churn", "path": str(root / "churn.flow"), "session_id": ANY}
        ]


async def test_delete_regular_csv(tmp_path: Path):
    csv = tmp_path / "tmp.csv"
    csv.write_text("x\n1\n")
    async with daemon_api(tmp_path) as api:
        await api.methods["file.delete"]({"path": str(csv)})
    assert not csv.exists()


@pytest.mark.parametrize("fail", [False, True])
async def test_cross_device_regular_file(tmp_path: Path, monkeypatch, fail):
    source = tmp_path / "plot.png"
    content = b"image bytes"
    source.write_bytes(content)
    dest = tmp_path / "external"
    dest.mkdir()
    rename = files._rename

    def cross_device(src, target):
        if src == source and target.parent == dest:
            raise OSError(errno.EXDEV, "Cross-device link")
        rename(src, target)

    def partial_copy(src, target, **kwargs):
        target.write_bytes(content[:3])
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_rename", cross_device)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(source), "destination": str(dest)}
        if fail:
            monkeypatch.setattr(files.shutil, "copy2", partial_copy)
            with pytest.raises(OsError, match="No space left"):
                await api.file_move(params)
            assert source.read_bytes() == content
            assert list(dest.iterdir()) == []
        else:
            await api.file_move(params)
            assert not source.exists()
            assert (dest / source.name).read_bytes() == content
            assert list(dest.iterdir()) == [dest / source.name]


@pytest.mark.parametrize("replace", [True, False])
async def test_cross_device_move_preserves_concurrent_save(
    tmp_path: Path, monkeypatch, replace
):
    source = tmp_path / "notes"
    dest = tmp_path / "external"
    source.write_text("old")
    dest.mkdir()
    rename = files._rename
    take = Path.rename

    def cross_device(src, target):
        if src == source and target.parent == dest:
            raise OSError(errno.EXDEV, "Cross-device link")
        rename(src, target)

    def save_before_detach(src, target):
        if src == source:
            if replace:
                new = tmp_path / "new"
                new.write_text("new work")
                new.replace(source)
            else:
                source.write_text("changed in place")
        return take(src, target)

    monkeypatch.setattr(files, "_rename", cross_device)
    monkeypatch.setattr(Path, "rename", save_before_detach)
    async with daemon_api(tmp_path) as api:
        with pytest.raises(FlowError, match="changed"):
            await api.file_move({"path": str(source), "destination": str(dest)})
    assert source.read_text() == ("new work" if replace else "changed in place")
    assert list(dest.iterdir()) == []


async def test_directory_cleanup_error_identifies_detached_files(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "old"
    source.mkdir()
    (source / "report").write_text("remaining")

    def refuse_cleanup(path):
        assert not source.exists()
        raise PermissionError(errno.EACCES, "Permission denied")

    async with daemon_api(tmp_path) as api:
        with monkeypatch.context() as m:
            m.setattr(files, "_remove_tree", refuse_cleanup)
            with pytest.raises(OsError, match="Permission denied") as refused:
                await api.file_delete({"path": str(source)})
    (remaining,) = tmp_path.rglob("report")
    assert str(remaining.parent.parent) in str(refused.value)
    assert remaining.read_text() == "remaining"


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_notebook_created_through_parent_link_protects_real_parent(
    tmp_path: Path,
):
    parent = tmp_path / "data"
    parent.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    (tmp_path / "alias").symlink_to(parent, target_is_directory=True)
    async with daemon_api(tmp_path) as api:
        await api.flow_init({"name": "alias/run"})
        await api.flow_open({"flow": str(parent / "run.flow")})
        assert len(api.hub.opened()) == 1
        with pytest.raises(FlowOpen) as refused:
            await api.file_move({"path": str(parent), "destination": str(dest)})
        assert refused.value.flows == [
            {"name": "run", "path": str(parent / "run.flow"), "session_id": ANY}
        ]


async def test_slow_move_keeps_daemon_available_and_reserves_paths(
    tmp_path: Path, monkeypatch
):
    source = make_workspace(tmp_path / "data")
    dest = tmp_path / "dest"
    dest.mkdir()
    started = asyncio.Event()
    resume = threading.Event()
    move = files.move
    loop = asyncio.get_running_loop()

    def slow_move(src, target):
        loop.call_soon_threadsafe(started.set)
        assert resume.wait(5)
        move(src, target)

    monkeypatch.setattr(files, "move", slow_move)
    async with daemon_api(tmp_path) as api:
        pending = asyncio.create_task(
            api.file_move({"path": str(source), "destination": str(dest)})
        )
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            await asyncio.wait_for(api.ping({}), timeout=1)
            pending.cancel()  # A disconnected caller still owns its pending move.
            await asyncio.sleep(0)
            with pytest.raises(FlowError, match="busy"):
                await api.flow_open({"flow": str(source / "churn.flow")})
            with pytest.raises(FlowError, match="busy"):
                await api.file_create({"directory": str(dest), "name": source.name})
            with pytest.raises(FlowError, match="busy"):
                await api.file_delete({"path": str(dest)})
        finally:
            resume.set()
            with pytest.raises(asyncio.CancelledError):
                await pending
        await api.flow_open({"flow": str(dest / "data" / "churn.flow")})


def test_case_change_does_not_replace_a_distinct_hard_link(tmp_path):
    tmp_path = tmp_path / "entries"
    tmp_path.mkdir()
    source = tmp_path / "report.md"
    target = tmp_path / "Report.md"
    source.touch()
    if target.exists():
        files.check_destination(source, target)
        files.move(source, target)
        assert os.listdir(tmp_path) == [target.name]
    else:
        os.link(source, target)
        with pytest.raises(AlreadyExists):
            files.check_destination(source, target)
        assert sorted(os.listdir(tmp_path)) == sorted([source.name, target.name])


@pytest.mark.skipif(sys.platform != "linux", reason="Linux mount table")
@pytest.mark.parametrize("move", [False, True])
def test_nested_bind_mount_refuses_operation_before_detach(tmp_path, monkeypatch, move):
    source = tmp_path / "data"
    mounted = source / "mounted"
    mounted.mkdir(parents=True)
    (mounted / "keep").write_text("external data")
    dest = tmp_path / "destination"
    dest.mkdir()
    mounts = tmp_path / "mountinfo"
    mounts.write_text(f"99 30 0:45 /subdir {mounted} rw - tmpfs tmpfs rw\n")
    original_open = Path.open
    monkeypatch.setattr(
        Path,
        "open",
        lambda p, *a, **kw: original_open(
            mounts if p == Path("/proc/self/mountinfo") else p, *a, **kw
        ),
    )
    if move:
        monkeypatch.setattr(
            files,
            "_rename",
            Mock(side_effect=OSError(errno.EXDEV, "Cross-device link")),
        )
    with pytest.raises(OSError, match="mounted filesystem"):
        if move:
            files.move(source, dest / source.name)
        else:
            files.remove(source)
    assert (mounted / "keep").read_text() == "external data"
    assert list(dest.iterdir()) == []


@pytest.mark.skipif(sys.platform != "linux", reason="Linux POSIX default ACL")
def test_cross_device_move_removes_extra_inherited_access(tmp_path, monkeypatch):
    source = tmp_path / "report"
    source.mkdir()
    (source / "data").write_text("restricted")
    dest = tmp_path / "destination"
    dest.mkdir()
    acl = struct.pack("<I", 2) + b"".join(
        struct.pack("<HHI", tag, access, principal)
        for tag, access, principal in [
            (1, 7, 0xFFFFFFFF),
            (4, 0, 0xFFFFFFFF),
            (8, 4, os.getgid() + 1),
            (16, 4, 0xFFFFFFFF),
            (32, 0, 0xFFFFFFFF),
        ]
    )
    os.setxattr(dest, "system.posix_acl_default", acl)
    rename = files._rename

    def cross_device(src, target):
        if src == source:
            raise OSError(errno.EXDEV, "Cross-device link")
        rename(src, target)

    monkeypatch.setattr(files, "_rename", cross_device)
    files.move(source, dest / source.name)
    published = dest / source.name
    assert (published / "data").read_text() == "restricted"
    assert not source.exists()
    for path in [published, published / "data"]:
        assert not {"system.posix_acl_access", "system.posix_acl_default"} & set(
            os.listxattr(path)
        )
