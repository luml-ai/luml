"""Path rules and local filesystem operations shared by the workspace transports."""

import asyncio
import ctypes
import errno
import hashlib
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from lumlflow.flow import atomic
from lumlflow.flow.errors import (
    AlreadyExists,
    FileConflict,
    FlowError,
    NotAFile,
    NotText,
    OsError,
    Protected,
    TooLarge,
)
from lumlflow.flow.store.flowstore import FLOW_SUFFIX, STORE_DIRNAME

MAX_TEXT_BYTES = 2 * 1024 * 1024


async def finish_operation(work: Awaitable[object]) -> None:
    """Keep filesystem reservations and cleanup alive if the caller disconnects."""
    task = asyncio.ensure_future(work)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


@contextmanager
def os_errors() -> Generator[None]:
    try:
        yield
    except FileExistsError as error:
        name = Path(error.filename2 or error.filename).name
        raise AlreadyExists(f'"{name}" already exists') from error
    except OSError as error:
        raise OsError(error.strerror or str(error)) from error


def valid_name(name: object) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or any(char in name for char in ("/", "\\", "\0"))
        or Path(name).drive
    ):
        raise FlowError(f"`{name}` is not a single path component")
    return name


def absolute_path(path: object) -> Path:
    if not isinstance(path, str) or "\0" in path or not Path(path).is_absolute():
        raise FlowError("an absolute path is required")
    return Path(path)


def _resolve(path: Path, *, strict: bool = True) -> Path:
    try:
        return path.resolve(strict=strict)
    except RuntimeError as loop:
        # Python 3.12 reports symlink loops as RuntimeError instead of ELOOP.
        raise OSError(errno.ELOOP, os.strerror(errno.ELOOP), str(path)) from loop


def entry_path(path: Path, *, strict: bool = True) -> Path:
    """Resolve the parent while keeping the named directory entry itself."""
    with os_errors():
        if path.name == "..":
            return _resolve(path, strict=strict)
        return _resolve(path.parent, strict=strict) / path.name


def _ordinary(path: Path, *, directory: bool = False) -> None:
    if (
        STORE_DIRNAME in path.parts
        or any(
            parent.name.endswith(FLOW_SUFFIX)
            and (not parent.is_symlink() or _resolve(parent).name.endswith(FLOW_SUFFIX))
            for parent in path.parents
        )
        or (directory and path.name.endswith(FLOW_SUFFIX))
    ):
        raise NotAFile(f"`{path}` belongs to a notebook or its store")


def ordinary_entry(path: str, *, strict: bool = True) -> Path:
    raw = absolute_path(path)
    with os_errors():
        _ordinary(raw)
        value = entry_path(raw, strict=strict)
        _ordinary(value)
        return value


def item_path(path: str) -> Path:
    """Preserve the leaf, including broken symlinks, for directory-entry operations."""
    value = ordinary_entry(path)
    with os_errors():
        mode = value.lstat().st_mode
        if stat.S_ISDIR(mode):
            _ordinary(value, directory=True)
        if (
            stat.S_ISLNK(mode)
            and value.is_dir()
            and _resolve(value).name.endswith(FLOW_SUFFIX)
        ):
            raise NotAFile(f"`{value}` links to a notebook")
        return value


def _regular_target(value: Path) -> Path:
    with os_errors():
        target = _resolve(value)
        _ordinary(target)
        if not stat.S_ISREG(target.stat().st_mode):
            raise NotAFile(f"`{value}` is not a regular file")
        return target


def regular_file(path: str) -> Path:
    value = item_path(path)
    _regular_target(value)
    return value


def text_target(path: str, check_lock: Callable[[Path], None] | None = None) -> Path:
    entry = item_path(path)
    target = _regular_target(entry)
    if check_lock is not None:
        check_lock(target)
    if ".luml" in {entry.suffix.lower(), target.suffix.lower()}:
        raise NotText(f"`{entry}` is a .luml archive")
    return target


def _check_text(data: bytes) -> None:
    if len(data) > MAX_TEXT_BYTES:
        raise TooLarge("text files must be at most 2 MB")
    if b"\0" in data:
        raise NotText("text files cannot contain NUL bytes")


def _conflict(path: Path, info: os.stat_result) -> FileConflict:
    return FileConflict(f"`{path}` changed on disk", mtime_ns=str(info.st_mtime_ns))


def _same_version(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        os.path.samestat(before, after)
        and before.st_ctime_ns == after.st_ctime_ns
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_size == after.st_size
        and before.st_mode == after.st_mode
    )


def read_text(
    path: Path,
    *,
    for_write: bool = False,
    expected: str | None = None,
    revision: str | None = None,
) -> tuple[str, os.stat_result, str]:
    # A concurrent rename must not pair the bytes of one file with the timestamp
    # of its successor. Nonblocking open also handles a regular file becoming a FIFO.
    flags = os.O_RDWR if for_write else os.O_RDONLY
    flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0)
    with os_errors(), os.fdopen(os.open(path, flags), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise NotAFile(f"`{path}` is not a regular file")
        # If an in-place edit overlaps the read, take one fresh snapshot.
        for _ in range(2):
            if expected is not None and expected != str(info.st_mtime_ns):
                raise _conflict(path, info)
            if info.st_size > MAX_TEXT_BYTES:
                if revision is not None:
                    raise _conflict(path, info)
                raise TooLarge("text files must be at most 2 MB")
            data = handle.read(MAX_TEXT_BYTES + 1)
            after = os.fstat(handle.fileno())
            if _same_version(info, after):
                break
            handle.seek(0)
            info = after
        else:
            if expected is not None:
                raise _conflict(path, info)
            raise FlowError(f"`{path}` kept changing while it was read")
        digest = hashlib.sha256(data).hexdigest()
        if revision is not None and revision != digest:
            raise _conflict(path, info)
        _check_text(data)
        try:
            return data.decode("utf-8"), info, digest
        except UnicodeDecodeError as error:
            raise NotText("text files must be UTF-8") from error


def _attributes(path: Path, *, moving: bool) -> dict[str, bytes]:
    # User labels and ACLs can be present on both files and directories.
    return {
        key: os.getxattr(path, key, follow_symlinks=False)
        for key in os.listxattr(path, follow_symlinks=False)
        if key.startswith("user.")
        or (key.startswith("system.") and "acl" in key)
        or (moving and key.startswith("security."))
    }


def _mac_acl(path: Path) -> bytes:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.acl_get_link_np.restype = ctypes.c_void_p
    acl = libc.acl_get_link_np(os.fsencode(path), 0x100)  # ACL_TYPE_EXTENDED
    if not acl:
        code = ctypes.get_errno()
        if code == errno.ENOENT:  # No extended ACL on this entry.
            return b""
        raise OSError(code, os.strerror(code))
    try:
        libc.acl_to_text.restype = ctypes.c_void_p
        text = libc.acl_to_text(ctypes.c_void_p(acl), None)
        if not text:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        try:
            return ctypes.string_at(text)
        finally:
            libc.acl_free(ctypes.c_void_p(text))
    finally:
        libc.acl_free(ctypes.c_void_p(acl))


def _preserve_access(
    path: Path, staged: Path, info: os.stat_result, *, moving: bool = False
) -> None:
    link = stat.S_ISLNK(info.st_mode)
    denied = PermissionError(
        errno.EACCES, f"cannot preserve access controls for {path}"
    )
    if sys.platform == "win32":
        # A sibling inherits its parent's security descriptor. Check that its
        # owner, group and DACL match before replacing the destination.
        from ctypes import wintypes

        def security(file: Path) -> bytes:
            required = wintypes.DWORD()
            get_security = ctypes.windll.advapi32.GetFileSecurityW
            flags = 0x7  # OWNER | GROUP | DACL_SECURITY_INFORMATION
            get_security(str(file), flags, None, 0, ctypes.byref(required))
            buffer = ctypes.create_string_buffer(required.value)
            if not get_security(
                str(file), flags, buffer, len(buffer), ctypes.byref(required)
            ):
                raise ctypes.WinError()
            return buffer.raw

        if link:
            raise denied  # GetFileSecurityW would follow the reparse point.
        descriptor = security(path)
        if descriptor != security(staged):
            if not moving or not ctypes.windll.advapi32.SetFileSecurityW(
                str(staged), 0x7, ctypes.create_string_buffer(descriptor)
            ):
                raise denied
            if security(staged) != descriptor:
                raise denied
        staged.chmod(stat.S_IMODE(info.st_mode))
    else:
        temp = staged.lstat()
        if (temp.st_uid, temp.st_gid) != (info.st_uid, info.st_gid):
            os.chown(staged, info.st_uid, info.st_gid, follow_symlinks=False)
        if not link:
            staged.chmod(stat.S_IMODE(info.st_mode))
        if sys.platform == "darwin":
            libc = ctypes.CDLL(None, use_errno=True)
            # COPYFILE_ACL | COPYFILE_XATTR | COPYFILE_NOFOLLOW
            if libc.copyfile(
                os.fsencode(path), os.fsencode(staged), None, 1 | 4 | (3 << 18)
            ):
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code))
            if moving and _mac_acl(path) != _mac_acl(staged):
                raise denied
        elif hasattr(os, "listxattr"):
            source = _attributes(path, moving=moving)
            inherited = _attributes(staged, moving=moving)
            for key in inherited.keys() - source.keys():
                os.removexattr(staged, key, follow_symlinks=False)
            for key, value in source.items():
                if inherited.get(key) != value:
                    os.setxattr(staged, key, value, follow_symlinks=False)
            if _attributes(staged, moving=moving) != source:
                raise denied
        else:
            raise OSError(errno.ENOTSUP, "cannot preserve file access controls")
    actual = staged.lstat()
    if (actual.st_uid, actual.st_gid, actual.st_mode) != (
        info.st_uid,
        info.st_gid,
        info.st_mode,
    ):
        raise denied


def write_text(
    path: Path,
    text: object,
    mtime_ns: object,
    revision: object,
    *,
    force: object,
    check_lock: Callable[[Path], None],
) -> tuple[os.stat_result, str]:
    if not isinstance(force, bool):
        raise FlowError("force must be a boolean")
    if not isinstance(mtime_ns, str) or not re.fullmatch(r"-?[0-9]+", mtime_ns):
        raise FlowError("mtime_ns must be a decimal string from file.read_text")
    expected_mtime = expected_revision = None
    if not force:
        if not isinstance(revision, str):
            raise FlowError("revision must be a string from file.read_text")
        expected_mtime = mtime_ns
        expected_revision = revision
    read_text(path, for_write=True, expected=expected_mtime, revision=expected_revision)
    if not isinstance(text, str):
        raise FlowError("text must be a string")
    if len(text) > MAX_TEXT_BYTES:
        raise TooLarge("text files must be at most 2 MB")
    try:
        data = text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise NotText("text files must be UTF-8") from error
    _check_text(data)

    with os_errors(), atomic.staged_bytes(path, data) as staged:
        info = staged.stat()

        def prepare() -> None:
            nonlocal info
            for _ in range(3):
                check_lock(path)
                _, current, _ = read_text(
                    path,
                    for_write=True,
                    expected=expected_mtime,
                    revision=expected_revision,
                )
                if sys.platform == "win32":
                    # CopyFileW retains extended attributes and named streams.
                    # Only replace the unnamed data stream with the edited bytes.
                    if not ctypes.windll.kernel32.CopyFileW(
                        str(path), str(staged), False
                    ):
                        raise ctypes.WinError()
                    with staged.open("wb") as output:
                        output.write(data)
                        output.flush()
                        os.fsync(output.fileno())
                _preserve_access(path, staged, current)
                info = staged.stat()
                if info.st_mtime_ns <= current.st_mtime_ns:
                    # FAT timestamps can be two seconds apart.
                    for increment in (1, 2_000_000_000):
                        os.utime(
                            staged,
                            ns=(info.st_atime_ns, current.st_mtime_ns + increment),
                        )
                        info = staged.stat()
                        if info.st_mtime_ns > current.st_mtime_ns:
                            break
                    else:
                        raise FlowError("could not advance the file modification time")
                after = path.lstat()
                if _same_version(current, after):
                    break
                if not force:
                    raise _conflict(path, after)
            else:
                raise FlowError(f"`{path}` kept changing during the save")

        atomic.replace_retry(staged, path, before_replace=prepare)
    atomic.fsync_dir(path.parent)
    return info, hashlib.sha256(data).hexdigest()


def directory_path(path: str) -> Path:
    value = item_path(path)
    with os_errors():
        resolved = _resolve(value)
        _ordinary(resolved, directory=True)
        if not stat.S_ISDIR(resolved.stat().st_mode):
            raise NotAFile(f"`{value}` is not a directory")
        return resolved


def check_protected(path: Path, ui_directories: set[Path]) -> None:
    with os_errors():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            return
        protected = ui_directories | {Path.home().resolve(), Path(path.anchor)}
        for folder in protected:
            for ancestor in (folder, *folder.parents):
                try:
                    if os.path.samestat(info, ancestor.stat()):
                        raise Protected(f"`{path}` is protected")
                except FileNotFoundError:
                    continue


def target_path(parent: Path, name: str, *, directory: bool) -> Path:
    target = parent / valid_name(name)
    _ordinary(target, directory=directory)
    return target


def create(target: Path, *, folder: bool) -> os.stat_result | None:
    with os_errors():
        if folder:
            target.mkdir()
            return None
        with target.open("xb") as handle:
            return os.fstat(handle.fileno())


def _case_change(source: Path, target: Path) -> bool:
    if (
        source.parent != target.parent
        or source.name == target.name
        or source.name.casefold() != target.name.casefold()
    ):
        return False
    # samefile alone also accepts distinct hard links. Directory enumeration
    # gives the stored spelling even when lookup ignores case.
    return os.path.samestat(
        source.lstat(), target.lstat()
    ) and target.name not in os.listdir(source.parent)


def check_destination(source: Path, target: Path) -> None:
    if target.parent.is_relative_to(source):
        raise FlowError("a folder cannot be moved into itself or its contents")
    try:
        target.lstat()
    except FileNotFoundError:
        return
    if not _case_change(source, target):
        raise AlreadyExists(f'"{target.name}" already exists')


def remove(source: Path) -> None:
    if not stat.S_ISDIR(source.lstat().st_mode):
        source.unlink()
        return
    _check_mounts(source)
    holding = _detach(source, prefix=".delete-")
    try:
        _remove_tree(holding)
    except OSError as error:
        raise OsError(f"could not finish deleting {holding}: {error}") from error


def _check_mounts(root: Path) -> None:
    if sys.platform == "linux":
        # st_dev and ismount both miss same-filesystem bind mounts.
        with Path("/proc/self/mountinfo").open("rb") as mounts:
            for line in mounts:
                name = re.sub(
                    rb"\\([0-7]{3})", lambda m: bytes([int(m[1], 8)]), line.split()[4]
                )
                if Path(os.fsdecode(name)).is_relative_to(root):
                    raise OSError(
                        errno.EBUSY,
                        f"cannot remove mounted filesystem at {os.fsdecode(name)}",
                    )
        return
    pending = [root]
    while pending:
        path = pending.pop()
        if path.is_symlink():
            continue
        if path.is_mount() or path.is_junction():
            raise OSError(errno.EBUSY, f"cannot remove mounted filesystem at {path}")
        if path.is_dir():
            pending.extend(path.iterdir())


def _mount_id(fd: int) -> int:
    if sys.platform == "linux":
        with Path(f"/proc/self/fdinfo/{fd}").open() as info:
            for line in info:
                if line.startswith("mnt_id:"):
                    return int(line.split()[1])
        raise OSError(errno.ENOTSUP, "could not verify mount boundary")
    return os.fstat(fd).st_dev


def _remove_tree(root: Path) -> None:
    if os.name == "nt":
        # Windows volume mounts are reparse points. rmtree does not descend
        # into junctions, including ones that appeared after the initial check.
        _check_mounts(root)
        shutil.rmtree(root)
        return

    def clear(fd: int, mount: int) -> None:
        with os.scandir(fd) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    child = os.open(entry.name, flags, dir_fd=fd)
                    try:
                        if _mount_id(child) != mount:
                            raise OSError(
                                errno.EBUSY,
                                f"cannot remove mounted directory {entry.name}",
                            )
                        clear(child, mount)
                    finally:
                        os.close(child)
                    os.rmdir(entry.name, dir_fd=fd)
                else:
                    os.unlink(entry.name, dir_fd=fd)

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(root.parent, flags)
    try:
        fd = os.open(root.name, flags, dir_fd=parent)
        try:
            mount = _mount_id(parent)
            if _mount_id(fd) != mount:
                raise OSError(errno.EBUSY, f"cannot remove mounted directory {root}")
            clear(fd, mount)
        finally:
            os.close(fd)
        os.rmdir(root.name, dir_fd=parent)
    finally:
        os.close(parent)


def _detach(source: Path, *, prefix: str) -> Path:
    holding = Path(tempfile.mkdtemp(dir=source.parent, prefix=prefix))
    try:
        source.rename(holding / "original")
    except BaseException:
        holding.rmdir()
        raise
    return holding


def _rename(source: Path, target: Path) -> None:
    """Atomic no-overwrite rename, including when another process creates the target."""
    if sys.platform == "win32":
        source.rename(target)  # Windows rename already refuses existing names.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "linux" and hasattr(libc, "renameat2"):
        # AT_FDCWD, RENAME_NOREPLACE (renameat2 has no stdlib binding).
        result = libc.renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    elif sys.platform == "darwin":
        result = libc.renamex_np(os.fsencode(source), os.fsencode(target), 4)
    else:
        raise OSError(errno.ENOTSUP, os.strerror(errno.ENOTSUP))
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _versions(root: Path) -> dict[Path, tuple[int, ...]]:
    """Record the identities and versions of entries without following links."""
    versions: dict[Path, tuple[int, ...]] = {}
    pending = [root]
    while pending:
        path = pending.pop()
        info = path.lstat()
        versions[path.relative_to(root)] = (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_size,
            info.st_mtime_ns,
            # Detaching changes the root's ctime. Descendants keep theirs.
            info.st_ctime_ns if path != root else 0,
        )
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
    return versions


def move(source: Path, target: Path) -> tuple[os.stat_result, os.stat_result]:
    original_info = source.lstat()
    try:
        _rename(source, target)
        return original_info, original_info
    except FileExistsError:
        if not _case_change(source, target):
            raise
        # Some filesystems refuse even a case-only rename with NOREPLACE.
        # Keep both legs exclusive so a concurrent creation cannot be overwritten.
        holding = _detach(source, prefix=".rename-")
        original = holding / "original"
        try:
            _rename(original, target)
        except BaseException:
            try:
                _rename(original, source)
            except OSError as error:
                raise OsError(
                    f"could not restore {original} to {source}: {error}"
                ) from error
            holding.rmdir()
            raise
        holding.rmdir()
        return original_info, target.lstat()
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise

    # Stage and verify the copy before publishing or removing any user data.
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".move-") as staged:
        changed_at = source.lstat().st_ctime_ns
        _check_mounts(source)
        versions = _versions(source)
        copy = Path(staged) / "copy"
        if stat.S_ISDIR(source.lstat().st_mode):
            shutil.copytree(source, copy, symlinks=True)
        else:
            shutil.copy2(source, copy, follow_symlinks=False)
        # Verify parent directories before addressing their children. A source
        # directory replaced by a link during the copy must never redirect chmod.
        for relative, version in versions.items():
            entry = source / relative
            staged_entry = copy / relative
            current = entry.lstat()
            if current.st_mode != version[2] or stat.S_IFMT(
                staged_entry.lstat().st_mode
            ) != stat.S_IFMT(current.st_mode):
                raise FlowError(f"`{source}` changed during the move")
            _preserve_access(entry, staged_entry, current, moving=True)
        _check_mounts(source)
        if source.lstat().st_ctime_ns != changed_at:
            raise FlowError(f"`{source}` changed during the move")
        holding = _detach(source, prefix=".move-")
        original = holding / "original"
        try:
            _check_mounts(original)
            if _versions(original) != versions:
                raise FlowError(f"`{source}` changed during the move")
            info = copy.lstat()
            _rename(copy, target)
        except BaseException:
            try:
                _rename(original, source)
            except OSError as error:
                raise OsError(
                    f"could not restore {original} to {source}: {error}"
                ) from error
            holding.rmdir()
            raise
        try:
            _remove_tree(holding)
        except OSError as error:
            raise OsError(
                f"moved to {target}, but could not clean up {holding}: {error}"
            ) from error
        return original_info, info
