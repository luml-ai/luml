import contextlib
import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lumlflow.flow.daemon import workspace

LOG_MAX_BYTES = 1024 * 1024
LOG_FILE_COUNT = 4

_LOGGER_NAMES = ("lumlflow", "uvicorn.error")
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_handler: RotatingFileHandler | None = None
_previous_states: dict[str, tuple[int, bool]] = {}
_lock = threading.Lock()


class _PrivateRotatingFileHandler(RotatingFileHandler):
    def doRollover(self) -> None:
        super().doRollover()
        _make_private(Path(self.baseFilename))
        _prune(Path(self.baseFilename))


def configure(path: Path | None = None) -> Path:
    global _handler, _previous_states

    target = (path or workspace.log_path()).resolve()
    with _lock:
        if _handler is not None and Path(_handler.baseFilename) == target:
            return target
        if _handler is None:
            _previous_states = {
                name: (logging.getLogger(name).level, logging.getLogger(name).propagate)
                for name in _LOGGER_NAMES
            }
        else:
            for name in _LOGGER_NAMES:
                logging.getLogger(name).removeHandler(_handler)
            _handler.close()
        target.parent.mkdir(parents=True, exist_ok=True)
        _prune(target)
        handler = _PrivateRotatingFileHandler(
            target,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_FILE_COUNT - 1,
            encoding="utf-8",
        )
        _make_private(target)
        handler.setFormatter(logging.Formatter(_FORMAT))
        for name in _LOGGER_NAMES:
            logger = logging.getLogger(name)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        _handler = handler
    return target


def close() -> None:
    global _handler, _previous_states

    with _lock:
        if _handler is None:
            return
        for name in _LOGGER_NAMES:
            logger = logging.getLogger(name)
            logger.removeHandler(_handler)
            previous_level, previous_propagate = _previous_states[name]
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
        _handler.close()
        _handler = None
        _previous_states = {}


def _make_private(path: Path) -> None:
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _prune(path: Path) -> None:
    for candidate in path.parent.glob(f"{path.name}.*"):
        suffix = candidate.name.removeprefix(f"{path.name}.")
        if suffix.isdigit() and int(suffix) >= LOG_FILE_COUNT:
            with contextlib.suppress(OSError):
                candidate.unlink()
