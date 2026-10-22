"""Run-and-attach: subprocess management + experiment auto-attach.

When `lumlflow tui <script> [args...]` is invoked, the TUI runs the
script as a child process sharing the SQLite store via the
`BACKEND_STORE_URI` environment variable, captures its stdout/stderr
into an in-app log pane (rather than letting it corrupt the terminal),
and watches the store for a newly created `active` experiment so the
TUI can auto-navigate into its live detail screen.

Key contracts (from SPEC.md):

- The child inherits the store URI via environment so both processes
  point at the same SQLite file.
- Child stdout/stderr is saved to persistent log files and tailed by
  the TUI; detaching cannot break the child's output streams.
- The TUI snapshots existing experiments at launch and watches for new
  ones; the first newly-appeared `active` experiment is the attach
  target. Multiple-new is supported (attach to the first, surface the
  rest).
- A non-zero exit is shown alongside the captured logs; the experiment
  status itself is reflected by the normal live view.
- If no new experiment ever appears (script finished without creating
  one, or a timeout elapses), the TUI says so and remains usable.
- The run can be stopped from inside the TUI (`Ctrl-C`) and a quit
  prompt offers to terminate or detach the child.

This module is the *plumbing* — subprocess + snapshot/watch. The UI
glue (log pane widget, screen that owns the run, lifecycle prompts)
lives in `widgets/log_pane.py`, `screens/run_attach.py` and
`app.py`.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from luml.experiments.tracker import ExperimentTracker

LineCallback = Callable[[str, str], None]
"""(stream_name, line) — `stream_name` is "stdout" or "stderr"."""

ExitCallback = Callable[[int | None], None]
"""(exit_code,) — None means the process was killed before it set one."""


@dataclass
class RunSpec:
    """How to launch the child process.

    `script` is the file path the user typed; `args` are pass-through
    arguments. The TUI runs the script via the same Python interpreter
    that hosts the TUI so module resolution matches.
    """

    script: str
    args: tuple[str, ...] = ()
    cwd: str | None = None

    @property
    def command(self) -> list[str]:
        return [sys.executable, self.script, *self.args]

    def describe(self) -> str:
        return " ".join(shlex.quote(part) for part in self.command)


@dataclass
class RunState:
    """Snapshot of the run's lifecycle, suitable for surfacing in the UI."""

    started: bool = False
    finished: bool = False
    exit_code: int | None = None
    detach_only: bool = False
    error_message: str | None = None
    log_dir: Path | None = None
    # Snapshot of all experiment ids that existed BEFORE the run started.
    # Used to detect newly created experiments without false positives from
    # the existing store contents.
    experiment_snapshot: set[str] = field(default_factory=set)


class RunManager:
    """Owns the child process, captures its output, and reports state.

    `RunManager` is intentionally framework-agnostic: it does not import
    Textual. The screen that hosts the run pushes line/exit callbacks
    and the manager calls them on the event loop when output arrives.

    The manager exposes a single `start()` coroutine that launches the
    process and spins up two background tasks to tail its log files.
    Each completed read line is dispatched through `on_line`; when both
    streams close and the process exits, `on_exit` fires once with the
    final exit code.
    """

    def __init__(
        self,
        spec: RunSpec,
        *,
        tracker: ExperimentTracker,
        store_uri: str,
        on_line: LineCallback,
        on_exit: ExitCallback,
        env: dict[str, str] | None = None,
    ) -> None:
        self.spec = spec
        self._tracker = tracker
        self._store_uri = store_uri
        self._on_line = on_line
        self._on_exit = on_exit
        self._env = env
        self._process: subprocess.Popen[bytes] | None = None
        self._reader_tasks: list[asyncio.Task[None]] = []
        self._wait_task: asyncio.Task[None] | None = None
        self.state = RunState()

    # ----- snapshot -----

    def snapshot_experiments(self) -> set[str]:
        """Record the ids that already exist so newly created ones stand out."""

        try:
            existing = self._tracker.list_experiments()
        except Exception:
            existing = []
        ids = {getattr(e, "id", None) for e in existing}
        ids.discard(None)
        snapshot: set[str] = {i for i in ids if isinstance(i, str)}
        self.state.experiment_snapshot = snapshot
        return snapshot

    def detect_new_experiments(self, *, require_active: bool = True) -> list[str]:
        """Return experiment ids that appeared since the snapshot.

        When `require_active=True` (the SPEC contract — "watches for a
        newly created experiment ... status `active`") we filter to only
        experiments whose status is still `active`. A short-lived script
        whose experiment has already flipped to `completed` won't match
        until the caller relaxes the filter (the screen does so on a
        final post-exit attempt so a fast script still attaches).
        """

        try:
            existing = self._tracker.list_experiments()
        except Exception:
            return []
        snapshot = self.state.experiment_snapshot
        new_ids: list[str] = []
        for exp in existing:
            exp_id = getattr(exp, "id", None)
            if not isinstance(exp_id, str):
                continue
            if exp_id in snapshot:
                continue
            if require_active:
                status = getattr(exp, "status", None)
                if status != "active":
                    continue
            new_ids.append(exp_id)
        return new_ids

    # ----- subprocess -----

    @property
    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    def build_environment(self) -> dict[str, str]:
        """Environment for the child process — shared store URI baked in."""

        env = dict(os.environ if self._env is None else self._env)
        env["BACKEND_STORE_URI"] = self._store_uri
        env["LUML_BACKEND_STORE_URI"] = self._store_uri
        env["PYTHONUNBUFFERED"] = "1"
        return env

    async def start(self) -> None:
        """Launch the child process and start log streaming.

        Snapshot is taken *before* the process starts so any experiment
        the script creates is correctly classified as "new".
        """

        if self.state.started:
            return
        self.snapshot_experiments()
        env = self.build_environment()
        try:
            log_root = Path.home() / ".luml" / "runs"
            log_root.mkdir(parents=True, exist_ok=True)
            self.state.log_dir = Path(tempfile.mkdtemp(prefix="run-", dir=log_root))
            stdout_path = self.state.log_dir / "stdout.log"
            stderr_path = self.state.log_dir / "stderr.log"
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                self._process = subprocess.Popen(
                    self.spec.command,
                    cwd=self.spec.cwd,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except OSError as exc:
            code = 127 if isinstance(exc, FileNotFoundError) else 126
            self.state.started = True
            self.state.finished = True
            self.state.exit_code = code
            self.state.error_message = str(exc)
            self._dispatch_line("stderr", f"failed to start: {exc}")
            self._dispatch_exit(code)
            return

        self.state.started = True
        for name, path in (("stdout", stdout_path), ("stderr", stderr_path)):
            self._reader_tasks.append(
                asyncio.create_task(
                    self._read_stream(path, name), name=f"run-manager-{name}"
                )
            )
        self._wait_task = asyncio.create_task(
            self._await_exit(), name="run-manager-wait"
        )

    async def _read_stream(self, path: Path, name: str) -> None:
        pending = b""
        try:
            with path.open("rb") as stream:
                while True:
                    running = self.is_running
                    raw = stream.readline()
                    if raw:
                        pending += raw
                        if pending.endswith(b"\n"):
                            self._dispatch_line(
                                name,
                                pending.decode("utf-8", errors="replace").rstrip("\n"),
                            )
                            pending = b""
                        await asyncio.sleep(0)
                        continue
                    if not running:
                        if pending:
                            self._dispatch_line(
                                name, pending.decode("utf-8", errors="replace")
                            )
                        return
                    await asyncio.sleep(0.05)
        except OSError as exc:  # pragma: no cover - defensive
            self._dispatch_line(name, f"<stream error: {exc}>")

    async def _await_exit(self) -> None:
        if self._process is None:
            return
        while self.is_running:
            await asyncio.sleep(0.05)
        await asyncio.gather(*self._reader_tasks)
        self.state.finished = True
        self.state.exit_code = self._process.returncode
        self._dispatch_exit(self.state.exit_code)

    async def detach(self) -> None:
        """Stop TUI monitoring while the child keeps writing its log files."""

        self.state.detach_only = True
        tasks = [*self._reader_tasks]
        if self._wait_task is not None:
            tasks.append(self._wait_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ----- termination -----

    async def terminate(
        self,
        *,
        sig: int = signal.SIGINT,
        kill_after: float = 5.0,
    ) -> None:
        """Send `sig` (default SIGINT) to the child's process group.

        After `kill_after` seconds, escalate to SIGKILL so the TUI is
        never blocked waiting on a misbehaving script.
        """

        if self._process is None or not self.is_running:
            return
        pid = self._process.pid
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            # Fall back to direct signal on the process itself.
            try:
                self._process.send_signal(sig)
            except Exception:  # pragma: no cover - defensive
                return
        try:
            async with asyncio.timeout(kill_after):
                while self.is_running:
                    await asyncio.sleep(0.05)
        except TimeoutError:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                self._process.kill()
            while self.is_running:
                await asyncio.sleep(0.05)
        if self._wait_task is not None and not self._wait_task.cancelled():
            await self._wait_task

    # ----- dispatch helpers -----

    def _dispatch_line(self, stream: str, line: str) -> None:
        try:
            self._on_line(stream, line)
        except Exception:  # pragma: no cover - defensive
            # A misbehaving callback must not crash the reader loop.
            pass

    def _dispatch_exit(self, code: int | None) -> None:
        try:
            self._on_exit(code)
        except Exception:  # pragma: no cover - defensive
            pass


def iter_attach_candidates(
    tracker: ExperimentTracker,
    snapshot: Iterable[str],
) -> list[str]:
    """Return experiment ids that are NEW relative to the snapshot.

    Returned in tracker order (typically creation order). Callers pick
    the first as the attach target and surface the rest for switching.
    """

    snap = set(snapshot)
    try:
        existing = tracker.list_experiments()
    except Exception:
        return []
    out: list[str] = []
    for exp in existing:
        exp_id = getattr(exp, "id", None)
        if not isinstance(exp_id, str):
            continue
        if exp_id in snap:
            continue
        out.append(exp_id)
    return out


__all__ = (
    "ExitCallback",
    "LineCallback",
    "RunManager",
    "RunSpec",
    "RunState",
    "iter_attach_candidates",
)
