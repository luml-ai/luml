"""Run-and-attach screen.

Launched when the user invokes `lumlflow tui <script> [args...]`.
The screen runs the script as a child process (sharing the SQLite
store via the `BACKEND_STORE_URI` env var), captures its stdout/stderr
into a scrollable log pane, and watches the tracker for a newly
created `active` experiment so the TUI can auto-navigate into its live
detail screen.

Lifecycle:

- On mount, the script process is launched and the log pane is shown.
- A short-interval timer polls the tracker for new experiment ids
  (using `RunManager.detect_new_experiments`). When the first one
  appears, the screen pushes the `ExperimentDetailScreen` and stops
  polling for attach. Additional new experiments are surfaced as a
  toast so the user knows they exist.
- If the script exits without ever creating an experiment, the timer
  is stopped and a status message is shown in the log pane; the screen
  remains usable as a browser shell.
- If the script exits with a non-zero code, the exit code is surfaced
  in the log pane as an error status.
- `Ctrl-C` (the `stop_run` action) terminates the child process.
- Quitting the app while the child runs prompts the user to choose
  terminate-or-detach (handled at app level via the quit hook).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from textual import work
from textual.binding import Binding
from textual.containers import Container
from textual.timer import Timer
from textual.widgets import Static

from lumlflow.tui.data import DataFacade
from lumlflow.tui.keymap import Scope
from lumlflow.tui.run_manager import RunManager, RunSpec
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment, RunLogPane

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp

# How often to poll the tracker for newly created experiments. Kept
# short enough that the attach feels immediate even on slow disks, but
# not so short that it spams SQLite when nothing is happening.
ATTACH_POLL_SECONDS = 0.5

# Maximum time to wait for the script to create an experiment before
# the screen says "no experiment was created". This applies even if the
# script is still running — the user is then free to keep watching the
# log, but the polling stops to avoid an ever-running timer.
DEFAULT_ATTACH_TIMEOUT = 60.0


class RunAttachScreen(BaseScreen):
    """Shows the run's log pane and auto-navigates on first new experiment."""

    DEFAULT_CSS = """
    RunAttachScreen {
        layout: vertical;
    }
    RunAttachScreen #run-body {
        height: 1fr;
        layout: vertical;
        padding: 1 2;
    }
    RunAttachScreen #run-meta {
        height: auto;
        padding-bottom: 1;
        color: $text-muted;
    }
    RunAttachScreen #run-status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        # Ctrl-C targets the *run*, not the app, while this screen is active.
        # The app-level `quit` action only fires if no run is in flight (the
        # screen consumes the keypress when the child is running).
        Binding("ctrl+c", "stop_run", "Stop run", show=False),
        Binding("s", "stop_run", "Stop run", show=False),
    ]

    breadcrumb_label = "Run"

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        spec: RunSpec,
        store_uri: str,
        attach_timeout: float = DEFAULT_ATTACH_TIMEOUT,
        attach_poll_seconds: float = ATTACH_POLL_SECONDS,
        auto_navigate: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id, breadcrumb_label=self.breadcrumb_label)
        self._facade = facade
        self._spec = spec
        self._store_uri = store_uri
        self._attach_timeout = attach_timeout
        self._attach_poll_seconds = attach_poll_seconds
        self._auto_navigate = auto_navigate
        self._run: RunManager | None = None
        self._poll_timer: Timer | None = None
        self._elapsed_polling: float = 0.0
        self._attached_id: str | None = None
        self._attach_announced: bool = False
        self._extra_new_ids: list[str] = []
        # Track whether the script has exited so the quit prompt can
        # answer "no, the child is already gone".
        self._exited: bool = False

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="run-body"):
            yield Static("", id="run-meta")
            yield RunLogPane(id="run-log")
            yield Static("Waiting for experiment…", id="run-status")

    def on_mount(self) -> None:
        meta = self.query_one("#run-meta", Static)
        meta.update(f"Running: {self._spec.describe()}")
        log = self.query_one("#run-log", RunLogPane)
        log.append_status(f"$ {self._spec.describe()}", level="info")
        facade = self.facade
        if facade is None:
            log.append_status(
                "facade unavailable; cannot launch process", level="error"
            )
            return
        self._run = RunManager(
            spec=self._spec,
            tracker=facade.tracker,
            store_uri=self._store_uri,
            on_line=self._on_line,
            on_exit=self._on_exit,
        )
        # Kick off the subprocess; this is async because we need an event
        # loop for `create_subprocess_exec`. The poll timer is started
        # once the process has been kicked off (the snapshot must be
        # taken before any new experiment lands). `@work` makes this a
        # fire-and-forget Worker; no await is needed.
        self._start_subprocess()  # noqa: F841

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        return (BreadcrumbSegment("Run"),)

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global",)

    # ----- facade access -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        return getattr(self.app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- subprocess lifecycle -----

    @work(group="run-attach-start")
    async def _start_subprocess(self) -> None:
        if self._run is None:
            return
        await self._run.start()
        # Once the process has been kicked off (or rejected), start the
        # attach poll loop. `@work` without `thread=True` runs the body
        # on the event loop, so we can schedule the timer directly.
        self._start_polling()

    def _start_polling(self) -> None:
        if self._poll_timer is not None:
            return
        self._poll_timer = self.set_interval(
            self._attach_poll_seconds, self._tick_attach
        )

    # ----- log dispatch -----

    def _on_line(self, stream: str, line: str) -> None:
        # `_on_line` is called from a reader task — same loop, so direct
        # widget calls are safe. Guard against the widget being torn
        # down (the screen may be popped while the script is mid-write).
        try:
            log = self.query_one("#run-log", RunLogPane)
        except Exception:
            return
        log.append_line(stream, line)

    def _on_exit(self, code: int | None) -> None:
        self._exited = True
        try:
            log = self.query_one("#run-log", RunLogPane)
        except Exception:
            log = None
        if log is not None:
            if code is None:
                log.append_status("process terminated", level="warning")
            elif code == 0:
                log.append_status("process exited 0", level="success")
            else:
                log.append_status(
                    f"process exited with code {code}", level="error"
                )
        self._refresh_status_line()
        # The script has finished; surface the no-experiment outcome
        # immediately rather than waiting for the timeout.
        if self._attached_id is None:
            # Give the poll one more chance — the script may have
            # created the experiment just before exiting and the
            # tracker may not have flushed yet.
            self.set_timer(0.1, self._maybe_report_no_experiment)

    def _maybe_report_no_experiment(self) -> None:
        if self._attached_id is not None:
            return
        # Try one more attach cycle synchronously. After the child has
        # exited, a fast-running script's experiment may have already
        # flipped from `active` → `completed`/`error`; relax the active
        # filter so we still attach to *something* the child produced
        # rather than reporting "no experiment was created" when one
        # plainly was.
        self._tick_attach(require_active=False)
        if self._attached_id is not None:
            return
        self._announce_no_experiment()

    # ----- attach polling -----

    def _tick_attach(self, *, require_active: bool = True) -> None:
        run = self._run
        if run is None:
            return
        if self._attached_id is not None:
            self._stop_polling()
            return
        candidates = run.detect_new_experiments(require_active=require_active)
        if not candidates:
            self._elapsed_polling += self._attach_poll_seconds
            if self._elapsed_polling >= self._attach_timeout:
                self._stop_polling()
                self._announce_no_experiment()
            return
        # First candidate becomes the attach target; the rest get
        # surfaced as a toast so the user can switch to them.
        self._attached_id = candidates[0]
        self._extra_new_ids = candidates[1:]
        self._stop_polling()
        self._announce_attached(candidates[0])
        if self._extra_new_ids:
            self._lumlflow_app.show_toast(
                f"{len(self._extra_new_ids)} additional new experiment(s) — "
                "open from the experiments list.",
                severity="info",
                duration=4.0,
            )
        if self._auto_navigate:
            self._navigate_to_detail(candidates[0])

    def _stop_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def _announce_attached(self, experiment_id: str) -> None:
        if self._attach_announced:
            return
        self._attach_announced = True
        try:
            log = self.query_one("#run-log", RunLogPane)
        except Exception:
            log = None
        if log is not None:
            log.append_status(
                f"attached to experiment {experiment_id}", level="success"
            )
        self._refresh_status_line()

    def _announce_no_experiment(self) -> None:
        try:
            log = self.query_one("#run-log", RunLogPane)
        except Exception:
            log = None
        if log is not None:
            log.append_status(
                "no experiment was created by this script.", level="warning"
            )
        self._refresh_status_line()

    def _refresh_status_line(self) -> None:
        try:
            status = self.query_one("#run-status", Static)
        except Exception:
            return
        bits: list[str] = []
        if self._attached_id is not None:
            bits.append(f"attached: {self._attached_id}")
        elif self._exited:
            bits.append("script exited; no experiment attached")
        else:
            bits.append("waiting for experiment…")
        if self._run is not None:
            if self._run.state.exit_code is not None:
                bits.append(f"exit {self._run.state.exit_code}")
            elif self._run.is_running:
                bits.append("running")
        status.update("  ·  ".join(bits))

    def _navigate_to_detail(self, experiment_id: str) -> None:
        # Lazy import: the screen module imports from this one when
        # constructing the app, so we keep this local to avoid an
        # import cycle.
        from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen

        try:
            screen = ExperimentDetailScreen(
                facade=self.facade,
                experiment_id=experiment_id,
                experiment_name=None,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._lumlflow_app.show_toast(
                f"Could not open experiment detail: {exc}", severity="error"
            )
            return
        self.app.push_screen(screen)

    # ----- termination -----

    def action_stop_run(self) -> None:
        run = self._run
        if run is None or self._exited:
            return
        self._lumlflow_app.show_toast(
            "Stopping run…", severity="info", duration=1.5
        )
        # Schedule the async terminate on the loop.
        asyncio.create_task(run.terminate(), name="run-attach-terminate")

    async def terminate_child(self) -> None:
        """Public hook for the app's quit-confirm flow.

        Awaited by the app so the quit completes only once the child
        has exited (or been killed).
        """

        run = self._run
        if run is None:
            return
        await run.terminate()

    # The screen has no live-refresh hook — the experiment detail screen
    # we navigate into provides its own. While we are still on this
    # screen, the global refresh scheduler is a no-op because we don't
    # implement `refresh_live()`.


__all__ = ("RunAttachScreen", "ATTACH_POLL_SECONDS", "DEFAULT_ATTACH_TIMEOUT")
