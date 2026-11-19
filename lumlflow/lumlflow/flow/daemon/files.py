"""Path rules and local filesystem operations shared by the workspace transports."""

import asyncio
import ctypes
import errno
import hashlib
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Awaitable, Callable, Iterator
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

logger = logging.getLogger(__name__)
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
def os_errors() -> Iterator[None]:
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


def _preserve_access(path: Path, staged: Path, info: os.stat_result) -> None:
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

        if security(path) != security(staged):
            raise PermissionError(errno.EACCES, "cannot preserve file access controls")
    else:
        temp = staged.stat()
        if (temp.st_uid, temp.st_gid) != (info.st_uid, info.st_gid):
            os.chown(staged, info.st_uid, info.st_gid)
        if sys.platform == "darwin":
            libc = ctypes.CDLL(None, use_errno=True)
            # COPYFILE_ACL copies just the access control list.
            if libc.copyfile(os.fsencode(path), os.fsencode(staged), None, 1):
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code))
        elif hasattr(os, "listxattr"):
            # A default ACL on the parent can also add an ACL to the
            # temporary file that was absent from the original.
            acl_names = {"system.posix_acl_access", "system.nfs4_acl"}
            source = acl_names.intersection(os.listxattr(path))
            for key in acl_names.intersection(os.listxattr(staged)) - source:
                os.removexattr(staged, key)
            for key in source:
                os.setxattr(staged, key, os.getxattr(path, key))
        else:
            raise OSError(errno.ENOTSUP, "cannot preserve file access controls")
    staged.chmod(stat.S_IMODE(info.st_mode))


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
    if path == path.parent or path == Path.home().resolve() or path in ui_directories:
        raise Protected(f"`{path}` is protected")


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


def check_destination(source: Path, target: Path) -> None:
    if target.parent.is_relative_to(source):
        raise FlowError("a folder cannot be moved into itself or its contents")
    try:
        target.lstat()
    except FileNotFoundError:
        return
    raise AlreadyExists(f'"{target.name}" already exists')


def remove(source: Path) -> None:
    if not stat.S_ISDIR(source.lstat().st_mode):
        source.unlink()
        return
    holding = _detach(source, prefix=".delete-")
    try:
        shutil.rmtree(holding)
    except OSError as error:
        raise OsError(f"could not finish deleting {holding}: {error}") from error


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
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise

    # Stage and verify the copy before publishing or removing any user data.
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".move-") as staged:
        changed_at = source.lstat().st_ctime_ns
        versions = _versions(source)
        copy = Path(staged) / "copy"
        if stat.S_ISDIR(source.lstat().st_mode):
            shutil.copytree(source, copy, symlinks=True)
        else:
            shutil.copy2(source, copy, follow_symlinks=False)
        if source.lstat().st_ctime_ns != changed_at:
            raise FlowError(f"`{source}` changed during the move")
        holding = _detach(source, prefix=".move-")
        original = holding / "original"
        try:
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
            shutil.rmtree(holding)
        except OSError:
            # The complete destination is already live. Preserve anything the OS
            # could not clean up instead of rolling back a partially removed tree.
            logger.warning(
                "could not clean up moved item at %s", holding, exc_info=True
            )
        return original_info, info
