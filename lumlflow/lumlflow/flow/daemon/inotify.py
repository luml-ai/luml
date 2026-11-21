import errno
import logging
import os
import threading
from collections.abc import Callable
from functools import partial
from pathlib import Path

from watchdog.observers.inotify_c import (
    CallbackId,
    InotifyConstants,
    InotifyEvent,
    InotifyFD,
    Mask,
    WatchDescriptor,
)

from lumlflow.flow.dsl.accept import CELL_SUFFIX
from lumlflow.flow.dsl.tree import WorkspaceExclusions

logger = logging.getLogger(__name__)

# What can change a scan's result, and nothing a read causes.
_MASK = Mask(
    InotifyConstants.IN_CREATE
    | InotifyConstants.IN_DELETE
    | InotifyConstants.IN_MODIFY
    | InotifyConstants.IN_CLOSE_WRITE
    | InotifyConstants.IN_MOVED_FROM
    | InotifyConstants.IN_MOVED_TO
    | InotifyConstants.IN_DONT_FOLLOW
    | InotifyConstants.IN_ONLYDIR
)
# Files that change which directories the scan prunes.
_PRUNING_FILES = {b".gitignore", b"pyvenv.cfg"}
_VANISHED = {errno.ENOENT, errno.ENOTDIR}
_JOIN_TIMEOUT_S = 2.0

Post = Callable[[str], None]
Job = Callable[[], None]
Submit = Callable[[Path, Job], None]


class TreeWatch:
    """One root's watches: a non-recursive watch on every directory the
    workspace scan would enter, and on none it prunes.

    Placing walks the tree, so it runs on the root's placing queue (`submit`),
    one job at a time. Events arrive on the inotify reader thread, which only
    reads the bookkeeping and hands directory changes over to that queue;
    `_lock` guards the bookkeeping between them.
    """

    def __init__(
        self,
        inotify: InotifyFD,
        root: Path,
        *,
        post: Post,
        wake: Callable[[], None],
        submit: Callable[[Job], None],
        stopping: threading.Event,
    ) -> None:
        self.root = root
        self._inotify = inotify
        self._id = CallbackId(id(self))
        self._post = post
        self._wake = wake
        self._submit = submit
        self._stopping = stopping
        self._lock = threading.Lock()
        self._paths: dict[WatchDescriptor, str] = {}
        self._wds: dict[str, WatchDescriptor] = {}
        self._warned = False
        self._dropped = False
        self._resync_queued = False

    def watched(self) -> set[Path]:
        with self._lock:
            return {Path(path) for path in self._wds}

    def place(self, top: str, *, announce: bool) -> None:
        """Watch `top` and every directory below it the scan would enter.

        Each directory is watched before it is listed: what lands in it after
        the listing raises an event, and what landed before is in the listing,
        which `announce` posts. A directory created and filled in one go so
        still ends in a scan that sees its files.
        """
        exclusions = WorkspaceExclusions(self.root)
        root = str(self.root)
        pending = [top]
        while pending and not self._stopping.is_set() and not self._dropped:
            directory = pending.pop()
            try:
                # One watched already passed this check when it was placed, and
                # a resync checks again what it keeps before it walks.
                if (
                    directory != root
                    and not self._watching(directory)
                    and exclusions.matches(Path(directory), directory=True)
                ):
                    continue
                self._add(directory)
                for entry in os.scandir(directory):
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry.path)
                    elif announce and entry.name.endswith(CELL_SUFFIX):
                        self._post(entry.path)
            except _Unwatchable:
                continue
            except _LimitReached:
                return
            except OSError as unreadable:
                if unreadable.errno not in _VANISHED:
                    self._incomplete(unreadable)

    def drop(self, *tops: str) -> None:
        """Stop watching each of `tops` and everything below it, in one pass
        over the watches. With none given, everything, for good: upkeep queued
        before the root was let go of finds it dropped and places nothing."""
        wanted = set(tops)
        with self._lock:
            if not wanted:
                self._dropped = True
            gone = [
                (path, wd)
                for path, wd in self._wds.items()
                if not wanted or _within(path, wanted)
            ]
            for path, wd in gone:
                del self._wds[path]
                self._paths.pop(wd, None)
        self._inotify.remove_callbacks([(wd, self._id) for _, wd in gone])

    def resync(self) -> None:
        """Bring the watches back in line with the tree, then wake the root's
        flows: after an overflow nobody knows what changed.

        Stale watches go first: a directory renamed while events were lost
        keeps its watch descriptor, and dropping its old path after placing
        the new one would take the new one's watch with it.
        """
        with self._lock:
            # Cleared first: a trigger landing while this runs queues one more.
            self._resync_queued = False
            if self._dropped:
                return
        exclusions = WorkspaceExclusions(self.root)
        stale: set[str] = set()
        for path in sorted(self.watched(), key=lambda watched: len(watched.parts)):
            if self._stopping.is_set():
                return
            if _within(str(path), stale):
                continue
            if not path.is_dir() or (
                path != self.root and exclusions.matches(path, directory=True)
            ):
                stale.add(str(path))
        if stale:
            self.drop(*stale)
        self.place(str(self.root), announce=False)
        if not self._stopping.is_set() and not self._dropped:
            self._wake()

    def on_event(self, event: InotifyEvent) -> None:
        with self._lock:
            base = self._paths.get(event.wd)
        if base is None:
            return
        path = os.path.join(base, os.fsdecode(event.name)) if event.name else base
        if event.is_directory and (event.is_create or event.is_moved_to):
            self._submit(lambda: self.place(path, announce=True))
        elif event.is_directory and event.is_moved_from:
            self._submit(lambda: self.drop(path))
        elif event.name in _PRUNING_FILES:
            self._queue_resync()
        if event.is_directory and (event.is_moved_from or event.is_moved_to):
            # The files a directory takes along raise no event of their own,
            # and its path names no module: only a scan sees them go.
            self._wake()
        self._post(path)

    def on_watch_deleted(self, wd: WatchDescriptor) -> None:
        with self._lock:
            path = self._paths.pop(wd, None)
            if path is not None and self._wds.get(path) == wd:
                del self._wds[path]

    def on_queue_overflow(self) -> None:
        self._queue_resync()

    def _queue_resync(self) -> None:
        with self._lock:
            if self._resync_queued:
                return
            self._resync_queued = True
        self._submit(self.resync)

    def _watching(self, directory: str) -> bool:
        with self._lock:
            return directory in self._wds

    def _add(self, directory: str) -> None:
        with self._lock:
            if directory in self._wds:
                return
        try:
            wd = self._inotify.add_callback(
                os.fsencode(directory), _MASK, self, self._id
            )
        except OSError as refused:
            if refused.errno not in _VANISHED:
                self._incomplete(refused)
            if refused.errno == errno.ENOSPC:
                raise _LimitReached from refused
            raise _Unwatchable from refused
        if wd == -1:
            # watchdog swallows EACCES: it hands back -1 and keeps the callback.
            self._inotify.remove_callbacks([(wd, self._id)])
            self._incomplete(PermissionError(errno.EACCES, "permission denied"))
            raise _Unwatchable
        with self._lock:
            self._paths[wd] = directory
            self._wds[directory] = wd

    def _incomplete(self, reason: OSError) -> None:
        if self._warned:
            return
        self._warned = True
        logger.warning(
            "watching %s is incomplete (%s): edits in the directories left "
            "unwatched reach its flows on their next scan, not on their own",
            self.root,
            reason.strerror or reason,
        )


class InotifyTrees:
    """A watcher's Linux watches: one inotify instance, one `TreeWatch` per
    root. Everything but `stop` runs on the watcher's placing queues, whose
    roots run side by side: `_lock` guards `trees`, and the inotify instance
    guards its own."""

    def __init__(
        self,
        *,
        post: Post,
        wake: Callable[[Path], None],
        submit: Submit,
        stopping: threading.Event,
    ) -> None:
        self._inotify = InotifyFD()
        self._inotify.start()
        self._post = post
        self._wake = wake
        self._submit = submit
        self._stopping = stopping
        self._lock = threading.Lock()
        self.trees: dict[Path, TreeWatch] = {}

    def schedule(self, root: Path) -> None:
        with self._lock:
            if root in self.trees:
                return
            tree = TreeWatch(
                self._inotify,
                root,
                post=self._post,
                wake=lambda: self._wake(root),
                submit=partial(self._submit, root),
                stopping=self._stopping,
            )
            self.trees[root] = tree
        tree.place(str(root), announce=False)

    def unschedule(self, root: Path) -> None:
        with self._lock:
            tree = self.trees.pop(root, None)
        if tree is not None:
            tree.drop()

    def stop(self) -> None:
        with self._lock:
            self.trees.clear()
        self._inotify.stop()
        self._inotify.join(_JOIN_TIMEOUT_S)


def _within(path: str, tops: set[str]) -> bool:
    """Whether `path` is one of `tops` or lies below one."""
    while path not in tops:
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent
    return True


class _Unwatchable(Exception):
    pass


class _LimitReached(Exception):
    pass
