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
- Child stdout/stderr is *piped*; nothing is ever written to the
  terminal, which would corrupt rendering.
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
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
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
    # Snapshot of all experiment ids that existed BEFORE the run started.
    # Used to detect newly created experiments without false positives from
    # the existing store contents.
    experiment_snapshot: set[str] = field(default_factory=set)


class RunManager:
    """Owns the child process, captures its output, and reports state.

    `RunManager` is intentionally framework-agnostic: it does not import
    Textual. The screen that hosts the run pushes line/exit callbacks
    and the manager calls them on the event loop via
    `loop.call_soon_threadsafe(...)` when output arrives.

    The manager exposes a single `start()` coroutine that launches the
    process and spins up two background tasks (stdout/stderr readers).
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
        self._process: asyncio.subprocess.Process | None = None
        self._reader_tasks: list[asyncio.Task[None]] = []
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

    def detect_new_experiments(
        self, *, require_active: bool = True
    ) -> list[str]:
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
        return self._process.returncode is None

    def build_environment(self) -> dict[str, str]:
        """Environment for the child process — shared store URI baked in."""

        env = dict(os.environ if self._env is None else self._env)
        env["BACKEND_STORE_URI"] = self._store_uri
        env["LUML_BACKEND_STORE_URI"] = self._store_uri
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
            self._process = await asyncio.create_subprocess_exec(
                *self.spec.command,
                cwd=self.spec.cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                # Place the child in its own process group so we can target
                # it with SIGINT without taking down the TUI.
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            self.state.started = True
            self.state.finished = True
            self.state.exit_code = 127
            self.state.error_message = str(exc)
            self._dispatch_line("stderr", f"failed to start: {exc}")
            self._dispatch_exit(127)
            return
        except PermissionError as exc:  # pragma: no cover - environment dep
            self.state.started = True
            self.state.finished = True
            self.state.exit_code = 126
            self.state.error_message = str(exc)
            self._dispatch_line("stderr", f"permission denied: {exc}")
            self._dispatch_exit(126)
            return

        self.state.started = True
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._reader_tasks.append(
            asyncio.create_task(
                self._read_stream(self._process.stdout, "stdout"),
                name="run-manager-stdout",
            )
        )
        self._reader_tasks.append(
            asyncio.create_task(
                self._read_stream(self._process.stderr, "stderr"),
                name="run-manager-stderr",
            )
        )
        asyncio.create_task(self._await_exit(), name="run-manager-wait")

    async def _read_stream(
        self, stream: asyncio.StreamReader, name: str
    ) -> None:
        while True:
            try:
                raw = await stream.readline()
            except Exception as exc:  # pragma: no cover - defensive
                self._dispatch_line(name, f"<stream error: {exc}>")
                return
            if not raw:
                return
            try:
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
            except Exception:  # pragma: no cover - defensive
                line = repr(raw)
            self._dispatch_line(name, line)

    async def _await_exit(self) -> None:
        if self._process is None:
            return
        try:
            code = await self._process.wait()
        except Exception:  # pragma: no cover - defensive
            code = None
        # Drain reader tasks so all output is dispatched before exit.
        for task in self._reader_tasks:
            try:
                await task
            except Exception:  # pragma: no cover - defensive
                pass
        self.state.finished = True
        self.state.exit_code = code
        self._dispatch_exit(code)

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

        if self._process is None or self._process.returncode is not None:
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
        # Schedule an escalation if the process does not exit in time.
        try:
            await asyncio.wait_for(self._process.wait(), timeout=kill_after)
        except TimeoutError:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    self._process.kill()
                except Exception:  # pragma: no cover - defensive
                    pass

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
