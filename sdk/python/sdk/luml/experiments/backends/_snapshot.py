"""Point-in-time copies of experiment databases for publishing.

Every SQLite call runs on a connection of the backend's pool, under its lock, so the
fork handlers keep holding off a fork while one runs. The live database is only ever
attached read-only.
"""

import contextlib
import errno
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from luml.experiments.backends._exceptions import (
    ExportSpaceError,
    LegacyMetricRowsError,
)
from luml.experiments.backends._snapshot_summaries import build_snapshot_summaries
from luml.experiments.backends.migration_runner import (
    KNOWN_EXPERIMENT_REVISION,
    ExperimentMigrationRunner,
    ExperimentSchema,
    read_experiment_schema,
)

if sys.platform != "win32":
    import fcntl

if TYPE_CHECKING:
    from luml.experiments.backends.sqlite import ConnectionPool

logger = logging.getLogger(__name__)

SNAPSHOT_PAGE_SIZE = 16384
WORK_DIR_PREFIX = ".snapshot-"
WORK_DIR_LOCK = ".lock"
LOCKED_DIR_STALE_SECONDS = 3600
UNLOCKED_DIR_STALE_SECONDS = 24 * 3600
_SPACE_ERRNOS = {errno.ENOSPC, errno.EFBIG, getattr(errno, "EDQUOT", errno.ENOSPC)}
# A copy, the migrated copy and the compacted result can exist at the same time.
_COPIES_AT_ONCE = 3
_held_work_dir_locks: set[int] = set()


@dataclass(frozen=True)
class ExperimentSnapshot:
    """A compacted, self-contained, non-WAL copy of an experiment database.

    Everything in `work_dir`, `path` included, is removed when the context that made
    the snapshot exits; callers may put their own temporary files there. When the copy
    could not be brought to schema revision 3, `fallback_reason` says why and the copy
    keeps the revision of the source.
    """

    path: Path
    work_dir: Path
    schema_revision: int
    min_reader_revision: int
    fallback_reason: str | None = None

    @property
    def artifact_generation(self) -> int:
        return 1 if self.fallback_reason is not None else 2


@contextlib.contextmanager
def snapshot_database(
    pool: "ConnectionPool", experiment_id: str, db_path: Path
) -> Generator[ExperimentSnapshot]:
    remove_abandoned_work_dirs(db_path.parent)
    needed_bytes = _COPIES_AT_ONCE * _database_size(db_path)
    try:
        work_dir = Path(
            tempfile.mkdtemp(
                prefix=f"{WORK_DIR_PREFIX}{os.getpid()}-", dir=db_path.parent
            )
        )
    except OSError as error:
        _raise_if_out_of_space(error, experiment_id, db_path.parent, needed_bytes)
        raise
    lock_fd: int | None = None
    try:
        try:
            lock_fd = _lock_work_dir(work_dir)
            snapshot = _build_snapshot(pool, experiment_id, db_path, work_dir)
        except Exception as error:
            _raise_if_out_of_space(error, experiment_id, db_path.parent, needed_bytes)
            raise
        yield snapshot
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if lock_fd is not None:
            _held_work_dir_locks.discard(lock_fd)
            os.close(lock_fd)


def _lock_work_dir(work_dir: Path) -> int | None:
    """Holds an exclusive lock on the work dir's lock file until it is closed."""
    if sys.platform == "win32":
        return None
    fd = os.open(work_dir / WORK_DIR_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except BaseException:
        os.close(fd)
        raise
    _held_work_dir_locks.add(fd)
    return fd


def _close_inherited_work_dir_locks() -> None:
    # A forked child shares the parent's lock but never finishes the parent's export.
    # Closing its copy keeps the parent's lock; flock(LOCK_UN) would release it.
    for fd in _held_work_dir_locks:
        with contextlib.suppress(OSError):
            os.close(fd)
    _held_work_dir_locks.clear()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_close_inherited_work_dir_locks)


def remove_abandoned_work_dirs(directory: Path) -> None:
    """Removes what the exports of processes that no longer run left behind."""
    if sys.platform == "win32":
        return
    for path in directory.glob(f"{WORK_DIR_PREFIX}*"):
        owner = _owner_pid(path.name)
        if owner is not None and owner != os.getpid() and not _process_exists(owner):
            _remove_if_abandoned(path)


def _remove_if_abandoned(path: Path) -> None:
    # The owner's pid may live in another pid namespace or on another host sharing the
    # store, so a missing pid alone proves nothing. A live exporter holds the lock for
    # its dir's whole life; the age guard covers the moment before it takes the lock.
    # A dir without a lock file may be mid-creation or from an older SDK.
    try:
        fd = os.open(path / WORK_DIR_LOCK, os.O_RDONLY)
    except FileNotFoundError:
        if _age_seconds(path) > UNLOCKED_DIR_STALE_SECONDS:
            shutil.rmtree(path, ignore_errors=True)
        return
    except OSError:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return
    try:
        if _age_seconds(path) > LOCKED_DIR_STALE_SECONDS:
            shutil.rmtree(path, ignore_errors=True)
    finally:
        os.close(fd)


def _age_seconds(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0.0


def _owner_pid(name: str) -> int | None:
    owner = name.removeprefix(WORK_DIR_PREFIX).split("-", 1)[0]
    return int(owner) if owner.isdecimal() else None


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _database_size(db_path: Path) -> int:
    return sum(
        path.stat().st_size
        for path in (db_path, Path(f"{db_path}-wal"))
        if path.exists()
    )


def _raise_if_out_of_space(
    error: BaseException, experiment_id: str, directory: Path, needed_bytes: int
) -> None:
    cause: BaseException | None = error
    while cause is not None:
        if (
            isinstance(cause, sqlite3.Error)
            and getattr(cause, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL
        ) or (isinstance(cause, OSError) and cause.errno in _SPACE_ERRNOS):
            raise ExportSpaceError(
                experiment_id, str(directory), needed_bytes
            ) from error
        cause = cause.__cause__ or cause.__context__


def _build_snapshot(
    pool: "ConnectionPool", experiment_id: str, db_path: Path, work_dir: Path
) -> ExperimentSnapshot:
    # The copy is taken before its revision is known: another process may migrate the
    # live database at any time, and the copy's own revision is the one that counts.
    copy = work_dir / "copy.db"
    _vacuum_into(pool, work_dir, db_path, copy)
    schema = _read_schema(pool, work_dir, copy)
    if schema.revision >= KNOWN_EXPERIMENT_REVISION:
        if schema.revision == KNOWN_EXPERIMENT_REVISION:
            _add_summaries(pool, work_dir, copy)
        return _snapshot(copy, work_dir, schema)

    migrated = work_dir / "migrated.db"
    shutil.copyfile(copy, migrated)
    try:
        _migrate(pool, migrated)
    except LegacyMetricRowsError as error:
        logger.warning(
            "Experiment %s is published in the older artifact format (zipped "
            "database, schema revision %s): %s",
            experiment_id,
            schema.revision,
            error,
        )
        return _snapshot(copy, work_dir, schema, fallback_reason=str(error))
    copy.unlink()
    compacted = work_dir / "exp.db"
    _vacuum_into(pool, work_dir, migrated, compacted)
    migrated.unlink()
    _add_summaries(pool, work_dir, compacted)
    return _snapshot(compacted, work_dir, _read_schema(pool, work_dir, compacted))


def _snapshot(
    path: Path,
    work_dir: Path,
    schema: ExperimentSchema,
    fallback_reason: str | None = None,
) -> ExperimentSnapshot:
    return ExperimentSnapshot(
        path=path,
        work_dir=work_dir,
        schema_revision=schema.revision,
        min_reader_revision=schema.min_reader_revision,
        fallback_reason=fallback_reason,
    )


@contextlib.contextmanager
def _helper_connection(
    pool: "ConnectionPool", work_dir: Path
) -> Generator[sqlite3.Connection]:
    """A pooled connection with no data of its own, for attaching other databases."""
    path = work_dir / "helper.db"
    path.touch()
    try:
        with pool.get_connection(path, write=True, create=False) as conn:
            yield conn
    finally:
        pool.close_connection(str(path))


def _read_only_uri(path: Path) -> str:
    return f"{path.absolute().as_uri()}?mode=ro"


def _vacuum_into(
    pool: "ConnectionPool", work_dir: Path, source: Path, target: Path
) -> None:
    """Writes a compacted copy of `source` as one read transaction, so it is a
    consistent snapshot while others write. The copy is not in WAL mode."""
    with _helper_connection(pool, work_dir) as conn:
        conn.execute("ATTACH DATABASE ? AS source", (_read_only_uri(source),))
        conn.execute(f"PRAGMA source.page_size = {SNAPSHOT_PAGE_SIZE}")
        conn.execute("VACUUM source INTO ?", (str(target),))


def _read_schema(
    pool: "ConnectionPool", work_dir: Path, path: Path
) -> ExperimentSchema:
    with _helper_connection(pool, work_dir) as conn:
        conn.execute("ATTACH DATABASE ? AS snapshot", (_read_only_uri(path),))
        return read_experiment_schema(conn, "snapshot")


def _add_summaries(pool: "ConnectionPool", work_dir: Path, path: Path) -> None:
    # Attached, the copy keeps its rollback journal: opened through the pool it would
    # be switched to WAL, which a published snapshot must not be in.
    with _helper_connection(pool, work_dir) as conn:
        conn.execute("ATTACH DATABASE ? AS snapshot", (str(path),))
        try:
            build_snapshot_summaries(conn, "snapshot")
        finally:
            conn.execute("DETACH DATABASE snapshot")


def _migrate(pool: "ConnectionPool", path: Path) -> None:
    try:
        with pool.get_connection(path, write=True, create=False) as conn:
            ExperimentMigrationRunner(conn).migrate()
    finally:
        pool.close_connection(str(path))
