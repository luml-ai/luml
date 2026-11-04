import logging
import os

from watchdog.observers.api import BaseObserver
from watchdog.observers.inotify import InotifyEmitter, InotifyWatchGroup
from watchdog.observers.inotify_c import InotifyConstants, InotifyEvent, Mask

logger = logging.getLogger(__name__)


class TolerantWatchGroup(InotifyWatchGroup):
    def on_event(self, event: InotifyEvent) -> None:
        try:
            super().on_event(event)
        except Exception:
            logger.exception("dropped an inotify event under %r", self.path)

    def _recursive_simulate(self, src_path: bytes) -> list[InotifyEvent]:
        events = []
        for root, dirnames, filenames in os.walk(
            src_path, followlinks=self.follow_symlink
        ):
            parent = self._active_callbacks_by_path.get(root)
            if parent is None:
                continue
            for dirname in dirnames:
                mask = Mask(InotifyConstants.IN_CREATE | InotifyConstants.IN_ISDIR)
                events.append(InotifyEvent(parent, mask, 0, dirname))
            for filename in filenames:
                mask = InotifyConstants.IN_CREATE
                events.append(InotifyEvent(parent, mask, 0, filename))
        return events


class TolerantInotifyEmitter(InotifyEmitter):
    def on_thread_start(self) -> None:
        self._inotify = TolerantWatchGroup(
            self._inotify_fd,
            os.fsencode(self.watch.path),
            is_recursive=self.watch.is_recursive,
            event_mask=self.get_event_mask_from_filter(),
            follow_symlink=self.watch.follow_symlink,
        )


class TolerantInotifyObserver(BaseObserver):
    def __init__(self) -> None:
        super().__init__(TolerantInotifyEmitter)
