"""Path rules and local filesystem operations shared by the workspace transports."""

import asyncio
import ctypes
import errno
import logging
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Awaitable, Iterator
from contextlib import contextmanager
from pathlib import Path

from lumlflow.flow.errors import AlreadyExists, FlowError, NotAFile, OsError, Protected
from lumlflow.flow.store.flowstore import FLOW_SUFFIX, STORE_DIRNAME

logger = logging.getLogger(__name__)


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


def item_path(path: str) -> Path:
    """Preserve the leaf, including broken symlinks, for directory-entry operations."""
    raw = absolute_path(path)
    with os_errors():
        _ordinary(raw)
        value = entry_path(raw)
        mode = value.lstat().st_mode
        _ordinary(value, directory=stat.S_ISDIR(mode))
        if (
            stat.S_ISLNK(mode)
            and value.is_dir()
            and _resolve(value).name.endswith(FLOW_SUFFIX)
        ):
            raise NotAFile(f"`{value}` links to a notebook")
        return value


def regular_file(path: str) -> Path:
    value = item_path(path)
    with os_errors():
        _ordinary(_resolve(value))
        if not stat.S_ISREG(value.stat().st_mode):
            raise NotAFile(f"`{value}` is not a regular file")
    return value


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


def create(target: Path, *, folder: bool) -> Path:
    with os_errors():
        if folder:
            target.mkdir()
        else:
            target.touch(exist_ok=False)
    return target


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


def move(source: Path, target: Path) -> None:
    try:
        _rename(source, target)
        return
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
