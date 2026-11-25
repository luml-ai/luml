import asyncio
import errno
import os
import stat
import struct
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from lumlflow.flow import atomic
from lumlflow.flow.daemon import files
from lumlflow.flow.daemon.client import _raised
from lumlflow.flow.errors import (
    FileConflict,
    FileLocked,
    FlowError,
    NotAFile,
    NotText,
    OsError,
    TooLarge,
)

from tests.helpers.daemon import daemon_api


def _hidden(folder: Path) -> list[str]:
    """Staging leftovers: every save stages under a dot-name beside the file."""
    return [entry.name for entry in folder.iterdir() if entry.name.startswith(".")]


async def test_read_and_save_utf8_preserves_line_endings_mode_and_precision(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    path = tmp_path / "notes"
    path.write_bytes("β\r\n".encode())
    path.chmod(0o751)
    mode = stat.S_IMODE(path.stat().st_mode)
    stamp = 1_700_000_000_123_456_789
    os.utime(path, ns=(stamp, stamp))
    async with daemon_api(root) as api:
        params = {"path": str(path)}
        edit = await api.methods["file.read_text"](params)
        assert edit["text"] == "β\r\n"
        assert edit["mtime_ns"] == str(path.stat().st_mtime_ns)
        with path.open("rb") as original:
            # Windows may hold the path against replacement while an fd is open.
            if sys.platform == "win32":
                original.close()
            saved = await api.methods["file.write_text"](
                {**params, **edit, "text": "γ\r\n"}
            )
            if not original.closed:
                assert original.read() == "β\r\n".encode()
    assert path.read_bytes() == "γ\r\n".encode()
    assert mode == stat.S_IMODE(path.stat().st_mode)
    assert saved["mtime_ns"] == str(path.stat().st_mtime_ns)
    assert saved["mtime_ns"] != edit["mtime_ns"]


async def test_optimistic_save_conflicts_and_force_overwrites(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("initial")
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        path.write_text("external edit")
        next_stamp = int(params["mtime_ns"]) + 2_000_000_000
        os.utime(path, ns=(next_stamp, next_stamp))
        stamp = str(path.stat().st_mtime_ns)
        with pytest.raises(FileConflict) as conflict:
            await api.file_write_text({**params, "text": "overwrite"})
        assert conflict.value.mtime_ns == stamp
        assert path.read_text() == "external edit"
        saved = await api.file_write_text(
            {**params, "text": "overwrite", "force": True}
        )
        assert saved["mtime_ns"] == str(path.stat().st_mtime_ns)
        assert path.read_text() == "overwrite"


@pytest.mark.parametrize("forced", [True, False])
@pytest.mark.parametrize("name", ["notes.md", "archive.luml"])
async def test_lock_takes_precedence_over_stale_base(tmp_path, forced, name):
    path = tmp_path / name
    path.write_text("agent edit")
    locked = FileLocked("held by Agent", label="Agent")
    async with daemon_api(tmp_path) as api:
        with patch.object(api.file_watcher, "check_write", side_effect=locked) as check:
            with pytest.raises(FileLocked) as refused:
                await api.file_write_text(
                    {
                        "path": str(path),
                        "text": "mine",
                        "mtime_ns": "0",
                        "force": forced,
                    }
                )
        check.assert_called_once_with(path)
        assert refused.value.label == "Agent"
        assert path.read_text() == "agent edit"


@pytest.mark.parametrize(
    "name, contents, kind",
    [
        ("binary", b"a\0b", NotText),
        ("legacy", b"\xff", NotText),
        ("archive.LUML", b"plain text", NotText),
        ("large", None, TooLarge),
    ],
)
async def test_read_and_forced_write_refuse_noneditable_files(
    tmp_path, name, contents, kind
):
    path = tmp_path / name
    contents = contents if contents is not None else b"x" * (files.MAX_TEXT_BYTES + 1)
    path.write_bytes(contents)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path)}
        with pytest.raises(kind):
            await api.file_read_text(params)
        with pytest.raises(kind):
            await api.file_write_text(
                {**params, "mtime_ns": "0", "text": "mine", "force": True}
            )
    assert path.read_bytes() == contents


async def test_size_limit_counts_utf8_bytes_and_applies_to_edits(tmp_path):
    path = tmp_path / "text"
    text = "é" * (files.MAX_TEXT_BYTES // 2)
    path.write_bytes(text.encode())
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path)}
        edit = await api.file_read_text(params)
        assert edit["text"] == text
        for invalid, error in [
            (text + "é", TooLarge),
            ("\0", NotText),
            ("\ud800", NotText),
        ]:
            with pytest.raises(error):
                await api.file_write_text({**params, **edit, "text": invalid})
        assert path.read_bytes() == text.encode()
        await api.file_write_text({**params, **edit, "text": ""})
        assert path.read_bytes() == b""


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_text_operations_follow_links_and_reject_private_targets(tmp_path):
    target = tmp_path / "source"
    target.write_text("initial")
    link = tmp_path / "notes"
    link.symlink_to(target)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(link)}
        edit = await api.file_read_text(params)
        assert edit["text"] == "initial"
        saved = await api.file_write_text({**params, **edit, "text": "updated"})
        assert str(target.stat().st_mtime_ns) == saved["mtime_ns"]
        assert link.readlink() == target
        assert target.read_text() == "updated"
        for directory in [tmp_path / "a.flow", tmp_path / ".lumlflow"]:
            directory.mkdir()
            hidden = directory / "data"
            hidden.write_text("internal")
            link.unlink()
            link.symlink_to(hidden)
            with pytest.raises(NotAFile):
                await api.file_read_text(params)
            with pytest.raises(NotAFile):
                await api.file_write_text(
                    {**params, **edit, "text": "edit", "force": True}
                )


async def test_two_saves_from_same_version_cannot_both_replace_it(tmp_path):
    path = tmp_path / "notes"
    path.touch()
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        saved, refused = await asyncio.gather(
            api.file_write_text({**params, "text": "first"}),
            api.file_write_text({**params, "text": "second"}),
            return_exceptions=True,
        )
    assert isinstance(saved, dict)
    assert isinstance(refused, FileConflict)
    assert refused.mtime_ns == saved["mtime_ns"]
    assert path.read_text() == "first"


async def test_successive_saves_in_one_clock_tick_keep_distinct_versions(
    tmp_path, monkeypatch
):
    path = tmp_path / "notes"
    path.touch()
    stamp = path.stat().st_mtime_ns
    stage = atomic.staged_bytes

    @contextmanager
    def fixed_timestamp(*args, **kwargs):
        with stage(*args, **kwargs) as staged:
            os.utime(staged, ns=(stamp, stamp))
            yield staged

    monkeypatch.setattr(atomic, "staged_bytes", fixed_timestamp)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), "text": "a"}
        edit = await api.file_read_text(params)
        first = await api.file_write_text({**edit, **params})
        second = await api.file_write_text({**params, **first, "text": "b"})
        assert len({str(stamp), first["mtime_ns"], second["mtime_ns"]}) == 3
        with pytest.raises(FileConflict):
            await api.file_write_text({**edit, **params})
    assert path.read_text() == "b"


async def test_read_returns_one_version_when_an_outside_editor_rewrites_in_place(
    tmp_path, monkeypatch
):
    path = tmp_path / "notes"
    path.write_text("before")
    original = path.stat()
    fstat = os.fstat
    changed = False

    def change_after_first_stat(fd):
        nonlocal changed
        info = fstat(fd)
        if not changed and os.path.samestat(info, original):
            changed = True
            path.write_text("after rewrite")
            stamp = info.st_mtime_ns + 2_000_000_000
            os.utime(path, ns=(stamp, stamp))
        return info

    async with daemon_api(tmp_path) as api:
        monkeypatch.setattr(os, "fstat", change_after_first_stat)
        edit = await api.file_read_text({"path": str(path)})
    assert changed
    assert edit["text"] == "after rewrite"
    assert edit["mtime_ns"] == str(path.stat().st_mtime_ns)


async def test_save_checks_for_outside_edits_before_publishing(tmp_path, monkeypatch):
    path = tmp_path / "notes"
    path.write_text("first")
    replace_retry = atomic.replace_retry

    def outside_edit(source, target, **kwargs):
        target.write_text("outside edit")
        replace_retry(source, target, **kwargs)

    monkeypatch.setattr(atomic, "replace_retry", outside_edit)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        with pytest.raises(FileConflict) as refused:
            await api.file_write_text({**params, "text": "mine"})
    assert refused.value.mtime_ns == str(path.stat().st_mtime_ns)
    assert path.read_text() == "outside edit"
    assert not _hidden(tmp_path)


async def test_save_failure_leaves_original_mode_and_data(tmp_path, monkeypatch):
    path = tmp_path / "notes"
    path.write_text("original")
    mode = path.stat().st_mode

    def fail_chmod(self, mode):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "chmod", fail_chmod)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        with pytest.raises(OsError, match="Permission denied"):
            await api.file_write_text({**params, "text": "mine"})
    assert path.stat().st_mode == mode
    assert path.read_text() == "original"
    assert not _hidden(tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX staging folder")
async def test_draft_is_owner_only_until_its_access_matches(tmp_path, monkeypatch):
    path = tmp_path / "notes"
    path.write_text("original")
    path.chmod(0o640)
    preserve = files._preserve_access
    seen = []

    def check_staging(target, staged, info, **kwargs):
        folder = staged.parent
        seen.append(folder)
        assert folder != target.parent
        assert folder.parent == target.parent
        assert stat.S_IMODE(folder.stat().st_mode) & 0o077 == 0
        preserve(target, staged, info, **kwargs)

    monkeypatch.setattr(files, "_preserve_access", check_staging)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        await api.file_write_text({**params, "text": "mine"})
    assert seen
    assert path.read_text() == "mine"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert not _hidden(tmp_path)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS inheritable ACLs")
async def test_draft_inherits_no_aces_from_the_folder(tmp_path, monkeypatch):
    # Mode 0700 does not override an inherited macOS ACE on the staging folder.
    subprocess.run(
        [
            "chmod",
            "+a",
            "everyone allow list,search,read,file_inherit,directory_inherit",
            str(tmp_path),
        ],
        check=True,
    )
    path = tmp_path / "notes"
    path.write_text("original")
    subprocess.run(["chmod", "+a", "user:nobody deny read", str(path)], check=True)
    acl = files._mac_acl(path)
    assert b"inherited" in acl
    preserve = files._preserve_access
    seen = []

    def check_staging(target, staged, info, **kwargs):
        seen.append((files._mac_acl(staged.parent), files._mac_acl(staged)))
        preserve(target, staged, info, **kwargs)

    monkeypatch.setattr(files, "_preserve_access", check_staging)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        await api.file_write_text({**params, "text": "mine"})
    assert seen
    assert all(entry == (b"", b"") for entry in seen)
    assert path.read_text() == "mine"
    assert files._mac_acl(path) == acl


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS inheritable ACLs")
@pytest.mark.parametrize("code", [errno.ENOTSUP, errno.EACCES])
async def test_staging_folder_acl_failure(tmp_path, monkeypatch, code):
    path = tmp_path / "notes"
    path.write_text("original")

    def refuse(target, source):
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(files, "_set_mac_acl", refuse)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        if code == errno.ENOTSUP:  # Nothing to inherit without ACL support.
            await api.file_write_text({**params, "text": "mine"})
            assert path.read_text() == "mine"
        else:
            with pytest.raises(OsError, match="Permission denied"):
                await api.file_write_text({**params, "text": "mine"})
            assert path.read_text() == "original"
    assert not _hidden(tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX staging folder")
async def test_failed_access_copy_leaves_no_staging_folder(tmp_path, monkeypatch):
    path = tmp_path / "notes"
    path.write_text("original")

    def refuse(target, staged, info, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(files, "_preserve_access", refuse)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        with pytest.raises(OsError, match="Permission denied"):
            await api.file_write_text({**params, "text": "mine"})
    assert path.read_text() == "original"
    assert not _hidden(tmp_path)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="POSIX directory mode"
)
async def test_save_into_unwritable_folder_reports_the_os_error(tmp_path):
    folder = tmp_path / "locked"
    folder.mkdir()
    path = folder / "notes"
    path.write_text("original")
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        folder.chmod(0o500)
        try:
            with pytest.raises(OsError, match="Permission denied"):
                await api.file_write_text({**params, "text": "mine"})
        finally:
            folder.chmod(0o700)
    assert path.read_text() == "original"
    assert not _hidden(folder)


async def test_successful_replace_releases_its_temporary_name(tmp_path, monkeypatch):
    path = tmp_path / "notes"
    path.write_text("original")
    replace = atomic.replace_retry

    def reuse_name(source, target, **kwargs):
        replace(source, target, **kwargs)
        source.write_bytes(b"another writer")

    monkeypatch.setattr(atomic, "replace_retry", reuse_name)
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        await api.file_write_text({**params, "text": "replacement"})
    assert path.read_text() == "replacement"
    if sys.platform == "win32":
        (reused,) = tmp_path.glob(".notes.*.tmp")
        assert reused.read_bytes() == b"another writer"
    else:
        # Only the daemon's own user can reach its owner-only staging folder.
        assert not _hidden(tmp_path)


async def test_rejects_invalid_text_rpc_arguments(tmp_path):
    path = tmp_path / "notes"
    path.touch()
    async with daemon_api(tmp_path) as api:
        params = {"path": str(path), **await api.file_read_text({"path": str(path)})}
        for bad in ["relative", [], None]:
            with pytest.raises(FlowError, match="absolute"):
                await api.file_read_text({"path": bad})
        for bad in [None, {}, int(params["mtime_ns"]), 1.5, ""]:
            with pytest.raises(FlowError, match="mtime_ns"):
                await api.file_write_text({**params, "mtime_ns": bad, "force": True})
        for bad in [None, "true", 1]:
            with pytest.raises(FlowError, match="force"):
                await api.file_write_text({**params, "force": bad})
        with pytest.raises(FlowError, match="text must be a string"):
            await api.file_write_text({**params, "text": 2})


def test_socket_error_preserves_the_version_and_lock_label():
    stamp = "1700000000123456789"
    conflict = _raised({"data": {"kind": "FileConflict", "mtime_ns": stamp}})
    assert isinstance(conflict, FileConflict)
    assert conflict.mtime_ns == stamp
    lock = _raised({"data": {"kind": "FileLocked", "label": "Agent"}})
    assert isinstance(lock, FileLocked)
    assert lock.label == "Agent"


async def test_restored_mtime_cannot_hide_a_content_change(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("first")
    stamp = path.stat().st_mtime_ns
    async with daemon_api(tmp_path) as api:
        edit = await api.file_read_text({"path": str(path)})
        path.write_text("other")
        os.utime(path, ns=(stamp, stamp))
        with pytest.raises(FileConflict) as conflict:
            await api.file_write_text({**edit, "path": str(path), "text": "mine"})
        assert conflict.value.mtime_ns == edit["mtime_ns"]
        assert path.read_text() == "other"
        await api.file_write_text(
            {**edit, "path": str(path), "force": True, "text": "mine"}
        )
    assert path.read_text() == "mine"


@pytest.mark.parametrize("new_contents", [b"changed while staged", b"binary\0"])
async def test_overwrite_rechecks_editability_before_publication(
    tmp_path, monkeypatch, new_contents
):
    path = tmp_path / "notes"
    path.write_text("first")
    stage = atomic.staged_bytes

    @contextmanager
    def outside_edit(*args, **kwargs):
        with stage(*args, **kwargs) as staged:
            path.write_bytes(new_contents)
            yield staged

    monkeypatch.setattr(atomic, "staged_bytes", outside_edit)
    async with daemon_api(tmp_path) as api:
        edit = await api.file_read_text({"path": str(path)})
        params = {**edit, "path": str(path), "text": "mine", "force": True}
        if b"\0" in new_contents:
            with pytest.raises(NotText):
                await api.file_write_text(params)
            assert path.read_bytes() == new_contents
        else:
            await api.file_write_text(params)
            assert path.read_text() == "mine"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux POSIX access ACL")
async def test_shared_file_retains_owning_group_restriction(tmp_path):
    path = tmp_path / "shared"
    path.touch()
    # Linux POSIX ACL v2: owner rw, named user r, owning group none, mask r,
    # other none. The group mode bits alone would allow owning-group reads.
    acl = struct.pack("<I", 2) + b"".join(
        struct.pack("<HHI", tag, access, principal)
        for tag, access, principal in [
            (1, 6, 0xFFFFFFFF),
            (2, 4, os.getuid() + 1),
            (4, 0, 0xFFFFFFFF),
            (16, 4, 0xFFFFFFFF),
            (32, 0, 0xFFFFFFFF),
        ]
    )
    key = "system.posix_acl_access"
    try:
        os.setxattr(path, key, acl)
    except OSError as error:
        if error.errno == errno.ENOTSUP:
            pytest.skip("filesystem does not support ACLs")
        raise
    async with daemon_api(tmp_path) as api:
        edit = await api.file_read_text({"path": str(path)})
        await api.file_write_text({**edit, "path": str(path), "text": "saved"})
    assert path.read_text() == "saved"
    assert os.getxattr(path, key) == acl


@pytest.mark.skipif(not hasattr(os, "setxattr"), reason="requires extended attributes")
async def test_text_save_keeps_application_metadata(tmp_path):
    path = tmp_path / "report.md"
    path.write_text("draft")
    os.setxattr(path, "user.application-label", b"reviewed")
    async with daemon_api(tmp_path) as api:
        edit = await api.file_read_text({"path": str(path)})
        await api.file_write_text({**edit, "path": str(path), "text": "ready"})
    assert path.read_text() == "ready"
    assert os.getxattr(path, "user.application-label") == b"reviewed"
