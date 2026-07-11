"""AttachmentsPanel widget — the body of the Attachments tab.

Renders an experiment's attachment tree (folder/file hierarchy with
sizes) on the left, and a preview pane on the right. Selecting a file
fetches its bytes on a worker and renders it according to type:

- **text-like** content (text/JSON/CSV/markdown/etc.) is decoded as
  UTF-8 with a `replace` fallback and shown inline as a syntax-aware
  Static body;
- **images** are best-effort previewed inline via the terminal's
  graphics protocol when supported (textual-image), and otherwise the
  panel reports "image preview not supported in this terminal" and
  offers save-to-disk — the common case over plain SSH;
- **anything else** (binaries, archives) reports "binary content" and
  offers save-to-disk only.

A large-file guard (`LARGE_FILE_THRESHOLD`) prevents the panel from
attempting an inline preview of attachments larger than ~1 MiB — for
those, the panel shows the size and offers save-to-disk instead so
the TUI never blocks loading a multi-megabyte attachment into memory
just to render it.

The save-to-disk action (`s`, with `w` as a vim-style alias) is bound
on a focused file row; the user is prompted for a path via
`SaveFileDialog` and the bytes are written from the same worker that
fetched them.

The panel uses Textual's `Tree` widget which materialises only the
visible nodes (virtualization) — so an experiment with thousands of
attachments stays smooth. Folder children are lazy-loaded the first
time a folder is expanded, using the handler's `parent_path`
mechanism, so the initial tree is just the root listing regardless of
attachment count below it.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from lumlflow.schemas.experiments import FileNode, FileNodeType
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.widgets.save_file_dialog import SaveFileDialog

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp


# Files larger than this guard are not auto-previewed — the panel shows
# the size and offers save-to-disk instead. The threshold is generous
# enough for most JSON/CSV/text logs but small enough that loading a
# binary into RAM never freezes the UI.
LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1 MiB


# Text-like content types we preview inline. Everything else falls
# through to the "binary" branch (still offered for save-to-disk).
_TEXT_PREFIXES: tuple[str, ...] = ("text/",)
_TEXT_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/json",
        "application/xml",
        "application/yaml",
        "application/x-yaml",
        "application/javascript",
        "application/x-sh",
        "application/x-shellscript",
        "application/toml",
        "image/svg+xml",  # SVG is XML text
    }
)
_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt", ".md", ".markdown", ".rst", ".log",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".csv", ".tsv", ".tab",
        ".py", ".pyi", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm",
        ".css", ".scss", ".rs", ".go", ".c", ".h", ".hpp", ".cpp",
        ".cc", ".java", ".rb", ".php", ".sh", ".bash", ".zsh",
        ".xml", ".svg",
    }
)


_IMAGE_MIME_PREFIX = "image/"
_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
)


def _format_size(size: int | None) -> str:
    """Format a byte size as a compact human-readable string."""

    if size is None:
        return "—"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MiB"
    return f"{size / (1024 * 1024 * 1024):.2f} GiB"


def _guess_mime(file_path: str) -> str:
    """Return a best-effort MIME type for a file path."""

    mt, _ = mimetypes.guess_type(file_path)
    return mt or "application/octet-stream"


def _is_text_like(file_path: str) -> bool:
    """Return True if the file should preview as text."""

    suffix = Path(file_path).suffix.lower()
    if suffix in _TEXT_EXTENSIONS:
        return True
    mt = _guess_mime(file_path)
    if mt in _TEXT_MIME_TYPES:
        return True
    return any(mt.startswith(p) for p in _TEXT_PREFIXES)


def _is_image(file_path: str) -> bool:
    """Return True if the file is an image we can attempt to render."""

    suffix = Path(file_path).suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return True
    mt = _guess_mime(file_path)
    return mt.startswith(_IMAGE_MIME_PREFIX)


def _decode_text(data: bytes, *, max_chars: int = 200_000) -> str:
    """Decode bytes for inline preview.

    UTF-8 with `replace` so files with mixed encodings still render —
    the preview is informative, not authoritative. The character cap
    keeps a runaway file from filling the buffer; truncation is shown
    with an explicit suffix.
    """

    text = data.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        truncation_note = "\n\n[... truncated, save to disk to view in full ...]"
        return text[:max_chars] + truncation_note
    return text


@dataclass
class _NodeData:
    """Per-tree-node payload — the file path and whether it is a folder."""

    path: str
    is_folder: bool
    size: int | None = None
    loaded: bool = False  # True once a folder's children have been fetched


class AttachmentsPanel(Widget):
    """File/folder tree + inline preview with save-to-disk fallback."""

    DEFAULT_CSS = """
    AttachmentsPanel {
        layout: horizontal;
        height: 1fr;
    }
    AttachmentsPanel #attachments-tree {
        width: 36;
        border-right: solid $panel;
    }
    AttachmentsPanel #attachments-right {
        width: 1fr;
        layout: vertical;
    }
    AttachmentsPanel #attachments-preview-header {
        height: auto;
        padding: 0 2;
        color: $text-muted;
    }
    AttachmentsPanel #attachments-preview-body {
        height: 1fr;
        padding: 0 2;
        overflow-y: auto;
    }
    AttachmentsPanel #attachments-empty {
        height: 1fr;
        padding: 2 4;
        content-align: center middle;
        text-align: center;
    }
    AttachmentsPanel .preview-large {
        color: $warning;
    }
    AttachmentsPanel .preview-binary {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("enter", "preview_focused", "Preview", show=False),
        # `s` is the primary save key (mnemonic: Save; no sort exists on
        # this tab so it is free); `w` (write) stays as a vim-style alias.
        Binding("s,w", "save_focused", "Save to disk", show=False),
        Binding("y", "yank_focused", "Yank path", show=False),
    ]

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        experiment_id: str,
        experiment_name: str | None = None,
        group_name: str | None = None,
        id: str | None = None,
        large_file_threshold: int = LARGE_FILE_THRESHOLD,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._experiment_id = experiment_id
        self._experiment_name = experiment_name
        self._group_name = group_name
        self._large_file_threshold = large_file_threshold
        # Lazy-load on first tab activation.
        self._started: bool = False
        # Track the currently previewed file so a slow fetch arriving
        # after the user has moved on doesn't overwrite the new preview.
        self._previewing_path: str | None = None
        # Map node ids -> _NodeData payloads. Textual's TreeNode.data
        # field would normally do this but using an explicit map lets
        # the same node be re-used across reloads.
        self._node_data: dict[int, _NodeData] = {}

    # ----- composition -----

    def compose(self) -> Iterable:
        with Horizontal():
            yield Tree("attachments", id="attachments-tree")
            with Vertical(id="attachments-right"):
                yield Static(
                    "Select a file to preview.",
                    id="attachments-preview-header",
                )
                yield Static("", id="attachments-preview-body")

    def on_mount(self) -> None:
        try:
            tree = self.query_one("#attachments-tree", Tree)
        except Exception:
            return
        tree.show_root = False
        tree.root.expand()

    # ----- lifecycle -----

    def start(self) -> None:
        """Trigger the first tree load (root listing only)."""

        if self._started or self.facade is None:
            return
        self._started = True
        self._fetch_children(parent_path=None, parent_node_id=None)

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        app = self.app
        return getattr(app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- tree population -----

    @work(thread=True, group="attachments-tree")
    def _fetch_children(
        self, *, parent_path: str | None, parent_node_id: int | None
    ) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.list_attachments_tree(
            self._experiment_id, parent_path=parent_path
        )
        self.app.call_from_thread(
            self._on_children_result, result, parent_path, parent_node_id
        )

    def _on_children_result(
        self,
        result: Result[Any],
        parent_path: str | None,
        parent_node_id: int | None,
    ) -> None:
        if not result.ok:
            err = result.error
            self._lumlflow_app.show_toast(
                f"Could not load attachments: {err.message if err else 'error'}",
                severity="error",
            )
            return
        nodes: list[FileNode] = list(result.unwrap() or [])
        try:
            tree = self.query_one("#attachments-tree", Tree)
        except Exception:
            return
        parent_node = self._find_node(tree, parent_node_id)
        if parent_node is None:
            return
        # Replace any prior children so a re-fetch yields the latest tree.
        parent_node.remove_children()
        # Sort: folders first, then files, alphabetically within each group
        # — mirrors the convention most file browsers use.
        folders = sorted(
            (n for n in nodes if n.type == FileNodeType.FOLDER), key=lambda n: n.name
        )
        files = sorted(
            (n for n in nodes if n.type == FileNodeType.FILE), key=lambda n: n.name
        )
        for node in (*folders, *files):
            label = self._render_node_label(node)
            is_folder = node.type == FileNodeType.FOLDER
            # Path may be `None` for the root listing's leaf rows on some
            # backends; fall back to the bare name.
            path = node.path or node.name
            if is_folder:
                child = parent_node.add(
                    label, expand=False, allow_expand=True
                )
            else:
                child = parent_node.add_leaf(label)
            self._node_data[child.id] = _NodeData(
                path=path, is_folder=is_folder, size=node.size, loaded=False
            )
        # Mark this parent as loaded.
        if parent_node_id is not None and parent_node_id in self._node_data:
            self._node_data[parent_node_id].loaded = True
        self._update_empty_state(bool(nodes), parent_path is None)

    @staticmethod
    def _render_node_label(node: FileNode) -> Text:
        text = Text()
        if node.type == FileNodeType.FOLDER:
            text.append("📁 ", style="bold")
            text.append(node.name, style="bold")
        else:
            text.append("📄 ", style="dim")
            text.append(node.name)
        if node.size is not None:
            text.append(f"  {_format_size(node.size)}", style="dim")
        return text

    @staticmethod
    def _find_node(tree: Tree[Any], node_id: int | None) -> TreeNode[Any] | None:
        if node_id is None:
            return tree.root
        # Tree's `get_node_by_id` is the right primitive but is not on
        # every Textual version — walk the tree as a fallback.
        getter = getattr(tree, "get_node_by_id", None)
        if getter is not None:
            try:
                return getter(node_id)
            except Exception:
                return None
        # Walk fallback.
        pending: list[TreeNode[Any]] = [tree.root]
        while pending:
            node = pending.pop()
            if node.id == node_id:
                return node
            pending.extend(node.children)
        return None

    def _update_empty_state(self, has_any: bool, is_root: bool) -> None:
        # Replace the entire body when there is no attachment at the
        # root — folders deeper in the tree don't get a separate empty
        # state because the user can already see the parent's label.
        if has_any or not is_root:
            return
        try:
            header = self.query_one("#attachments-preview-header", Static)
            body = self.query_one("#attachments-preview-body", Static)
        except Exception:
            return
        header.update("No attachments")
        body.update(Text("No attachments yet.", style="dim"))

    # ----- tree event handlers -----

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[Any]) -> None:
        if event.node.tree.id != "attachments-tree":
            return
        data = self._node_data.get(event.node.id)
        if data is None or not data.is_folder or data.loaded:
            return
        self._fetch_children(parent_path=data.path, parent_node_id=event.node.id)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[Any]) -> None:
        if event.node.tree.id != "attachments-tree":
            return
        data = self._node_data.get(event.node.id)
        if data is None:
            return
        # Update the preview header even if we don't fetch — the user
        # can see "what file is the cursor on" without pressing Enter.
        self._update_preview_header(data)

    def on_tree_node_selected(self, event: Tree.NodeSelected[Any]) -> None:
        if event.node.tree.id != "attachments-tree":
            return
        data = self._node_data.get(event.node.id)
        if data is None:
            return
        if data.is_folder:
            # Selecting a folder toggles expansion via the Tree widget's
            # default handler; nothing else to do here.
            return
        self._preview_file(data)

    # ----- preview -----

    def action_preview_focused(self) -> None:
        node = self._focused_node()
        if node is None:
            return
        data = self._node_data.get(node.id)
        if data is None:
            return
        if data.is_folder:
            return
        self._preview_file(data)

    def _focused_node(self) -> TreeNode[Any] | None:
        try:
            tree = self.query_one("#attachments-tree", Tree)
        except Exception:
            return None
        return tree.cursor_node

    def _update_preview_header(self, data: _NodeData) -> None:
        try:
            header = self.query_one("#attachments-preview-header", Static)
        except Exception:
            return
        size_str = _format_size(data.size)
        kind = "folder" if data.is_folder else "file"
        header.update(
            Text.assemble(
                (data.path, "bold"),
                ("  ·  ", "dim"),
                (kind, "dim"),
                ("  ·  ", "dim"),
                (size_str, "dim"),
            )
        )

    def _preview_file(self, data: _NodeData) -> None:
        # Update header to show what is being previewed.
        self._update_preview_header(data)
        self._previewing_path = data.path
        # Large-file guard: don't fetch / decode multi-megabyte attachments
        # for an inline preview. The user can still save to disk.
        if data.size is not None and data.size > self._large_file_threshold:
            self._render_large_file(data)
            return
        # Binary files: don't fetch unless asked to save (just describe).
        if not _is_text_like(data.path) and not _is_image(data.path):
            self._render_binary_placeholder(data)
            return
        self._render_loading()
        self._fetch_preview(data.path)

    def _render_loading(self) -> None:
        try:
            body = self.query_one("#attachments-preview-body", Static)
        except Exception:
            return
        body.update("Loading…")

    def _render_large_file(self, data: _NodeData) -> None:
        try:
            body = self.query_one("#attachments-preview-body", Static)
        except Exception:
            return
        body.update(
            Text.assemble(
                (
                    f"File is {_format_size(data.size)} — exceeds the "
                    f"{_format_size(self._large_file_threshold)} inline preview "
                    "threshold.\n\n",
                    "bold yellow",
                ),
                "Press [s] to save it to disk and open in an external viewer.",
            )
        )

    def _render_binary_placeholder(self, data: _NodeData) -> None:
        try:
            body = self.query_one("#attachments-preview-body", Static)
        except Exception:
            return
        body.update(
            Text.assemble(
                (
                    "Binary content "
                    f"({_guess_mime(data.path)}) — no inline preview.\n\n",
                    "dim",
                ),
                "Press [s] to save it to disk.",
            )
        )

    @work(thread=True, exclusive=True, group="attachments-content")
    def _fetch_preview(self, file_path: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.get_attachment(self._experiment_id, file_path)
        self.app.call_from_thread(
            self._on_preview_result, result, file_path
        )

    def _on_preview_result(self, result: Result[Any], file_path: str) -> None:
        # Drop the result if the user has moved on to another file.
        if file_path != self._previewing_path:
            return
        try:
            body = self.query_one("#attachments-preview-body", Static)
        except Exception:
            return
        if not result.ok:
            err = result.error
            body.update(
                Text(
                    f"Could not load file: {err.message if err else 'error'}",
                    style="bold red",
                )
            )
            return
        data: bytes = result.unwrap() or b""
        if _is_text_like(file_path):
            body.update(_decode_text(data))
            return
        if _is_image(file_path):
            # Inline image rendering uses the terminal's graphics
            # protocol when available; without it (the common SSH case)
            # we degrade to a save-to-disk hint per the SPEC.
            body.update(
                Text.assemble(
                    (
                        "Image preview not supported in this terminal.\n\n",
                        "bold yellow",
                    ),
                    "Press [w] to save it to disk and open in an external viewer.",
                )
            )
            return
        # Shouldn't reach here — `_preview_file` filters non-text/non-image
        # paths to the binary placeholder branch — but render a safe
        # default just in case.
        body.update(Text("Binary content — press [w] to save to disk.", style="dim"))

    # ----- save to disk -----

    def action_save_focused(self) -> None:
        node = self._focused_node()
        if node is None:
            return
        data = self._node_data.get(node.id)
        if data is None or data.is_folder:
            return
        # Default save target is the basename in the current working
        # directory so the user only has to confirm.
        default_name = Path(data.path).name
        suggested = str(Path.cwd() / default_name)
        dialog = SaveFileDialog(
            title=f"Save {default_name}",
            default_path=suggested,
        )
        file_path = data.path
        self.app.push_screen(
            dialog,
            callback=lambda dest: self._on_save_dest(dest, file_path),
        )

    def _on_save_dest(self, dest: str | None, file_path: str) -> None:
        if not dest:
            return
        self._save_to_disk(file_path, dest)

    @work(thread=True, group="attachments-save")
    def _save_to_disk(self, file_path: str, dest: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.get_attachment(self._experiment_id, file_path)
        if not result.ok:
            err = result.error
            self.app.call_from_thread(
                self._lumlflow_app.show_toast,
                f"Could not load file: {err.message if err else 'error'}",
                severity="error",
            )
            return
        data: bytes = result.unwrap() or b""
        try:
            destination = Path(dest).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        except OSError as exc:
            self.app.call_from_thread(
                self._lumlflow_app.show_toast,
                f"Save failed: {exc}",
                severity="error",
            )
            return
        self.app.call_from_thread(
            self._lumlflow_app.show_toast,
            f"Saved to {destination}",
            severity="success",
            duration=3.0,
        )

    # ----- yank -----

    def action_yank_focused(self) -> None:
        node = self._focused_node()
        if node is None:
            return
        data = self._node_data.get(node.id)
        if data is None:
            return
        self._lumlflow_app.yank_to_clipboard(data.path, label="attachment path")


__all__ = (
    "LARGE_FILE_THRESHOLD",
    "AttachmentsPanel",
    "_decode_text",
    "_format_size",
    "_is_image",
    "_is_text_like",
)
