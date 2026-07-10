"""Live auto-refresh scheduler.

A background scheduler that periodically asks the currently visible
screen to re-fetch its data (on a worker thread), diff it against what
is displayed, and apply only the changes in place — preserving the
user's cursor, selection, and scroll position. Newly appeared rows,
status flips, in-progress traces becoming `ok`/`error`, and new metric
points appear without a manual reload, with a brief pulse on what
changed.

Key contracts (from SPEC.md):

- Refresh runs on a worker — the event loop never blocks.
- Refresh pauses while a modal/dialog is open so the underlying list
  does not shift under the dialog. The app already tracks
  `_open_dialog_count`; the scheduler reads `LumlflowApp.is_refresh_paused`.
- Refresh only re-reads the visible window. It never widens its working
  set as a run grows; memory stays bounded.
- The interval is configurable per-app (`refresh_interval`), and there
  is a manual-refresh action (`r`) that runs one cycle immediately
  regardless of the toggle.

Screens opt in by implementing the `LiveRefreshable` protocol — a
`refresh_live()` method that runs in the worker (it is synchronous and
returns nothing). Screens that don't implement it are simply skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from textual.timer import Timer

    from lumlflow.tui.app import LumlflowApp


@runtime_checkable
class LiveRefreshable(Protocol):
    """A screen (or widget) that can refresh its data in place.

    The contract is intentionally simple: the scheduler calls
    `refresh_live()` on the foreground screen at the configured cadence.
    The implementation runs whatever read/diff/apply work it needs to
    keep its view up to date, scheduling actual SQLite calls on a worker
    thread (typically via `@work(thread=True)` or
    `run_worker(fn, thread=True)`). Implementations must preserve the
    user's cursor/scroll/selection.
    """

    def refresh_live(self) -> None: ...  # pragma: no cover - protocol


class LiveRefreshScheduler:
    """Periodically asks the foreground screen to refresh in place.

    One instance per app, owned by `LumlflowApp`. The scheduler holds a
    single `Timer` and calls `_tick` on every interval. Inside `_tick`
    it checks whether refresh is currently active (toggle on AND no
    open dialogs) and, if so, asks the current screen to refresh its
    visible window.

    The scheduler is intentionally dumb about *what* gets refreshed —
    that decision belongs to the screen. The screen knows which rows
    are visible, which tab is active, and how to merge the new page
    into its table without disturbing the user's cursor.
    """

    def __init__(self, app: LumlflowApp, *, interval: float) -> None:
        self._app = app
        self._interval = max(0.1, interval)
        self._timer: Timer | None = None

    # ----- lifecycle -----

    def start(self) -> None:
        """Begin firing on the configured interval.

        Called once by the app on mount. Re-entrant: calling `start()`
        on a running scheduler is a no-op.
        """

        if self._timer is not None:
            return
        # `set_interval` returns a `Timer` whose callback is invoked
        # on the event loop. The callback itself does no blocking
        # work — it only delegates to the foreground screen which
        # then schedules a worker thread.
        self._timer = self._app.set_interval(self._interval, self._tick)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    # ----- interval -----

    @property
    def interval(self) -> float:
        return self._interval

    def set_interval(self, interval: float) -> None:
        """Reconfigure the refresh interval at runtime.

        Restarts the timer so the new interval takes effect on the
        next cycle.
        """

        new_interval = max(0.1, interval)
        if new_interval == self._interval and self._timer is not None:
            return
        self._interval = new_interval
        if self._timer is not None:
            self.stop()
            self.start()

    # ----- ticks -----

    def _tick(self) -> None:
        """One refresh cycle.

        Called by the timer on the event loop. The scheduler reads the
        toggle and the dialog-open count and either skips the cycle or
        delegates to the current screen. The screen's `refresh_live()`
        is responsible for offloading any SQLite work to a worker.
        """

        if not self._app.live_refresh_on:
            return
        if self._app.is_refresh_paused:
            return
        self.refresh_now()

    def refresh_now(self) -> None:
        """Trigger a single refresh cycle immediately.

        Used by the `r` key — a manual refresh fires even when the
        live-refresh toggle is off, so users can pull updates on
        demand without enabling continuous refresh.
        """

        screen = self._app.screen
        if not isinstance(screen, LiveRefreshable):
            return
        try:
            screen.refresh_live()
        except Exception as exc:  # pragma: no cover - defensive
            # A misbehaving screen must not crash the scheduler.
            # Surface the error as a toast and continue.
            self._app.show_toast(
                f"Refresh failed: {exc}", severity="error", duration=2.5
            )


__all__ = ("LiveRefreshable", "LiveRefreshScheduler")
