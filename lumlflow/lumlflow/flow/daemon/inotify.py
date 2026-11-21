import errno
import logging
import os
import threading
from collections.abc import Callable
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
Submit = Callable[[Callable[[], None]], None]


class TreeWatch:
    """One root's watches: a non-recursive watch on every directory the
    workspace scan would enter, and on none it prunes.

    Placing walks the tree, so it runs on the watcher's placing thread
    (`submit`). Events arrive on the inotify reader thread, which only reads
    the bookkeeping and hands directory changes over to the placing thread;
    `_lock` guards the two maps between them.
    """

    def __init__(
        self,
        inotify: InotifyFD,
        root: Path,
        *,
        post: Post,
        wake: Callable[[], None],
        submit: Submit,
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
        while pending and not self._stopping.is_set():
            directory = pending.pop()
            try:
                if directory != root and exclusions.matches(
                    Path(directory), directory=True
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

    def drop(self, top: str | None = None) -> None:
        """Stop watching `top` and everything below it; everything if None."""
        below = (top or "") + os.sep
        with self._lock:
            gone = [
                (path, wd)
                for path, wd in self._wds.items()
                if top is None or path == top or path.startswith(below)
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
        exclusions = WorkspaceExclusions(self.root)
        for path in self.watched():
            if not path.is_dir() or (
                path != self.root and exclusions.matches(path, directory=True)
            ):
                self.drop(str(path))
        self.place(str(self.root), announce=False)
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
            self._submit(self.resync)
        self._post(path)

    def on_watch_deleted(self, wd: WatchDescriptor) -> None:
        with self._lock:
            path = self._paths.pop(wd, None)
            if path is not None and self._wds.get(path) == wd:
                del self._wds[path]

    def on_queue_overflow(self) -> None:
        self._submit(self.resync)

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
    root. Everything but `stop` runs on the watcher's placing thread."""

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
        self.trees: dict[Path, TreeWatch] = {}

    def schedule(self, root: Path) -> None:
        if root in self.trees:
            return
        tree = TreeWatch(
            self._inotify,
            root,
            post=self._post,
            wake=lambda: self._wake(root),
            submit=self._submit,
            stopping=self._stopping,
        )
        self.trees[root] = tree
        tree.place(str(root), announce=False)

    def unschedule(self, root: Path) -> None:
        tree = self.trees.pop(root, None)
        if tree is not None:
            tree.drop()

    def stop(self) -> None:
        self.trees.clear()
        self._inotify.stop()
        self._inotify.join(_JOIN_TIMEOUT_S)


class _Unwatchable(Exception):
    pass


class _LimitReached(Exception):
    pass
