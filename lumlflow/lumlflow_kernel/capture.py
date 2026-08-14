"""File-descriptor capture of a run's console, and its stdin at EOF.

Redirection is at the fd level, not by replacing `sys.stdout`, so output from C
extensions, tqdm, and subprocesses is caught too — tqdm and `logging` default
to stderr, which is why both streams are taken. Bytes are passed through
untouched, so ANSI survives into the live console and the stored artifact.

One counter, stamped under one lock, orders both streams: chunk order is
faithful at chunk granularity, and exact cross-stream interleaving is
unknowable once the OS buffers the two pipes independently — the accepted
limit of any log capture. There is a reader loop per pipe rather than one
`select` over both because on Windows `select` accepts sockets only; the
invariant that matters, a single monotonic `seq`, is the shared counter's.
"""

from __future__ import annotations

import os
import sys
import threading
from collections import deque
from collections.abc import Callable
from types import TracebackType
from typing import Any

DEFAULT_CAP_BYTES = 256 * 1024
_READ_SIZE = 1 << 16
_JOIN_TIMEOUT_S = 5.0
_STREAMS = ("stdin", "stdout", "stderr")

Emit = Callable[[str, int, bytes], None]


class Capture:
    """Capture stdout/stderr for the duration of the `with` block.

    `emit` receives every chunk as it lands — the live console channel. What
    the block accumulates is a capped artifact: the head and the tail, because
    a run's first output says what it started and its last says how it failed.

    `stdin_at_eof` is what makes a cell non-interactive. The scratch REPL turns
    it off: that surface is one a person is typing at.
    """

    def __init__(
        self,
        emit: Emit,
        *,
        cap_bytes: int = DEFAULT_CAP_BYTES,
        stdin_at_eof: bool = True,
    ) -> None:
        self._emit = emit
        self._stdin_at_eof = stdin_at_eof
        self._half_cap = max(cap_bytes // 2, 1)
        self._lock = threading.Lock()
        self._seq = 0
        self._head: list[bytes] = []
        self._head_bytes = 0
        self._tail: deque[bytes] = deque()
        self._tail_bytes = 0
        self._omitted = 0
        self._readers: list[threading.Thread] = []
        self._saved: dict[int, int] = {}
        self._streams: dict[str, Any] = {}

    def __enter__(self) -> Capture:
        _flush_streams()
        for fd in (0, 1, 2) if self._stdin_at_eof else (1, 2):
            self._saved[fd] = os.dup(fd)
        if self._stdin_at_eof:
            devnull = os.open(os.devnull, os.O_RDONLY)
            try:
                os.dup2(devnull, 0)
            finally:
                os.close(devnull)
        for fd, stream in ((1, "stdout"), (2, "stderr")):
            read_fd, write_fd = os.pipe()
            os.dup2(write_fd, fd)
            os.close(write_fd)
            reader = threading.Thread(
                target=self._drain,
                args=(read_fd, stream),
                name=f"capture-{stream}",
                # A cell can leave a child holding the write end, and then this
                # loop never sees EOF. `__exit__` gives up on it after a
                # timeout; a non-daemon reader would go on to hold the whole
                # kernel open at `shutdown`.
                daemon=True,
            )
            reader.start()
            self._readers.append(reader)
        self._bind_streams()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._unbind_streams()
        for fd, saved in self._saved.items():
            os.dup2(saved, fd)
            os.close(saved)
        self._saved.clear()
        for reader in self._readers:
            reader.join(timeout=_JOIN_TIMEOUT_S)
        self._readers.clear()

    @property
    def truncated(self) -> bool:
        return self._omitted > 0

    def artifact(self) -> bytes:
        """The stored log blob: head, a stated gap, tail."""
        head = b"".join(self._head)
        if not self._omitted:
            return head + b"".join(self._tail)
        gap = f"\n... {self._omitted} bytes of output omitted ...\n".encode()
        return head + gap + b"".join(self._tail)

    def _drain(self, read_fd: int, stream: str) -> None:
        try:
            while True:
                data = os.read(read_fd, _READ_SIZE)
                if not data:
                    return
                self._record(stream, data)
        except OSError:
            return
        finally:
            os.close(read_fd)

    def _record(self, stream: str, data: bytes) -> None:
        with self._lock:
            self._seq += 1
            seq = self._seq
            self._accumulate(data)
        try:
            self._emit(stream, seq, data)
        except Exception:
            # The console channel is best-effort; the artifact is the record.
            pass

    def _accumulate(self, data: bytes) -> None:
        if self._head_bytes < self._half_cap:
            room = self._half_cap - self._head_bytes
            self._head.append(data[:room])
            self._head_bytes += min(room, len(data))
            data = data[room:]
            if not data:
                return
        self._tail.append(data)
        self._tail_bytes += len(data)
        while self._tail_bytes > self._half_cap:
            oldest = self._tail[0]
            kept = oldest[self._tail_bytes - self._half_cap :]
            self._omitted += len(oldest) - len(kept)
            self._tail_bytes -= len(oldest) - len(kept)
            if kept:
                self._tail[0] = kept
            else:
                self._tail.popleft()

    def _bind_streams(self) -> None:
        """Point Python's own stream objects at the captured descriptors.

        Redirecting the fds is what catches C extensions and subprocesses;
        rebinding `sys.stdout` is what catches a `print` in a process where
        something already replaced it with an object of its own. The new
        writers are line-buffered, so a run's output streams while it runs
        instead of arriving all at once when it exits.
        """
        self._streams = {name: getattr(sys, name) for name in _STREAMS}
        if self._stdin_at_eof:
            sys.stdin = _reopen(0, "r")
        sys.stdout = _reopen(1, "w")
        sys.stderr = _reopen(2, "w")

    def _unbind_streams(self) -> None:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
                stream.close()
            except (AttributeError, ValueError, OSError):
                pass
        for name, stream in self._streams.items():
            setattr(sys, name, stream)
        self._streams.clear()


def _reopen(fd: int, mode: str) -> Any:
    """A stream over a private duplicate, so closing it never closes the fd."""
    return os.fdopen(
        os.dup(fd), mode, buffering=1, encoding="utf-8", errors="backslashreplace"
    )


def _flush_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, ValueError, OSError):
            pass
