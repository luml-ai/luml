import atexit
import functools
import logging
import os
import sqlite3
import threading
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from luml.experiments.backends.sqlite import ConnectionPool

logger = logging.getLogger(__name__)

DEFAULT_FLUSH_INTERVAL = 0.5
DEFAULT_FLUSH_THRESHOLD = 5_000
# Inline flushes of a database whose last flush held more metric keys than this grow
# in proportion, keeping `flush_threshold / WIDE_FLUSH_KEYS` rows per key.
WIDE_FLUSH_KEYS = 10
MAX_FLUSH_THRESHOLD = 200_000
MAX_QUEUED_BYTES = 64 * 2**20
# Measured: a queued metric row with a 12-character key of its own, less the key.
_QUEUED_ROW_BYTES = 240

PendingRow = tuple[str, tuple[Any, ...]]
type RawLock = threading.Lock | threading.RLock

_NATIVELY_BOUND_TYPES: frozenset[type] = frozenset({type(None), float, str, bytes})
_SQLITE_INT_MIN = -(2**63)
_SQLITE_INT_MAX = 2**63 - 1
# Errors caused by one row's values. Any other error (busy, locked, I/O) is about the
# database, so the rows stay queued instead of being dropped.
_ROW_ERRORS = (
    sqlite3.IntegrityError,
    sqlite3.DataError,
    sqlite3.ProgrammingError,
    sqlite3.InterfaceError,
    # Raised when binding a str with lone surrogates, which UTF-8 cannot encode.
    UnicodeEncodeError,
)

# A database that keeps failing (read-only, replaced, corrupt) fails every timer tick.
_FLUSH_WARNING_INTERVAL = 30.0

# Used only when the forking thread already holds a tracker lock: blocking in the usual
# order could then deadlock, so a lock still busy after this long is not held.
_REENTRANT_FORK_TIMEOUT = 1.0

_live_buffers: "weakref.WeakSet[WriteBuffer]" = weakref.WeakSet()
_bind_probe = threading.local()
_bind_probe_lock = threading.Lock()


class _ThreadState(threading.local):
    def __init__(self) -> None:
        self.locks_held = 0
        self.buffer_locks_held = 0
        self.deferred: list[Callable[[], None]] = []
        self.held_for_fork: list[RawLock] = []


_thread_state = _ThreadState()


@dataclass(frozen=True)
class BatchKeys:
    """The distinct metric keys of the last flush of a database."""

    count: int
    mean_length: int


@dataclass
class _FlushFailure:
    logged_at: float
    suppressed: int = 0


class TransactionHook(Protocol):
    """Runs inside each flush transaction of a write buffer, under its flush lock."""

    def prepare(
        self, conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> list[PendingRow]:
        """Returns the rows to execute; may write, but must not commit."""
        ...

    def before_commit(
        self, conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> None: ...

    def after_commit(self, db_path: str) -> None: ...

    def batch_keys(self, db_path: str) -> BatchKeys | None: ...

    def execute_many(
        self, conn: sqlite3.Connection, sql: str, params: list[tuple[Any, ...]]
    ) -> None:
        """Executes one run of rows with the same statement, in order."""
        ...

    def forget(self, db_path: str) -> None: ...

    def forget_all(self) -> None: ...


class GuardedLock:
    """A lock that counts, per thread, how many tracker locks the thread holds.

    The garbage collector can run a finalizer on any thread at any allocation, also
    while that thread holds one of these locks. Cleanup reached from a finalizer checks
    the count and defers itself rather than block on, or nest inside, what it holds.
    """

    __slots__ = ("_buffer_lock", "_lock")

    def __init__(
        self, lock: "threading.Lock | threading.RLock", *, buffer_lock: bool = True
    ) -> None:
        self._lock = lock
        self._buffer_lock = int(buffer_lock)

    def __enter__(self) -> None:
        # Counted before acquiring, so a collection between the two still sees it.
        state = _thread_state
        state.locks_held += 1
        state.buffer_locks_held += self._buffer_lock
        try:
            self._lock.acquire()
        except BaseException:
            state.locks_held -= 1
            state.buffer_locks_held -= self._buffer_lock
            raise

    def __exit__(self, *exc_info: object) -> None:
        self._lock.release()
        state = _thread_state
        state.locks_held -= 1
        state.buffer_locks_held -= self._buffer_lock
        if state.deferred and not state.locks_held:
            _run_deferred(state)


def defer_while_locked(call: Callable[[], None]) -> bool:
    """Queues `call` until this thread releases its last tracker lock.

    Returns False, queueing nothing, when the thread holds no tracker lock.
    """
    state = _thread_state
    if not state.locks_held:
        return False
    state.deferred.append(call)
    return True


def _run_deferred(state: _ThreadState) -> None:
    while state.deferred and not state.locks_held:
        call = state.deferred.pop(0)
        try:
            call()
        except Exception:
            logger.warning("Deferred cleanup %r failed", call, exc_info=True)


def check_bindable(params: tuple[Any, ...]) -> None:
    """Raises what sqlite3 would raise when binding `params`, without a database."""
    for value in params:
        value_type = type(value)
        if value_type is int:
            if _SQLITE_INT_MIN <= value <= _SQLITE_INT_MAX:
                continue
        elif value_type in _NATIVELY_BOUND_TYPES:
            continue
        _probe_binding(params)
        return


def _probe_binding(params: tuple[Any, ...]) -> None:
    conn: sqlite3.Connection | None = getattr(_bind_probe, "conn", None)
    if conn is None:
        conn = _bind_probe.conn = sqlite3.connect(":memory:")
    with _bind_probe_lock:
        conn.execute("SELECT " + ", ".join("?" * len(params)), params)


class WriteBuffer:
    """Per-database queue of rows that are committed in one transaction per flush.

    Flushes of one database are serialised, so rows reach it in the order they were
    appended, and a flush does not return while another one still holds its rows.
    """

    def __init__(
        self,
        pool: "ConnectionPool",
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        flush_threshold: int = DEFAULT_FLUSH_THRESHOLD,
        hook: TransactionHook | None = None,
    ) -> None:
        self.pool = pool
        self.flush_interval = flush_interval
        self.flush_threshold = flush_threshold
        self._hook = hook
        self._rows: dict[str, list[PendingRow]] = {}
        self._other_rows: dict[str, int] = {}
        self._flush_locks: dict[str, threading.Lock] = {}
        self._database_locks: dict[str, GuardedLock] = {}
        self._next_steps: dict[str, dict[str, int]] = {}
        # A deleted database refuses rows until it is created again, and both a delete
        # and a re-creation start a new generation, so a call that began before either
        # cannot reach the next incarnation.
        self._deleted: set[str] = set()
        self._generations: dict[str, int] = {}
        self._flush_failures: dict[str, _FlushFailure] = {}
        self._lock = GuardedLock(threading.Lock())
        self._stop = threading.Event()
        self._flusher: threading.Thread | None = None
        self._flusher_start_failed = False
        self._exit_hook = functools.partial(
            WriteBuffer._flush_on_exit, weakref.ref(self)
        )
        _live_buffers.add(self)
        atexit.register(self._exit_hook)

    @property
    def write_through(self) -> bool:
        return self.flush_interval <= 0

    @staticmethod
    def _flush_on_exit(buffer_ref: "weakref.ReferenceType[WriteBuffer]") -> None:
        if (buffer := buffer_ref()) is not None:
            buffer.close()

    @staticmethod
    def _run_flusher(
        buffer_ref: "weakref.ReferenceType[WriteBuffer]",
        stop: threading.Event,
        interval: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # Counted from the start of each flush, so slow flushes do not stretch the
        # period and with it what a killed process loses.
        wait = interval
        while not stop.wait(wait):
            buffer = buffer_ref()
            if buffer is None:
                return
            started = clock()
            buffer.flush_on_timer()
            del buffer
            wait = max(0.0, interval - (clock() - started))

    def generation(self, db_path: str) -> int:
        return self._generations.get(db_path, 0)

    def accepts(self, db_path: str, generation: int) -> bool:
        return db_path not in self._deleted and self.generation(db_path) == generation

    def database_lock(self, db_path: str) -> GuardedLock:
        """Serialises a database's step counters with its first use and its deletion."""
        if (lock := self._database_locks.get(db_path)) is not None:
            return lock
        with self._lock:
            lock = self._database_locks.get(db_path)
            if lock is None:
                # Not a buffer lock: flushing while holding it is not re-entrant.
                lock = GuardedLock(threading.Lock(), buffer_lock=False)
                self._database_locks[db_path] = lock
            return lock

    def next_step(self, db_path: str, key: str) -> int | None:
        return self._next_steps.get(db_path, {}).get(key)

    def set_next_step(self, db_path: str, key: str, step: int) -> None:
        self._next_steps.setdefault(db_path, {})[key] = step

    def append(
        self, db_path: str, generation: int, sql: str, params: tuple[Any, ...]
    ) -> bool:
        self.make_room(db_path)
        return self.enqueue(db_path, generation, sql, params)

    def make_room(self, db_path: str) -> None:
        """Flushes `db_path` inline when its queue is full; raises if that fails."""
        if self.write_through:
            return
        queued = len(self._rows.get(db_path, ()))
        if queued < self.flush_threshold:
            return
        # The raised threshold is sized for metric points only: rows of any other kind
        # (spans, evals) may be large, so they alone stay held to the base threshold.
        if self._other_rows.get(db_path, 0) >= self.flush_threshold or (
            queued >= self.flush_threshold_for(db_path)
        ):
            self.flush(db_path)

    def flush_threshold_for(self, db_path: str) -> int:
        """`flush_threshold`, raised for a database whose last flush held many metric
        keys, up to `MAX_FLUSH_THRESHOLD` rows and `MAX_QUEUED_BYTES`."""
        keys = self._hook.batch_keys(db_path) if self._hook is not None else None
        if keys is None:
            return self.flush_threshold
        # A flush rewrites ten bucket rows per metric it touches, whatever its points,
        # and an inline one stops the logging thread: a wide experiment's flushes must
        # carry many steps per metric, and are best left to the timer.
        wide = self.flush_threshold * keys.count // WIDE_FLUSH_KEYS
        by_bytes = MAX_QUEUED_BYTES // (_QUEUED_ROW_BYTES + keys.mean_length)
        return max(self.flush_threshold, min(wide, MAX_FLUSH_THRESHOLD, by_bytes))

    def enqueue(
        self,
        db_path: str,
        generation: int,
        sql: str,
        params: tuple[Any, ...],
        *,
        metric_point: bool = False,
    ) -> bool:
        """Queues the row; False when the database was deleted after `generation`."""
        if self.write_through:
            return self._write_through(db_path, generation, sql, params)
        check_bindable(params)
        with self._lock:
            if not self.accepts(db_path, generation):
                return False
            self._rows.setdefault(db_path, []).append((sql, params))
            if not metric_point:
                self._other_rows[db_path] = self._other_rows.get(db_path, 0) + 1
            if self._flusher is None:
                self._start_flusher()
        return True

    def _write_through(
        self, db_path: str, generation: int, sql: str, params: tuple[Any, ...]
    ) -> bool:
        if not self.accepts(db_path, generation):
            return False
        try:
            with (
                self.pool.get_connection(db_path, write=True, create=False) as conn,
                GuardedLock(self._flush_lock(db_path)),
            ):
                if not self.accepts(db_path, generation):
                    return False
                rows = self._prepare(conn, db_path, [(sql, params)])
                conn.execute(*rows[0])
                self._commit(conn, db_path, rows)
        except sqlite3.OperationalError:
            if self.accepts(db_path, generation):
                raise
            return False
        return True

    def _start_flusher(self) -> None:
        flusher = threading.Thread(
            target=WriteBuffer._run_flusher,
            args=(weakref.ref(self), self._stop, self.flush_interval),
            name="luml-write-buffer",
            daemon=True,
        )
        try:
            flusher.start()
        except RuntimeError:
            # The row is already queued: raising would make a caller that retries log
            # it twice. Without the timer it is written by the next flush or close.
            if not self._flusher_start_failed:
                self._flusher_start_failed = True
                logger.warning(
                    "Could not start the write buffer's flush timer; buffered rows "
                    "are written at the next flush or close",
                    exc_info=True,
                )
            return
        self._flusher = flusher

    def _flush_lock_unsafe(self, db_path: str) -> threading.Lock:
        flush_lock = self._flush_locks.get(db_path)
        if flush_lock is None:
            flush_lock = self._flush_locks[db_path] = threading.Lock()
        return flush_lock

    def _flush_lock(self, db_path: str) -> threading.Lock:
        with self._lock:
            return self._flush_lock_unsafe(db_path)

    def flush(self, db_path: str) -> None:
        """Commits the queued rows of `db_path`.

        On a database error the rows go back to the front of the queue and the error
        is raised. Rows rejected one by one (constraint violations) are logged and
        dropped. A call on a thread already inside this buffer (a finalizer run by the
        garbage collector) returns at once and leaves the rows to the outer flush.
        """
        if _thread_state.buffer_locks_held:
            return
        with self._lock:
            if db_path in self._deleted:
                self._rows.pop(db_path, None)
                self._other_rows.pop(db_path, None)
                return
            flush_lock = self._flush_lock_unsafe(db_path)
            if not self._rows.get(db_path) and not flush_lock.locked():
                return
        try:
            with (
                self.pool.get_connection(db_path, write=True, create=False) as conn,
                GuardedLock(flush_lock),
            ):
                self._write_pending(conn, db_path)
        except sqlite3.OperationalError:
            if db_path not in self._deleted:
                raise
        self._flush_failures.pop(db_path, None)

    def _write_pending(self, conn: sqlite3.Connection, db_path: str) -> None:
        with self._lock:
            rows = self._rows.pop(db_path, None)
            other_rows = self._other_rows.pop(db_path, 0)
        if not rows:
            return
        try:
            self._write(conn, db_path, rows)
        except BaseException:
            with self._lock:
                self._rows[db_path] = rows + self._rows.get(db_path, [])
                self._other_rows[db_path] = other_rows + self._other_rows.get(
                    db_path, 0
                )
            raise

    def flush_all(self) -> None:
        if _thread_state.buffer_locks_held:
            return
        with self._lock:
            # A flush takes its rows out of the queue under the flush lock and commits
            # them before releasing it: a held lock may stand for rows still in flight.
            in_flight = [
                db_path
                for db_path, flush_lock in self._flush_locks.items()
                if flush_lock.locked() and db_path not in self._rows
            ]
            db_paths = list(self._rows) + in_flight
        first_error: BaseException | None = None
        for db_path in db_paths:
            try:
                self.flush(db_path)
            except Exception as error:
                first_error = first_error or error
        if first_error is not None:
            raise first_error

    def flush_on_timer(self) -> None:
        if _thread_state.buffer_locks_held:
            return
        with self._lock:
            db_paths = list(self._rows)
        for db_path in db_paths:
            try:
                self.flush(db_path)
            except Exception:
                self._warn_flush_failure(db_path)

    def _warn_flush_failure(self, db_path: str) -> None:
        """Logs the first failure at once, repeats at most every 30 seconds."""
        now = time.monotonic()
        failure = self._flush_failures.get(db_path)
        if failure is not None and now - failure.logged_at < _FLUSH_WARNING_INTERVAL:
            failure.suppressed += 1
            return
        self._flush_failures[db_path] = _FlushFailure(logged_at=now)
        if failure is None:
            logger.warning(
                "Could not flush buffered rows to %s; retrying in %ss",
                db_path,
                self.flush_interval,
                exc_info=True,
            )
        else:
            logger.warning(
                "Could not flush buffered rows to %s; retrying in %ss "
                "(%d more failures since the last warning)",
                db_path,
                self.flush_interval,
                failure.suppressed,
                exc_info=True,
            )

    def discard(self, db_path: str) -> None:
        """Drops the rows of a database being deleted and refuses new ones."""
        # Marked before taking the lock: enqueue checks the mark under the lock, and a
        # re-entrant call, which must not take the lock, still marks the database.
        self._deleted.add(db_path)
        self._generations[db_path] = self.generation(db_path) + 1
        if _thread_state.buffer_locks_held:
            return
        # Waiting out a flush or write in progress keeps it from reaching the files
        # after they are removed.
        with GuardedLock(self._flush_lock(db_path)), self._lock:
            self._rows.pop(db_path, None)
            self._other_rows.pop(db_path, None)
            self._next_steps.pop(db_path, None)
            if self._hook is not None:
                self._hook.forget(db_path)

    def mark_created(self, db_path: str) -> None:
        with self._lock:
            if db_path in self._deleted:
                self._deleted.discard(db_path)
                self._generations[db_path] = self.generation(db_path) + 1
                self._rows.pop(db_path, None)
                self._other_rows.pop(db_path, None)
                self._next_steps.pop(db_path, None)
            # A new database holds none of the ids cached for an earlier one.
            if self._hook is not None:
                self._hook.forget(db_path)

    def close(self) -> None:
        """Stops the timer and flushes everything. Called from a finalizer on a thread
        inside the tracker's locks, it runs once that thread has released them."""
        if defer_while_locked(self.close):
            return
        atexit.unregister(self._exit_hook)
        with self._lock:
            self._stop.set()
            self._stop = threading.Event()
            flusher, self._flusher = self._flusher, None
        if flusher is not None and flusher is not threading.current_thread():
            flusher.join()
        self.flush_all()

    def _prepare(
        self, conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> list[PendingRow]:
        if self._hook is None:
            return rows
        return self._hook.prepare(conn, db_path, rows)

    def _commit(
        self, conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> None:
        if self._hook is not None:
            self._hook.before_commit(conn, db_path, rows)
        conn.commit()
        if self._hook is not None:
            self._hook.after_commit(db_path)

    def _execute_many(
        self, conn: sqlite3.Connection, sql: str, params: list[tuple[Any, ...]]
    ) -> None:
        if self._hook is None:
            conn.executemany(sql, params)
        else:
            self._hook.execute_many(conn, sql, params)

    def _write(
        self, conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> None:
        try:
            prepared = self._prepare(conn, db_path, rows)
            for sql, group in groupby(prepared, key=itemgetter(0)):
                self._execute_many(conn, sql, [params for _, params in group])
            self._commit(conn, db_path, prepared)
            return
        except _ROW_ERRORS:
            conn.rollback()
        # Re-applying row by row keeps one bad row from losing the whole batch:
        # a failed statement only undoes itself, the transaction stays open. The
        # rollback also undid what the hook wrote, so it prepares the rows again.
        prepared = self._prepare(conn, db_path, rows)
        for sql, params in prepared:
            try:
                conn.execute(sql, params)
            except _ROW_ERRORS:
                logger.exception(
                    "Dropped buffered row for %s: %s %r", db_path, sql.strip(), params
                )
        self._commit(conn, db_path, prepared)

    def _hold_for_fork(self, held: list[RawLock], timeout: float) -> None:
        """Takes every lock under which this buffer or its pool calls into SQLite."""
        while True:
            start = len(held)
            connection_locks = self.pool.connection_locks()
            inner_locks = [lock._lock for lock in connection_locks]
            inner_locks += list(self._flush_locks.values())
            for lock in inner_locks:
                if lock.acquire(timeout=timeout):
                    held.append(lock)
            pool_lock = self.pool.lock._lock
            if not pool_lock.acquire(timeout=timeout):
                return
            held.append(pool_lock)
            # Connections open only under the pool lock, so once it is held no new
            # connection lock can appear; one opened before it was taken is not held.
            if set(self.pool.connection_locks()) <= set(connection_locks):
                return
            _release_from(held, start)

    def _reset_after_fork(self) -> None:
        self._rows = {}
        self._other_rows = {}
        self._flush_locks = {}
        self._database_locks = {}
        self._next_steps = {}
        self._flush_failures = {}
        if self._hook is not None:
            self._hook.forget_all()
        self._lock = GuardedLock(threading.Lock())
        self._stop = threading.Event()
        self._flusher = None
        self.pool.reset_after_fork()


def _release_from(held: list[RawLock], start: int) -> None:
    while len(held) > start:
        held.pop().release()


def _hold_locks_before_fork() -> None:
    # SQLite's mutexes and its in-process file-lock state do not survive fork(): a
    # thread inside a sqlite3 call at that moment leaves the child hung, or with a
    # database that stays locked. Holding every lock that guards such a call keeps
    # all threads out of SQLite until the fork is done.
    state = _thread_state
    timeout = _REENTRANT_FORK_TIMEOUT if state.locks_held else -1
    state.locks_held += 1
    state.buffer_locks_held += 1
    for buffer in list(_live_buffers):
        buffer._hold_for_fork(state.held_for_fork, timeout)
    if _bind_probe_lock.acquire(timeout=timeout):
        state.held_for_fork.append(_bind_probe_lock)


def _end_fork_hold(state: _ThreadState) -> None:
    state.locks_held -= 1
    state.buffer_locks_held -= 1
    if state.deferred and not state.locks_held:
        _run_deferred(state)


def _release_locks_after_fork_in_parent() -> None:
    state = _thread_state
    _release_from(state.held_for_fork, 0)
    _end_fork_hold(state)


def _reset_buffers_after_fork() -> None:
    """Forked children must not write rows they inherited from the parent.

    The parent still owns those rows and flushes them itself. Locks held by another
    parent thread at fork time would stay locked forever in the child, so the child
    gets fresh ones, and a fresh connection pool; no flusher thread survives a fork.
    """
    global _bind_probe, _bind_probe_lock
    _bind_probe = threading.local()
    _bind_probe_lock = threading.Lock()
    state = _thread_state
    state.held_for_fork = []
    for buffer in list(_live_buffers):
        buffer._reset_after_fork()
    _end_fork_hold(state)


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_hold_locks_before_fork,
        after_in_parent=_release_locks_after_fork_in_parent,
        after_in_child=_reset_buffers_after_fork,
    )
