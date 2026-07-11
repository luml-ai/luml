"""Breadcrumb widget rendered in the app header."""

from dataclasses import dataclass
from typing import ClassVar

from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


@dataclass(frozen=True)
class BreadcrumbSegment:
    label: str
    target: str | None = None


class Breadcrumb(Static):
    """Clickable breadcrumb of the navigation stack."""

    DEFAULT_CSS = """
    Breadcrumb {
        height: 1;
        padding: 0 1;
        color: $foreground;
        background: $surface;
    }
    """

    SEPARATOR: ClassVar[str] = " › "

    segments: reactive[tuple[BreadcrumbSegment, ...]] = reactive(tuple)

    class SegmentClicked(Message):
        def __init__(self, segment: BreadcrumbSegment, index: int) -> None:
            super().__init__()
            self.segment = segment
            self.index = index

    def __init__(
        self,
        segments: tuple[BreadcrumbSegment, ...] = (),
        *,
        id: str | None = None,
    ) -> None:
        super().__init__("", id=id)
        self.segments = segments

    def set_segments(self, segments: tuple[BreadcrumbSegment, ...]) -> None:
        self.segments = segments

    def watch_segments(self, segments: tuple[BreadcrumbSegment, ...]) -> None:
        text = Text(no_wrap=True, overflow="ellipsis")
        for i, segment in enumerate(segments):
            if i > 0:
                text.append(self.SEPARATOR, style="dim")
            style = "bold" if i == len(segments) - 1 else "underline"
            text.append(segment.label, style=style)
        self.update(text)

    async def on_click(self, event: Click) -> None:
        if not self.segments:
            return
        text_x = event.x - 1
        if text_x < 0:
            return
        cursor = 0
        for index, segment in enumerate(self.segments):
            seg_end = cursor + len(segment.label)
            if cursor <= text_x < seg_end:
                self.post_message(self.SegmentClicked(segment, index))
                return
            cursor = seg_end + len(self.SEPARATOR)
