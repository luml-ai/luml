"""App header bar: product title · clickable breadcrumb · status cluster.

The header is the persistent top chrome shared by every screen. Layout
(left → right):

- the product title ("lumlflow") rendered in the accent color so the
  app feels branded — never blends into content,
- the clickable `Breadcrumb` (filled `1fr` so it grows with the window),
- a right-aligned status cluster: loading spinner, selection chip, the
  live-refresh dot, and the active store path when space permits.

The header replaces what used to be a single flat row (breadcrumb +
status). Indicators are reactive so the app shell can update them by
assigning to the attribute (``self._header.loading = True``) without
querying the indicator widgets directly.
"""

from typing import ClassVar

from rich.text import Text
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from lumlflow.tui.widgets.breadcrumb import Breadcrumb, BreadcrumbSegment

# Product name shown in the header's leftmost cell. Kept lowercase to
# match the CLI command — the brand identity is "lumlflow", not
# "Lumlflow", even in the headerbar.
PRODUCT_TITLE: str = "lumlflow"


class _StatusIndicator(Static):
    DEFAULT_CSS = """
    _StatusIndicator {
        width: auto;
        height: 1;
        padding: 0 1;
        color: $foreground;
        background: $surface;
    }
    """


class _ProductTitle(Static):
    """Left-aligned brand mark."""

    DEFAULT_CSS = """
    _ProductTitle {
        width: auto;
        height: 1;
        padding: 0 1;
        color: $accent;
        background: $surface;
        text-style: bold;
    }
    """


class StatusHeader(Horizontal):
    """Product title + breadcrumb + status indicators in a single bar."""

    DEFAULT_CSS = """
    StatusHeader {
        dock: top;
        height: 1;
        background: $surface;
    }
    StatusHeader > Breadcrumb {
        width: 1fr;
    }
    """

    auto_refresh_on: reactive[bool] = reactive(True)
    selection_count: reactive[int] = reactive(0)
    loading: reactive[bool] = reactive(False)
    store_label: reactive[str] = reactive("")

    SPINNER_FRAMES: ClassVar[tuple[str, ...]] = (
        "⠋",
        "⠙",
        "⠹",
        "⠸",
        "⠼",
        "⠴",
        "⠦",
        "⠧",
        "⠇",
        "⠏",
    )

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._title = _ProductTitle(PRODUCT_TITLE, id="app-title")
        self._breadcrumb = Breadcrumb(id="breadcrumb")
        self._loading_indicator = _StatusIndicator("", id="status-loading")
        self._refresh_indicator = _StatusIndicator("", id="status-refresh")
        self._selection_indicator = _StatusIndicator("", id="status-selection")
        self._store_indicator = _StatusIndicator("", id="status-store")
        self._spinner_index = 0

    def compose(self):  # type: ignore[override]
        yield self._title
        yield self._breadcrumb
        yield self._loading_indicator
        yield self._selection_indicator
        yield self._store_indicator
        yield self._refresh_indicator

    def on_mount(self) -> None:
        self._refresh_status_indicators()
        self.set_interval(0.1, self._tick_spinner)

    def set_breadcrumb(self, segments: tuple[BreadcrumbSegment, ...]) -> None:
        self._breadcrumb.set_segments(segments)

    def set_store_label(self, label: str) -> None:
        self.store_label = label

    def watch_auto_refresh_on(self, _: bool) -> None:
        self._refresh_status_indicators()

    def watch_selection_count(self, _: int) -> None:
        self._refresh_status_indicators()

    def watch_loading(self, _: bool) -> None:
        self._refresh_status_indicators()

    def watch_store_label(self, _: str) -> None:
        self._refresh_status_indicators()

    def _refresh_status_indicators(self) -> None:
        refresh = Text()
        refresh.append("● live" if self.auto_refresh_on else "○ live", style="dim")
        self._refresh_indicator.update(refresh)

        if self.selection_count > 0:
            sel_text = Text(f"✓ {self.selection_count}", style="bold")
            self._selection_indicator.update(sel_text)
            self._selection_indicator.display = True
        else:
            self._selection_indicator.update("")
            self._selection_indicator.display = False

        if not self.loading:
            self._loading_indicator.update("")
            self._loading_indicator.display = False
        else:
            self._loading_indicator.display = True

        if self.store_label:
            self._store_indicator.update(Text(self.store_label, style="dim"))
            self._store_indicator.display = True
        else:
            self._store_indicator.update("")
            self._store_indicator.display = False

    def _tick_spinner(self) -> None:
        if not self.loading:
            return
        self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER_FRAMES)
        frame = self.SPINNER_FRAMES[self._spinner_index]
        self._loading_indicator.update(Text(frame, style="bold"))
