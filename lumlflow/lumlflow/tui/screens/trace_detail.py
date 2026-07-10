"""Trace detail screen — span tree + span detail + annotations.

The screen renders a single trace's span hierarchy as a Textual ``Tree``
with **inline, time-proportional waterfall bars** and span-type
icons/colors, flanked by a structured span detail pane (header,
attributes, events, status) and the per-span annotations table. Span
annotations support full create / edit / delete via the
``AnnotationDialog`` and the facade's
``create_span_annotation`` / ``update_span_annotation`` /
``delete_span_annotation`` methods.

Performance considerations the SPEC calls out:

- The span tree uses Textual's ``Tree`` widget which materialises only
  the visible nodes (virtualization), so deeply-nested traces with
  thousands of spans stay smooth.
- Auto-collapse rule: traces with more than ``AUTO_COLLAPSE_THRESHOLD``
  spans render with subtrees collapsed by default so the initial view
  is concise. Root nodes stay expanded so structure is always visible.
- ``E``/``C`` expand-all / collapse-all the entire tree in one keystroke.
- The detail pane and annotation list update from the cached
  ``TraceDetails`` — only annotation reads hit the store on demand.

Two focusable panes (tree + detail/annotations) participate in the
``Tab`` / ``Shift-Tab`` focus cycle, both wrapped in ``PanelFrame``s so
the active pane is visually highlighted via the standard accent
border. The span tree is auto-focused on mount so ``j``/``k``/``Enter``
work without a preliminary ``Tab``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import DataTable, Static, Tree
from textual.widgets.tree import TreeNode

from lumlflow.schemas.annotations import (
    Annotation,
    AnnotationKind,
    CreateAnnotation,
    UpdateAnnotation,
)
from lumlflow.schemas.experiments import Span, TraceDetails
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment, PanelFrame
from lumlflow.tui.widgets.annotation_dialog import (
    AnnotationDialog,
    AnnotationDialogResult,
)
from lumlflow.tui.widgets.dialogs import ConfirmDialog

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp

# Auto-collapse trees with more than this many spans so initial render
# stays scannable on large traces. The user expands explicitly with `l`
# (single node) or `E` (whole tree).
AUTO_COLLAPSE_THRESHOLD = 30

# OTel span status codes (matches the SDK's `log_span(status_code=...)`).
_STATUS_OK = 1
_STATUS_ERROR = 2

# Plain style names used through `Static.update` / Text rendering. CSS
# variables don't expand here — these are direct Rich style names.
_SPAN_STATUS_STYLE: dict[int, str] = {
    _STATUS_OK: "bold green",
    _STATUS_ERROR: "bold red",
}

# Number of cells used to render the inline waterfall bar. Keep modest
# so very deep / wide trees still leave room for the span name on a
# narrow terminal.
_WATERFALL_WIDTH = 16


# Span-type icon + Rich style by ``dfs_span_type`` (mirrors the web
# UI's category icons). Values follow ``SpanTypeEnum`` from the JS
# experiments package:
#   0 = DEFAULT, 1 = CHAT, 2 = AGENT, 3 = TOOL, 4 = EMBEDDER, 5 = RERANKER
_SPAN_TYPE_GLYPH: dict[int, tuple[str, str]] = {
    0: ("•", "dim"),
    1: ("◆", "cyan"),
    2: ("★", "magenta"),
    3: ("⚙", "yellow"),
    4: ("≋", "blue"),
    5: ("⇅", "green"),
}


def _span_type_glyph(span_type: int | None) -> tuple[str, str]:
    if span_type is None:
        return _SPAN_TYPE_GLYPH[0]
    return _SPAN_TYPE_GLYPH.get(span_type, _SPAN_TYPE_GLYPH[0])


def _format_duration_ns(start_ns: int, end_ns: int) -> str:
    """Format a nanosecond span duration as a compact label."""

    if end_ns < start_ns:
        return "—"
    delta_ns = end_ns - start_ns
    if delta_ns < 1_000:
        return f"{delta_ns} ns"
    if delta_ns < 1_000_000:
        return f"{delta_ns / 1_000:.1f} µs"
    if delta_ns < 1_000_000_000:
        return f"{delta_ns / 1_000_000:.1f} ms"
    seconds = delta_ns / 1_000_000_000
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, sec = divmod(int(seconds), 60)
    return f"{minutes}m {sec:02d}s"


def _format_event_offset_ns(offset_ns: int) -> str:
    """Format an event offset (``event.timestamp - trace_start``) compactly."""

    if offset_ns < 0:
        # An event before the trace window — surface as a negative offset
        # rather than hiding the anomaly.
        return f"-{_format_duration_ns(0, -offset_ns)}"
    return f"+{_format_duration_ns(0, offset_ns)}"


def _format_value(value: int | bool | str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def waterfall_geometry(
    span_start: int,
    span_end: int,
    trace_start: int,
    trace_end: int,
    width: int = _WATERFALL_WIDTH,
) -> tuple[int, int]:
    """Return ``(leading_blanks, bar_cells)`` for a span's waterfall bar.

    Maps the span's ``[start, end]`` interval to the trace window
    ``[trace_start, trace_end]`` projected over ``width`` cells. The bar
    is at least one cell wide so even instantaneous spans remain visible.
    """

    if width <= 0:
        return (0, 0)
    trace_span = max(1, trace_end - trace_start)
    duration = max(0, span_end - span_start)
    start_offset = max(0, span_start - trace_start)
    leading = int((start_offset / trace_span) * width)
    leading = max(0, min(width - 1, leading))
    bar = int(round((duration / trace_span) * width))
    bar = max(1, min(width - leading, bar)) if duration > 0 else 1
    return leading, bar


@dataclass
class _SpanNode:
    """Span row with cached fields used by the tree label + detail panel."""

    span: Span
    children: list[_SpanNode]


def _build_span_tree(spans: list[Span]) -> list[_SpanNode]:
    """Build the parent → children adjacency from a flat span list.

    Orphaned spans (whose ``parent_span_id`` references a span that
    isn't in the list) are treated as roots so the trace is still
    navigable even with a malformed parent chain.
    """

    by_id: dict[str, _SpanNode] = {
        s.span_id: _SpanNode(span=s, children=[]) for s in spans
    }
    roots: list[_SpanNode] = []
    for span in spans:
        node = by_id[span.span_id]
        parent_id = span.parent_span_id
        if parent_id and parent_id in by_id:
            by_id[parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def _trace_window(spans: Iterable[Span]) -> tuple[int, int]:
    """Return the ``(min_start, max_end)`` over a span sequence."""

    spans_list = list(spans)
    if not spans_list:
        return (0, 0)
    start = min(s.start_time_unix_nano for s in spans_list)
    end = max(s.end_time_unix_nano for s in spans_list)
    if end <= start:
        end = start + 1
    return start, end


class TraceDetailScreen(BaseScreen):
    """Span tree + span detail + annotations CRUD for one trace.

    Two focusable panes — the span tree on the left and the detail /
    annotations on the right. ``Tab`` / ``Shift-Tab`` (handled by the
    app shell) cycles between them; the active pane's ``PanelFrame``
    border switches to the accent color. ``Enter`` on a tree node
    mirrors the span detail; ``a`` / ``e`` / ``d`` manipulate
    annotations on the focused span; ``E`` / ``C`` expand / collapse the
    whole tree in one keystroke.
    """

    DEFAULT_CSS = """
    TraceDetailScreen {
        layout: vertical;
    }
    TraceDetailScreen #trace-detail-body {
        height: 1fr;
        layout: horizontal;
    }
    TraceDetailScreen #span-tree-panel {
        width: 60%;
        height: 1fr;
    }
    TraceDetailScreen #span-detail-panel {
        width: 1fr;
        height: 1fr;
    }
    TraceDetailScreen #span-tree {
        height: 1fr;
    }
    TraceDetailScreen #trace-summary {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    TraceDetailScreen #span-detail-scroll {
        height: 1fr;
    }
    TraceDetailScreen #span-detail-header {
        height: auto;
        padding-bottom: 1;
    }
    TraceDetailScreen #span-detail-attrs,
    TraceDetailScreen #span-detail-events {
        height: auto;
        padding-bottom: 1;
    }
    TraceDetailScreen .section-title {
        text-style: bold;
        padding-top: 1;
        color: $text-muted;
    }
    TraceDetailScreen #span-annotations-table {
        height: auto;
        max-height: 12;
    }
    """

    BINDINGS = [
        Binding("a", "annotate", "Annotate", show=False),
        Binding("e", "edit_annotation", "Edit annotation", show=False),
        Binding("d", "delete_annotation", "Delete annotation", show=False),
        Binding("y", "yank", "Yank span id", show=False),
        Binding("E", "expand_all", "Expand all", show=False),
        Binding("C", "collapse_all", "Collapse all", show=False),
    ]

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        experiment_id: str,
        experiment_name: str | None = None,
        group_name: str | None = None,
        trace_id: str,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._experiment_id = experiment_id
        self._experiment_name = experiment_name
        self._group_name = group_name
        self._trace_id = trace_id
        self._details: TraceDetails | None = None
        self._spans_by_id: dict[str, Span] = {}
        # The Tree's node `data` field stores the span_id; mapping in the
        # other direction lets us scroll to a span on the fly.
        self._tree_nodes: dict[str, TreeNode[str]] = {}
        self._selected_span_id: str | None = None
        self._span_annotations: list[Annotation] = []
        # Cached trace window used to project waterfall bars.
        self._trace_window_start: int = 0
        self._trace_window_end: int = 1
        # Set when the user is editing a known annotation so the dialog
        # callback can route to the right path.
        self._editing_annotation_id: str | None = None

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="trace-detail-body"):
            with PanelFrame(
                title="Spans",
                fill=True,
                id="span-tree-panel",
            ):
                yield Static("", id="trace-summary")
                yield Tree("trace", id="span-tree")
            with PanelFrame(
                title="Detail",
                fill=True,
                id="span-detail-panel",
            ):
                with VerticalScroll(id="span-detail-scroll"):
                    yield Static(
                        "Select a span to see its detail.",
                        id="span-detail-header",
                    )
                    yield Static("Attributes", classes="section-title")
                    yield Static("", id="span-detail-attrs")
                    yield Static("Events", classes="section-title")
                    yield Static("", id="span-detail-events")
                    yield Static("Annotations", classes="section-title")
                    yield DataTable(
                        id="span-annotations-table",
                        cursor_type="row",
                        zebra_stripes=True,
                    )

    def on_mount(self) -> None:
        # The children may not yet be mounted when the screen's
        # `on_mount` fires (Textual mounts them asynchronously); defer
        # setup to the next refresh cycle if so.
        if not self._init_widgets():
            self.call_after_refresh(self._init_widgets)
        # Trigger the initial fetch.
        if self.facade is not None:
            self._fetch_trace()

    def _init_widgets(self) -> bool:
        try:
            table = self.query_one("#span-annotations-table", DataTable)
            tree = self.query_one("#span-tree", Tree)
        except Exception:
            return False
        if not table.columns:
            table.add_columns("Name", "Kind", "Type", "Value", "Rationale")
        tree.show_root = False
        tree.guide_depth = 2
        # Auto-focus the span tree so navigation keys work immediately
        # when the user arrives from a trace list drill-in.
        tree.focus()
        return True

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        segments = [BreadcrumbSegment("Groups")]
        if self._group_name:
            segments.append(BreadcrumbSegment(self._group_name))
        if self._experiment_name:
            segments.append(BreadcrumbSegment(self._experiment_name))
        segments.append(BreadcrumbSegment(f"Trace {self._trace_id[:8]}"))
        return tuple(segments)

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global", "span_tree", "annotations")

    def focusable_panes(self) -> Iterable:
        try:
            return (
                self.query_one("#span-tree", Tree),
                self.query_one("#span-annotations-table", DataTable),
            )
        except Exception:
            return ()

    # ----- facade access -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        return getattr(self.app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- trace fetch + tree population -----

    @work(thread=True, exclusive=True, group="trace-detail")
    def _fetch_trace(self) -> None:
        facade = self.facade
        if facade is None:
            self.app.call_from_thread(
                self._on_trace_failure, "facade unavailable"
            )
            return
        result = facade.get_trace(self._experiment_id, self._trace_id)
        self.app.call_from_thread(self._on_trace_result, result)

    def _on_trace_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "unknown error"
            self._on_trace_failure(msg)
            return
        details: TraceDetails = result.unwrap()
        self._details = details
        self._spans_by_id = {s.span_id: s for s in details.spans}
        self._trace_window_start, self._trace_window_end = _trace_window(
            details.spans
        )
        self._populate_tree(details.spans)
        self._update_trace_summary()
        # Auto-select the first root span so the detail pane has content.
        if details.spans:
            self._set_selected_span(details.spans[0].span_id, scroll=True)

    def _on_trace_failure(self, message: str) -> None:
        self._lumlflow_app.show_toast(
            f"Could not load trace: {message}", severity="error"
        )
        try:
            self.query_one("#span-detail-header", Static).update(
                f"Could not load trace: {message}"
            )
        except Exception:
            pass

    def _populate_tree(self, spans: list[Span]) -> None:
        tree = self.query_one("#span-tree", Tree)
        tree.clear()
        self._tree_nodes.clear()
        roots = _build_span_tree(spans)
        auto_collapse = len(spans) > AUTO_COLLAPSE_THRESHOLD

        def add_subtree(parent_node: TreeNode[str], items: list[_SpanNode]) -> None:
            for item in items:
                label = self._render_span_label(item.span)
                expand = not auto_collapse
                if item.children:
                    node = parent_node.add(
                        label,
                        data=item.span.span_id,
                        expand=expand,
                        allow_expand=True,
                    )
                    add_subtree(node, item.children)
                else:
                    node = parent_node.add_leaf(
                        label, data=item.span.span_id
                    )
                self._tree_nodes[item.span.span_id] = node

        add_subtree(tree.root, roots)
        # The root is hidden (`show_root = False`); expand it so first-level
        # spans are always visible regardless of auto-collapse.
        tree.root.expand()

    def _render_span_label(self, span: Span) -> Text:
        """Build the tree-row label: status · type-icon · waterfall · name · duration.

        The waterfall bar is rendered as ``leading-blanks + bar`` so the
        bar's horizontal position encodes the span's start offset within
        the trace window, and its length encodes the duration. Error
        spans use the error color so they pop out of the tree.
        """

        text = Text()
        is_error = span.status_code == _STATUS_ERROR
        # Status indicator: red dot for ERROR, green for OK, dim otherwise.
        if is_error:
            text.append("● ", style="bold red")
        elif span.status_code == _STATUS_OK:
            text.append("● ", style="bold green")
        else:
            text.append("○ ", style="dim")
        # Span-type icon (chat / agent / tool / embedder / reranker / default).
        glyph, glyph_style = _span_type_glyph(span.dfs_span_type)
        text.append(f"{glyph} ", style=glyph_style)
        # Inline time-proportional waterfall bar.
        leading, bar_cells = waterfall_geometry(
            span.start_time_unix_nano,
            span.end_time_unix_nano,
            self._trace_window_start,
            self._trace_window_end,
        )
        bar_style = "red" if is_error else "cyan"
        text.append(" " * leading)
        text.append("█" * bar_cells, style=bar_style)
        # Padding after the bar so the name doesn't reflow as bars shift.
        trailing = max(0, _WATERFALL_WIDTH - leading - bar_cells)
        text.append(" " * trailing)
        text.append("  ")
        # Span name + duration.
        name_style = "bold red" if is_error else "bold"
        text.append(span.name, style=name_style)
        duration = _format_duration_ns(
            span.start_time_unix_nano, span.end_time_unix_nano
        )
        text.append(f"  {duration}", style="dim")
        if span.annotation_count:
            text.append(f"  ✎{span.annotation_count}", style="bold yellow")
        return text

    def _update_trace_summary(self) -> None:
        try:
            summary = self.query_one("#trace-summary", Static)
        except Exception:
            return
        if self._details is None:
            summary.update("")
            return
        total = len(self._details.spans)
        errors = sum(
            1
            for s in self._details.spans
            if s.status_code == _STATUS_ERROR
        )
        bits = [f"{total} span{'s' if total != 1 else ''}"]
        if errors:
            bits.append(f"{errors} error{'s' if errors != 1 else ''}")
        summary.update("  ·  ".join(bits))

    # ----- expand-all / collapse-all -----

    def action_expand_all(self) -> None:
        try:
            tree = self.query_one("#span-tree", Tree)
        except Exception:
            return
        for node in self._tree_nodes.values():
            node.expand()
        tree.root.expand()

    def action_collapse_all(self) -> None:
        for node in self._tree_nodes.values():
            node.collapse()

    # ----- selection / detail rendering -----

    def _set_selected_span(self, span_id: str, *, scroll: bool = False) -> None:
        if span_id not in self._spans_by_id:
            return
        self._selected_span_id = span_id
        node = self._tree_nodes.get(span_id)
        if node is not None and scroll:
            try:
                tree = self.query_one("#span-tree", Tree)
                tree.select_node(node)
                tree.scroll_to_node(node)
            except Exception:
                pass
        span = self._spans_by_id[span_id]
        self._render_span_detail(span)
        self._fetch_span_annotations(span_id)

    def _render_span_detail(self, span: Span) -> None:
        try:
            header = self.query_one("#span-detail-header", Static)
            attrs = self.query_one("#span-detail-attrs", Static)
            events = self.query_one("#span-detail-events", Static)
        except Exception:
            return
        # ----- header (name, status, duration, ids, status message) -----
        head = Text()
        head.append(span.name, style="bold")
        head.append("\n")
        head.append("status: ")
        status_style = _SPAN_STATUS_STYLE.get(
            span.status_code or 0, "dim"
        )
        head.append(
            self._status_label(span.status_code), style=status_style
        )
        head.append("    duration: ")
        head.append(
            _format_duration_ns(
                span.start_time_unix_nano, span.end_time_unix_nano
            ),
            style="dim",
        )
        head.append("\nspan id: ")
        head.append(span.span_id, style="dim")
        if span.parent_span_id:
            head.append("    parent: ")
            head.append(span.parent_span_id, style="dim")
        if span.status_message:
            head.append("\nstatus message: ")
            head.append(span.status_message, style="bold red")
        header.update(head)

        # ----- attributes -----
        if span.attributes:
            text = Text()
            for i, (k, v) in enumerate(span.attributes.items()):
                if i > 0:
                    text.append("\n")
                text.append(f"{k}", style="bold")
                text.append(" = ")
                text.append(f"{v}")
            attrs.update(text)
        else:
            attrs.update(Text("(no attributes)", style="dim"))

        # ----- events -----
        events.update(self._format_events(span))

    def _format_events(self, span: Span) -> Text:
        if not span.events:
            return Text("(no events)", style="dim")
        text = Text()
        trace_start = self._trace_window_start
        for i, event in enumerate(span.events):
            if i > 0:
                text.append("\n")
            if not isinstance(event, dict):
                # Unknown event payload — render as best-effort string.
                text.append(str(event))
                continue
            name = event.get("name") or "(unnamed event)"
            timestamp = event.get("timestamp")
            text.append(str(name), style="bold")
            if isinstance(timestamp, (int, float)):
                offset = int(timestamp) - trace_start
                text.append(
                    f"  {_format_event_offset_ns(offset)}", style="dim"
                )
            attributes = event.get("attributes")
            if isinstance(attributes, dict) and attributes:
                for k, v in attributes.items():
                    text.append("\n  ")
                    text.append(f"{k}", style="dim bold")
                    text.append(" = ")
                    text.append(f"{v}", style="dim")
        return text

    @staticmethod
    def _status_label(status_code: int | None) -> str:
        if status_code == _STATUS_OK:
            return "ok"
        if status_code == _STATUS_ERROR:
            return "error"
        return "unset"

    # ----- annotation fetch + render -----

    @work(thread=True, exclusive=True, group="span-annotations")
    def _fetch_span_annotations(self, span_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.list_span_annotations(
            self._experiment_id, self._trace_id, span_id
        )
        self.app.call_from_thread(
            self._on_span_annotations_result, result, span_id
        )

    def _on_span_annotations_result(
        self, result: Result[Any], span_id: str
    ) -> None:
        if span_id != self._selected_span_id:
            return
        if not result.ok:
            self._span_annotations = []
            self._refresh_annotations_table()
            err = result.error
            self._lumlflow_app.show_toast(
                f"Annotation load failed: {err.message if err else 'error'}",
                severity="error",
            )
            return
        self._span_annotations = list(result.unwrap())
        self._refresh_annotations_table()

    def _refresh_annotations_table(self) -> None:
        try:
            table = self.query_one("#span-annotations-table", DataTable)
        except Exception:
            return
        table.clear()
        if not self._span_annotations:
            # Drop the row cursor so the placeholder isn't rendered as a
            # full-width highlighted (selected-looking) bar.
            table.cursor_type = "none"
            table.add_row(
                Text("No annotations", style="dim"),
                Text(""),
                Text(""),
                Text(""),
                Text(""),
                key="__no_annotations__",
            )
            return
        table.cursor_type = "row"
        for ann in self._span_annotations:
            kind_style = (
                "bold magenta"
                if ann.annotation_kind == AnnotationKind.EXPECTATION
                else "bold cyan"
            )
            table.add_row(
                Text(ann.name, style="bold"),
                Text(ann.annotation_kind.value, style=kind_style),
                Text(ann.value_type.value, style="dim"),
                Text(_format_value(ann.value)),
                Text(ann.rationale or "", overflow="ellipsis"),
                key=ann.id,
            )

    # ----- tree event handlers -----

    def on_tree_node_highlighted(
        self, event: Tree.NodeHighlighted[str]
    ) -> None:
        if event.node is None:
            return
        data = event.node.data
        if not isinstance(data, str):
            return
        if data == self._selected_span_id:
            return
        self._set_selected_span(data)

    def on_tree_node_selected(
        self, event: Tree.NodeSelected[str]
    ) -> None:
        # Pressing Enter on a node also targets the same span.
        if event.node is None:
            return
        data = event.node.data
        if not isinstance(data, str):
            return
        self._set_selected_span(data)

    # ----- yank span id -----

    def action_yank(self) -> None:
        if self._selected_span_id is None:
            return
        self._lumlflow_app.show_toast(
            f"span id: {self._selected_span_id}",
            severity="info",
            duration=2.5,
        )

    # ----- annotation create -----

    def action_annotate(self) -> None:
        if self._selected_span_id is None:
            self._lumlflow_app.show_toast(
                "Select a span first.", severity="warning", duration=1.5
            )
            return
        dialog = AnnotationDialog(title="New span annotation")
        self._editing_annotation_id = None
        self.app.push_screen(dialog, callback=self._on_annotation_dialog_result)

    # ----- annotation edit (works on the focused annotation row) -----

    def action_edit_annotation(self) -> None:
        ann = self._focused_annotation()
        if ann is None:
            return
        dialog = AnnotationDialog(
            title=f"Edit annotation · {ann.name}",
            existing=ann,
        )
        self._editing_annotation_id = ann.id
        self.app.push_screen(dialog, callback=self._on_annotation_dialog_result)

    def action_delete_annotation(self) -> None:
        ann = self._focused_annotation()
        if ann is None:
            return
        dialog = ConfirmDialog(
            title="Delete annotation",
            message=(
                f"Delete annotation {ann.name!r}? This cannot be undone."
            ),
            confirm_label="Delete",
            destructive=True,
        )
        ann_id = ann.id
        self.app.push_screen(
            dialog,
            callback=lambda confirmed: self._on_annotation_delete_confirmed(
                ann_id, confirmed
            ),
        )

    def _focused_annotation(self) -> Annotation | None:
        if not self._span_annotations:
            return None
        try:
            table = self.query_one("#span-annotations-table", DataTable)
        except Exception:
            return None
        if table.row_count == 0:
            return None
        try:
            row_index = table.cursor_row
            if not (0 <= row_index < len(self._span_annotations)):
                return None
            return self._span_annotations[row_index]
        except Exception:
            return None

    def _on_annotation_dialog_result(
        self, result: AnnotationDialogResult | None
    ) -> None:
        if result is None:
            self._editing_annotation_id = None
            return
        if self._selected_span_id is None:
            self._editing_annotation_id = None
            return
        if result.mode == "create":
            body = CreateAnnotation(
                name=result.name,
                annotation_kind=result.kind,
                value_type=result.value_type,
                value=result.value,
                rationale=result.rationale,
            )
            self._run_create_annotation(self._selected_span_id, body)
        else:
            ann_id = self._editing_annotation_id
            if ann_id is None:
                return
            update_body = UpdateAnnotation(
                value=result.value,
                rationale=result.rationale,
            )
            self._run_update_annotation(ann_id, update_body)
        self._editing_annotation_id = None

    @work(thread=True, group="span-annotation-create")
    def _run_create_annotation(
        self, span_id: str, body: CreateAnnotation
    ) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.create_span_annotation(
            self._experiment_id, self._trace_id, span_id, body
        )
        self.app.call_from_thread(
            self._on_annotation_mutation_result, result, span_id, "created"
        )

    @work(thread=True, group="span-annotation-update")
    def _run_update_annotation(
        self, annotation_id: str, body: UpdateAnnotation
    ) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.update_span_annotation(
            self._experiment_id, annotation_id, body
        )
        span_id = self._selected_span_id or ""
        self.app.call_from_thread(
            self._on_annotation_mutation_result, result, span_id, "updated"
        )

    def _on_annotation_mutation_result(
        self, result: Result[Any], span_id: str, verb: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "annotation save failed"
            self._lumlflow_app.show_toast(
                f"Annotation {verb}: {msg}", severity="error"
            )
            return
        self._lumlflow_app.show_toast(
            f"Annotation {verb}.", severity="success", duration=2.0
        )
        # Reload the annotations for the current span and update the
        # tree label so the ✎N indicator stays in sync.
        if span_id == self._selected_span_id:
            self._fetch_span_annotations(span_id)
        self._bump_annotation_count(span_id, delta=1 if verb == "created" else 0)

    def _on_annotation_delete_confirmed(
        self, annotation_id: str, confirmed: bool | None
    ) -> None:
        if not confirmed:
            return
        self._run_delete_annotation(annotation_id)

    @work(thread=True, group="span-annotation-delete")
    def _run_delete_annotation(self, annotation_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.delete_span_annotation(
            self._experiment_id, annotation_id
        )
        span_id = self._selected_span_id or ""
        self.app.call_from_thread(
            self._on_annotation_delete_result, result, annotation_id, span_id
        )

    def _on_annotation_delete_result(
        self, result: Result[Any], annotation_id: str, span_id: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "delete failed"
            self._lumlflow_app.show_toast(
                f"Delete failed: {msg}", severity="error"
            )
            return
        # Remove the row locally so the UI updates without a round-trip,
        # and decrement the tree label's annotation count.
        self._span_annotations = [
            a for a in self._span_annotations if a.id != annotation_id
        ]
        self._refresh_annotations_table()
        self._bump_annotation_count(span_id, delta=-1)
        self._lumlflow_app.show_toast(
            "Annotation deleted.", severity="success", duration=2.0
        )

    def _bump_annotation_count(self, span_id: str, *, delta: int) -> None:
        """Increment / decrement the annotation_count badge on a span node."""

        span = self._spans_by_id.get(span_id)
        if span is None:
            return
        new_count = max(0, span.annotation_count + delta)
        if new_count == span.annotation_count:
            return
        span.annotation_count = new_count
        node = self._tree_nodes.get(span_id)
        if node is None:
            return
        node.set_label(self._render_span_label(span))


__all__ = (
    "AUTO_COLLAPSE_THRESHOLD",
    "TraceDetailScreen",
    "_build_span_tree",
    "_format_duration_ns",
    "_format_event_offset_ns",
    "_span_type_glyph",
    "_trace_window",
    "waterfall_geometry",
)
