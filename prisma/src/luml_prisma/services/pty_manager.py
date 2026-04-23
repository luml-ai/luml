import asyncio
import contextlib
import errno
import fcntl
import json
import os
import pty
import re
import signal
import struct
import subprocess
import termios
import threading
import time
import uuid
from dataclasses import dataclass, field

_SCROLLBACK_LIMIT = 100_000

_ANSI_ESCAPE_RE = re.compile(
    rb"\x1b"
    rb"(?:"
    rb"\[[0-?]*[ -/]*[@-~]"
    rb"|\][^\x07]*\x07"
    rb"|\][^\x1b]*\x1b\\"
    rb"|[()][AB012]"
    rb"|[@-Z\\-_]"
    rb")"
)


def _has_printable_content(data: bytes) -> bool:
    stripped = _ANSI_ESCAPE_RE.sub(b"", data)
    return any(b > 0x1F and b != 0x7F for b in stripped)


@dataclass
class PtySession:
    session_id: str
    task_id: str
    pid: int
    fd: int
    process: subprocess.Popen[bytes]
    cols: int
    rows: int
    session_type: str = "agent"
    scrollback: bytearray = field(default_factory=bytearray)
    subscribers: list[asyncio.Queue[bytes | str | None]] = field(default_factory=list)
    reader_thread: threading.Thread | None = None
    last_output_time: float = field(default_factory=time.monotonic)
    waiting_notified: bool = False
    last_notified_time: float = 0.0


class PtyManager:
    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def spawn(
        self,
        task_id: str,
        command: list[str],
        cwd: str,
        cols: int = 120,
        rows: int = 40,
        session_type: str = "agent",
    ) -> PtySession:
        try:
            master_fd, slave_fd = pty.openpty()
        except OSError as e:
            raise OSError(f"Failed to open PTY: {e}") from e

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        env = os.environ.copy()
        for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "CONDA_PREFIX"):
            env.pop(key, None)
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = str(cols)
        env["LINES"] = str(rows)

        try:
            process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=cwd,
                env=env,
                preexec_fn=os.setsid,
                close_fds=True,
            )
        except OSError:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)

        session_id = uuid.uuid4().hex
        session = PtySession(
            session_id=session_id,
            task_id=task_id,
            pid=process.pid,
            fd=master_fd,
            process=process,
            cols=cols,
            rows=rows,
            session_type=session_type,
        )
        self._sessions[session_id] = session

        thread = threading.Thread(
            target=self._reader_thread, args=(session,), daemon=True
        )
        thread.start()
        session.reader_thread = thread
        return session

    def _push_to_subscribers(
        self, session: PtySession, data: bytes | str | None
    ) -> None:
        for queue in list(session.subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(data)

    def _reader_thread(self, session: PtySession) -> None:  # noqa: C901
        try:
            while True:
                try:
                    data = os.read(session.fd, 4096)
                except OSError as e:
                    if e.errno in (errno.EIO, errno.EBADF):
                        break
                    break
                if not data:
                    break
                if _has_printable_content(data):
                    session.last_output_time = time.monotonic()
                    session.waiting_notified = False
                session.scrollback.extend(data)
                if len(session.scrollback) > _SCROLLBACK_LIMIT:
                    excess = len(session.scrollback) - _SCROLLBACK_LIMIT
                    del session.scrollback[:excess]
                loop = self._loop
                if loop is not None and loop.is_running():
                    try:
                        loop.call_soon_threadsafe(
                            self._push_to_subscribers, session, data
                        )
                    except RuntimeError:
                        self._push_to_subscribers(session, data)
                else:
                    self._push_to_subscribers(session, data)
        except Exception:
            pass
        finally:
            loop = self._loop
            if loop is not None and loop.is_running():
                try:
                    loop.call_soon_threadsafe(self._push_to_subscribers, session, None)
                except RuntimeError:
                    self._push_to_subscribers(session, None)
            else:
                self._push_to_subscribers(session, None)

    def write(self, session_id: str, data: bytes) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"No session {session_id}")
        os.write(session.fd, data)

    def resize(self, session_id: str, cols: int, rows: int) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"No session {session_id}")
        session.cols = cols
        session.rows = rows
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(session.fd, termios.TIOCSWINSZ, winsize)
        os.kill(session.pid, signal.SIGWINCH)

    def terminate(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        with contextlib.suppress(ProcessLookupError):
            os.kill(session.pid, signal.SIGTERM)
        try:
            session.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.kill(session.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                session.process.wait(timeout=2)
        with contextlib.suppress(OSError):
            os.close(session.fd)
        if session.reader_thread and session.reader_thread.is_alive():
            session.reader_thread.join(timeout=2)

    def terminate_task(self, task_id: str) -> None:
        for session in self._find_task_sessions(task_id):
            self.terminate(session.session_id)

    def is_alive(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        return session.process.poll() is None

    def is_task_alive(self, task_id: str) -> bool:
        return any(s.process.poll() is None for s in self._find_task_sessions(task_id))

    def get_active_session_id(self, task_id: str) -> str | None:
        for s in self._find_task_sessions(task_id):
            if s.process.poll() is None:
                return s.session_id
        return None

    def get_scrollback(self, session_id: str) -> bytes:
        session = self._sessions.get(session_id)
        if session is None:
            return b""
        return bytes(session.scrollback)

    def subscribe(self, session_id: str) -> asyncio.Queue[bytes | str | None]:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"No session {session_id}")
        if self._loop is None:
            with contextlib.suppress(RuntimeError):
                self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | str | None] = asyncio.Queue(maxsize=256)
        session.subscribers.append(queue)
        return queue

    def unsubscribe(
        self, session_id: str, queue: asyncio.Queue[bytes | str | None]
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        with contextlib.suppress(ValueError):
            session.subscribers.remove(queue)

    def get_dead_session_ids(self) -> list[str]:
        return [
            sid for sid, s in self._sessions.items() if s.process.poll() is not None
        ]

    def cleanup_dead(self) -> list[tuple[str, str, str, int | None]]:
        dead: list[tuple[str, str, str, int | None]] = []
        for session_id, session in list(self._sessions.items()):
            exit_code = session.process.poll()
            if exit_code is not None:
                dead.append(
                    (session_id, session.task_id, session.session_type, exit_code)
                )
                with contextlib.suppress(OSError):
                    os.close(session.fd)
                del self._sessions[session_id]
        return dead

    def check_idle_sessions(
        self, threshold: float = 5.0, cooldown: float = 30.0
    ) -> None:
        now = time.monotonic()
        for session in self._sessions.values():
            if session.session_type != "agent":
                continue
            if session.process.poll() is not None:
                continue
            if session.waiting_notified:
                continue
            if now - session.last_notified_time < cooldown:
                continue
            if now - session.last_output_time >= threshold:
                msg = json.dumps({"type": "waiting_for_input"})
                self._push_to_subscribers(session, msg)
                session.waiting_notified = True
                session.last_notified_time = now

    def get_exit_code(self, session_id: str) -> int | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return session.process.poll()

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get_agent_session_ids(self) -> list[str]:
        return [
            sid
            for sid, s in self._sessions.items()
            if s.session_type == "agent" and s.process.poll() is None
        ]

    def is_session_waiting_notified(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        return session.waiting_notified

    def get_idle_duration(self, session_id: str) -> float | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.process.poll() is not None:
            return None
        return time.monotonic() - session.last_output_time

    def get_idle_agent_sessions(self, threshold: float = 5.0) -> list[str]:
        now = time.monotonic()
        return [
            sid
            for sid, s in self._sessions.items()
            if s.session_type == "agent"
            and s.process.poll() is None
            and now - s.last_output_time >= threshold
        ]

    def get_session_type(self, session_id: str) -> str | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return session.session_type

    def _find_task_sessions(self, task_id: str) -> list[PtySession]:
        return [s for s in self._sessions.values() if s.task_id == task_id]

    def shutdown(self) -> None:
        for session_id in list(self._sessions.keys()):
            self.terminate(session_id)
