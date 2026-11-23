"""Directory subscriptions and lease-based locks for Workspace files."""

import asyncio
import os
import stat
import weakref
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver, ObservedWatch

from lumlflow.flow.daemon import files
from lumlflow.flow.daemon.stream import Frame, Subscription
from lumlflow.flow.errors import FileLocked, FlowError, NotAFile
from lumlflow.flow.store.flowstore import STORE_DIRNAME

DEBOUNCE_S = 0.3
Sessions = dict[object, tuple[str, str]]


def _version(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size


@dataclass
class _Lock:
    session: object | None
    actor: str | None
    label: str
    last: float
    info: os.stat_result
    pin: weakref.finalize | None = None

    def pin_unwatched(self, path: Path) -> None:
        # Linux stat has no birth time. Hold the inode while its directory is
        # unwatched so unlink/create cannot recycle its number beneath a lock.
        if self.pin is None and hasattr(os, "O_PATH"):
            with suppress(OSError):
                fd = os.open(path, os.O_PATH | os.O_NOFOLLOW)
                if os.path.samestat(os.fstat(fd), self.info):
                    self.pin = weakref.finalize(self, os.close, fd)
                else:
                    os.close(fd)


@dataclass
class _Selection:
    directory: Path
    file: Path | None
    target: Path | None

    @property
    def directories(self) -> set[Path]:
        roots = {self.directory}
        if self.file is not None:
            roots.add(self.file.parent)
        if self.target is not None:
            roots.add(self.target.parent)
        return roots


class FileWatcher(FileSystemEventHandler):
    def __init__(
        self,
        sessions: Callable[[], Sessions],
        clock: Callable[[], float],
        idle_s: float,
    ) -> None:
        self._sessions = sessions
        self._at_start: dict[object, dict[Path, tuple[int, ...]]] = {}
        self._clock = clock
        self._idle_s = idle_s
        self._loop: asyncio.AbstractEventLoop | None = None
        self._observer: BaseObserver | None = None
        self._watches: dict[Path, tuple[ObservedWatch, os.stat_result]] = {}
        self._subscribers: dict[Subscription, _Selection] = {}
        self._locks: dict[Path, _Lock] = {}
        self._writes: dict[Path, tuple[int, ...]] = {}
        self._pending: dict[Path, asyncio.TimerHandle] = {}
        self._changes: dict[Path, set[Path]] = {}
        self._watch_timer: asyncio.TimerHandle | None = None
        self._dirty_locks: set[Path] = set()

    def subscribe(
        self, sub: Subscription, directory: str, file: str | None
    ) -> list[Frame]:
        self.expire()
        root = files.directory_path(directory)
        path = target = None
        if file is not None:
            raw = files.absolute_path(file)
            files.directory_path(str(raw.parent))
            path = files.entry_path(raw)
            # A deleted file or dangling link still needs its parent watched.
            with files.os_errors():
                if path.exists():
                    target = files.regular_file(file).resolve(strict=True)
                elif path.name == STORE_DIRNAME:
                    raise NotAFile(f"`{path}` belongs to a notebook store")
        with files.os_errors():
            if self._observer is None:
                self._loop = asyncio.get_running_loop()
                observer = Observer()
                observer.start()
                self._observer = observer
            assert self._observer is not None
            try:
                selection = _Selection(root, path, target)
                for directory_path in selection.directories:
                    self._watch(directory_path)
                self._subscribers[sub] = selection
                if self._watch_timer is None:
                    self._watch_timer = asyncio.get_running_loop().call_later(
                        0.5, self._refresh_watches
                    )
                sub.file_watcher = self
            finally:
                self._drop_unused()
        return [self._snapshot(self._subscribers[sub])]

    def unsubscribe(self, sub: Subscription) -> None:
        self._subscribers.pop(sub, None)
        sub.file_watcher = None
        self._drop_unused()

    def _unwatch(self, root: Path) -> None:
        watch, _ = self._watches.pop(root)
        assert self._observer is not None
        with suppress(KeyError, OSError):
            self._observer.unschedule(watch)
        for path, lock in self._locks.items():
            if path.parent == root:
                lock.pin_unwatched(path)
        for path in list(self._writes):
            if path.parent == root:
                del self._writes[path]

    def _watch(self, root: Path) -> None:
        held = self._watches.get(root)
        try:
            info = root.stat()
        except OSError:
            if held:
                self._unwatch(root)
                self._queue(root, root)
            raise
        if held:
            if os.path.samestat(held[1], info):
                return
            self._unwatch(root)
            self._queue(root, root)
        # Recheck the path policy when a directory has been replaced by a link.
        if files.directory_path(str(root)) != root:
            raise NotAFile(f"`{root}` is no longer the watched directory")
        assert self._observer is not None
        watch = self._observer.schedule(self, str(root), recursive=False)
        self._watches[root] = watch, info

    def _lost_watch(self, root: Path) -> None:
        if root in self._watches:
            self._unwatch(root)
            self._queue(root, root)
            with suppress(OSError, FlowError):
                self._watch(root)

    def _drop_unused(self) -> None:
        used = {root for s in self._subscribers.values() for root in s.directories}
        for root in self._watches.keys() - used:
            self._unwatch(root)
        if not used and self._watch_timer:
            self._watch_timer.cancel()
            self._watch_timer = None

    def _refresh_target(self, selection: _Selection) -> None:
        path = selection.file
        if path is None:
            return
        target = None
        with suppress(OSError, FlowError):
            target = files.regular_file(str(path)).resolve(strict=True)
            self._watch(target.parent)
        if target != selection.target:
            selection.target = target
            self._queue(path.parent, path)
            self._dirty_locks.add(path.parent)
            self._drop_unused()

    def _refresh_watches(self) -> None:
        # An inode watch can follow a directory away from its subscribed name.
        # Its replacement need not generate an event on any remaining watch.
        self._watch_timer = None
        for selection in self._subscribers.values():
            self._refresh_target(selection)
        roots = {root for s in self._subscribers.values() for root in s.directories}
        for root in roots:
            missing = root not in self._watches
            with suppress(OSError, FlowError):
                self._watch(root)
                if missing:
                    self._queue(root, root)
        if roots:
            self._watch_timer = asyncio.get_running_loop().call_later(
                0.5, self._refresh_watches
            )

    def lease_starting(self, session: object) -> None:
        # Watchdog can still have undelivered events when the socket acquires
        # its first lease. Those file versions predate this session.
        versions: dict[Path, tuple[int, ...]] = {}
        for root in self._watches:
            with suppress(OSError), os.scandir(root) as entries:
                for entry in entries:
                    with suppress(OSError):
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISREG(info.st_mode):
                            versions[Path(entry.path)] = (
                                *_version(info),
                                info.st_ctime_ns,
                            )
        self._at_start[session] = versions

    async def stop(self) -> None:
        self._loop = None
        for timer in self._pending.values():
            timer.cancel()
        self._pending.clear()
        self._changes.clear()
        self._at_start.clear()
        self._dirty_locks.clear()
        for sub in list(self._subscribers):
            self.unsubscribe(sub)
        self._locks.clear()
        if self._observer is not None:
            self._observer.stop()
            await asyncio.to_thread(self._observer.join)
            self._observer = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        loop = self._loop
        if loop is None or event.event_type not in {
            "created",
            "modified",
            "attrib",
            "deleted",
            "moved",
        }:
            return
        if event.is_directory and event.event_type in {"deleted", "moved"}:
            with suppress(RuntimeError):
                loop.call_soon_threadsafe(
                    self._lost_watch, Path(os.fsdecode(event.src_path))
                )
        if event.event_type == "moved" and event.src_path and event.dest_path:
            with suppress(RuntimeError):
                loop.call_soon_threadsafe(
                    self._observed_move,
                    Path(os.fsdecode(event.src_path)),
                    Path(os.fsdecode(event.dest_path)),
                    event.is_directory,
                )
            return
        for name, changed in (
            (event.src_path, event.event_type in {"created", "modified"}),
            (event.dest_path, True),
        ):
            if name:
                path = Path(os.fsdecode(name))
                if path.name == STORE_DIRNAME:
                    continue
                with suppress(RuntimeError):
                    loop.call_soon_threadsafe(
                        self.notice, path, changed and not event.is_directory
                    )

    def notice(self, path: Path, write: bool) -> None:
        if path in self._watches:
            self._queue(path, path)
        if path.parent not in self._watches:
            return
        for selection in self._subscribers.values():
            if path == selection.file:
                self._refresh_target(selection)
        if write:
            with suppress(OSError):
                info = path.lstat()
                if stat.S_ISREG(info.st_mode):
                    signature = _version(info)
                    agents = {
                        session: display
                        for session, display in self._sessions().items()
                        if self._at_start.get(session, {}).get(path)
                        != (*signature, info.st_ctime_ns)
                    }
                    if self._writes.get(path) != (*signature, info.st_ctime_ns):
                        self._writes.pop(path, None)
                        if agents:
                            session, (actor, label) = (
                                next(iter(agents.items()))
                                if len(agents) == 1
                                else (None, (None, "an agent"))
                            )
                            self._locks[path] = _Lock(
                                session, actor, label, self._clock(), info
                            )
                            self._dirty_locks.add(path.parent)
        elif not path.exists():
            self._writes.pop(path, None)
            if self._locks.pop(path, None) is not None:
                self._dirty_locks.add(path.parent)
        self._queue(path.parent, path)

    def _queue(self, directory: Path, path: Path) -> None:
        self._changes.setdefault(directory, set()).add(path)
        if directory not in self._pending:
            self._pending[directory] = asyncio.get_running_loop().call_later(
                DEBOUNCE_S, self._flush, directory
            )

    def _flush(self, directory: Path) -> None:
        self._pending.pop(directory)
        paths = self._changes.pop(directory)
        if len(paths) > 1:
            paths.discard(directory)
        for sub, selection in self._subscribers.items():
            if directory not in selection.directories:
                continue
            for path in sorted(paths):
                changes = [(directory, path)]
                if (
                    path == selection.target
                    and selection.file is not None
                    and selection.file != path
                ):
                    changes.append((selection.file.parent, selection.file))
                for parent, changed in changes:
                    sub.offer(
                        {
                            "channel": "files",
                            "type": "changed",
                            "directory": str(parent),
                            "path": str(changed),
                        }
                    )
        if directory in self._dirty_locks:
            self._dirty_locks.remove(directory)
            self._announce({directory})

    @staticmethod
    def _matches(path: Path, lock: _Lock) -> bool:
        with suppress(OSError):
            info = path.lstat()
            return os.path.samestat(info, lock.info) and getattr(
                info, "st_birthtime_ns", None
            ) == getattr(lock.info, "st_birthtime_ns", None)
        return False

    def _observed_move(self, source: Path, target: Path, directory: bool) -> None:
        transferred = False
        for path, lock in list(self._locks.items()):
            if path.is_relative_to(source):
                destination = target / path.relative_to(source)
                if self._matches(destination, lock):
                    del self._locks[path]
                    self._locks[destination] = lock
                    if destination.parent not in self._watches:
                        lock.pin_unwatched(destination)
                    self._dirty_locks.update((path.parent, destination.parent))
                    transferred = True
        if source.name != STORE_DIRNAME:
            self.notice(source, False)
        if target.name != STORE_DIRNAME:
            self.notice(target, not directory and not transferred)

    def prepare_move(
        self, source: Path
    ) -> Callable[[Path, os.stat_result, os.stat_result], None]:
        # A move runs on a worker. Its removal event may be delivered before
        # the operation reports the destination (including a cross-device copy).
        held = {
            path: lock
            for path, lock in self._locks.items()
            if path.is_relative_to(source) and self._matches(path, lock)
        }

        def moved(target: Path, original: os.stat_result, info: os.stat_result) -> None:
            self.written(target, info)
            directories: set[Path] = set()
            for path, lock in held.items():
                destination = target / path.relative_to(source)
                with suppress(OSError):
                    current = destination.lstat()
                    if path == source:
                        if not (
                            os.path.samestat(original, lock.info)
                            and os.path.samestat(current, info)
                        ):
                            continue
                    elif os.path.samestat(original, info):
                        if not os.path.samestat(current, lock.info):
                            continue
                    elif (
                        not stat.S_ISREG(current.st_mode)
                        or current.st_size != lock.info.st_size
                    ):
                        continue
                    if self._locks.get(path) is lock:
                        del self._locks[path]
                    moved_lock = replace(lock, info=current, pin=None)
                    if destination.parent not in self._watches:
                        moved_lock.pin_unwatched(destination)
                    self._locks[destination] = moved_lock
                    directories.update((path.parent, destination.parent))
            self.expire()
            self._announce(directories)

        return moved

    def _snapshot(self, selection: _Selection) -> Frame:
        rows = []
        for path, lock in self._locks.items():
            if path.parent not in selection.directories or not self._matches(
                path, lock
            ):
                continue
            row = {
                "path": str(path),
                "actor": lock.actor,
                "label": lock.label,
                "last": int(lock.last * 1000),
            }
            rows.append(row)
            if selection.target == path and selection.file != path:
                rows.append({**row, "path": str(selection.file)})
        return {
            "channel": "files",
            "type": "locks",
            "locks": rows,
            "idle_after_s": self._idle_s,
        }

    def _announce(self, directories: set[Path]) -> None:
        for sub, selection in self._subscribers.items():
            if directories & selection.directories:
                sub.offer(self._snapshot(selection))

    def expire(
        self, ended: set[tuple[asyncio.StreamWriter, str]] | None = None
    ) -> None:
        sessions = self._sessions()
        for session in self._at_start.keys() - sessions.keys():
            del self._at_start[session]
        if not self._locks:
            return
        now = self._clock()
        changed = set()
        for path, lock in list(self._locks.items()):
            if (
                now - lock.last >= self._idle_s
                or not sessions
                or (lock.session is not None and lock.session not in sessions)
                or (ended and (lock.session, lock.actor) in ended)
            ):
                del self._locks[path]
                changed.add(path.parent)
                self._dirty_locks.discard(path.parent)
        if changed:
            self._announce(changed)

    def check_write(self, path: Path) -> None:
        self.expire()
        if (lock := self._locks.get(path)) and self._matches(path, lock):
            raise FileLocked(f"{lock.label} is working on this file", label=lock.label)

    def written(self, path: Path, info: os.stat_result) -> None:
        if path.parent not in self._watches or not stat.S_ISREG(info.st_mode):
            return
        version = _version(info)
        # Acknowledge only the published inode. Its rename can advance ctime.
        # Retire this acknowledgement on a different version or removal, so
        # an older publication timer cannot retire a newer save.
        try:
            published = path.lstat()
        except OSError:
            return
        if _version(published) != version:
            return
        self._writes[path] = (*version, published.st_ctime_ns)
        # A move may finish on a worker after its watchdog event reached the loop.
        lock = self._locks.get(path)
        if lock is not None and _version(lock.info) == version:
            del self._locks[path]
            self._dirty_locks.discard(path.parent)
            self._announce({path.parent})
