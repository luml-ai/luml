"""Eval detail screen — inputs / outputs / refs / scores / metadata + annotations.

The screen renders a single eval sample's full payload alongside its
annotations, with create / edit / delete via the shared
`AnnotationDialog` and the facade's `create_eval_annotation` /
`update_eval_annotation` / `delete_eval_annotation` methods.

Layout mirrors the trace detail screen: a left pane with the eval
fields grouped by category and a right pane with the annotations
table. The annotations pane is keyboard-actionable with `a`/`e`/`d`
matching the SPEC's row verbs.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import DataTable, Static

from lumlflow.schemas.annotations import (
    Annotation,
    AnnotationKind,
    CreateAnnotation,
    UpdateAnnotation,
)
from lumlflow.schemas.experiments import Eval
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment
from lumlflow.tui.widgets.annotation_dialog import (
    AnnotationDialog,
    AnnotationDialogResult,
)
from lumlflow.tui.widgets.dialogs import ConfirmDialog

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp


def _format_value(value: int | bool | str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_dict(value: dict[str, Any] | None) -> Text:
    """Render an eval payload dict as `key = value` lines.

    Returns `(none)` (dim) for an empty/missing dict so the user can
    still tell the section is intentional but unused. Values that are
    themselves containers are rendered with `repr` so the structure is
    visible without taking over the screen.
    """

    if not value:
        return Text("(none)", style="dim")
    text = Text()
    for i, (k, v) in enumerate(value.items()):
        if i > 0:
            text.append("\n")
        text.append(f"{k}", style="bold")
        text.append(" = ")
        if isinstance(v, str):
            text.append(v)
        elif isinstance(v, bool):
            text.append("true" if v else "false")
        elif isinstance(v, int | float):
            text.append(str(v))
        elif isinstance(v, list | dict):
            text.append(repr(v))
        elif v is None:
            text.append("null", style="dim")
        else:
            text.append(str(v))
    return text


class EvalDetailScreen(BaseScreen):
    """Eval fields + annotations CRUD for one eval sample."""

    DEFAULT_CSS = """
    EvalDetailScreen {
        layout: vertical;
    }
    EvalDetailScreen #eval-detail-body {
        height: 1fr;
        layout: horizontal;
    }
    EvalDetailScreen #eval-fields-pane {
        width: 60%;
        border-right: solid $panel;
        padding: 0 1;
    }
    EvalDetailScreen #eval-fields-scroll {
        height: 1fr;
    }
    EvalDetailScreen #eval-annotations-pane {
        width: 1fr;
        padding: 0 1;
        layout: vertical;
    }
    EvalDetailScreen #eval-detail-header {
        height: auto;
        padding-bottom: 1;
    }
    EvalDetailScreen .section-title {
        text-style: bold;
        padding-top: 1;
    }
    EvalDetailScreen .field-content {
        height: auto;
    }
    EvalDetailScreen #eval-annotations-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("a", "annotate", "Annotate", show=False),
        Binding("e", "edit_annotation", "Edit annotation", show=False),
        Binding("d", "delete_annotation", "Delete annotation", show=False),
        Binding("y", "yank", "Yank eval id", show=False),
    ]

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        experiment_id: str,
        experiment_name: str | None = None,
        group_name: str | None = None,
        dataset_id: str,
        eval_id: str,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._experiment_id = experiment_id
        self._experiment_name = experiment_name
        self._group_name = group_name
        self._dataset_id = dataset_id
        self._eval_id = eval_id
        self._eval: Eval | None = None
        self._annotations: list[Annotation] = []
        self._editing_annotation_id: str | None = None

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="eval-detail-body"):
            with Vertical(id="eval-fields-pane"):
                yield Static("Loading eval…", id="eval-detail-header")
                with VerticalScroll(id="eval-fields-scroll"):
                    yield Static("Inputs", classes="section-title")
                    yield Static(
                        "(loading)", id="eval-inputs", classes="field-content"
                    )
                    yield Static("Outputs", classes="section-title")
                    yield Static(
                        "(loading)", id="eval-outputs", classes="field-content"
                    )
                    yield Static("References", classes="section-title")
                    yield Static(
                        "(loading)", id="eval-refs", classes="field-content"
                    )
                    yield Static("Scores", classes="section-title")
                    yield Static(
                        "(loading)", id="eval-scores", classes="field-content"
                    )
                    yield Static("Metadata", classes="section-title")
                    yield Static(
                        "(loading)", id="eval-metadata", classes="field-content"
                    )
                    yield Static("Linked traces", classes="section-title")
                    yield Static(
                        "(none)", id="eval-traces", classes="field-content"
                    )
            with Vertical(id="eval-annotations-pane"):
                yield Static("Annotations", classes="section-title")
                yield DataTable(
                    id="eval-annotations-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )

    def on_mount(self) -> None:
        # The DataTable may not yet be present in the widget tree when
        # the screen's `on_mount` fires (Textual mounts children
        # asynchronously). Guard the columns setup so a startup-ordering
        # race doesn't crash the worker callbacks.
        try:
            table = self.query_one("#eval-annotations-table", DataTable)
        except Exception:
            self.call_after_refresh(self._init_annotations_table)
        else:
            table.add_columns("Name", "Kind", "Type", "Value", "Rationale")
        if self.facade is not None:
            self._fetch_eval()
            self._fetch_annotations()

    def _init_annotations_table(self) -> None:
        try:
            table = self.query_one("#eval-annotations-table", DataTable)
        except Exception:
            return
        # Idempotent: only add columns once.
        if not table.columns:
            table.add_columns("Name", "Kind", "Type", "Value", "Rationale")

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        segments = [BreadcrumbSegment("Groups")]
        if self._group_name:
            segments.append(BreadcrumbSegment(self._group_name))
        if self._experiment_name:
            segments.append(BreadcrumbSegment(self._experiment_name))
        segments.append(BreadcrumbSegment(f"Eval {self._eval_id[:8]}"))
        return tuple(segments)

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global", "annotations")

    def focusable_panes(self) -> Iterable:
        try:
            return (
                self.query_one("#eval-fields-scroll", VerticalScroll),
                self.query_one("#eval-annotations-table", DataTable),
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

    # ----- eval fetch + render -----

    @work(thread=True, exclusive=True, group="eval-detail")
    def _fetch_eval(self) -> None:
        facade = self.facade
        if facade is None:
            self.app.call_from_thread(self._on_eval_failure, "facade unavailable")
            return
        result = facade.get_eval(self._experiment_id, self._eval_id)
        self.app.call_from_thread(self._on_eval_result, result)

    def _on_eval_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "unknown error"
            self._on_eval_failure(msg)
            return
        eval_rec: Eval = result.unwrap()
        self._eval = eval_rec
        self._render_eval(eval_rec)

    def _on_eval_failure(self, message: str) -> None:
        self._lumlflow_app.show_toast(
            f"Could not load eval: {message}", severity="error"
        )
        try:
            self.query_one("#eval-detail-header", Static).update(
                f"Could not load eval: {message}"
            )
        except Exception:
            pass

    def _render_eval(self, eval_rec: Eval) -> None:
        try:
            header = self.query_one("#eval-detail-header", Static)
        except Exception:
            return
        head = Text()
        head.append(f"eval {eval_rec.id}", style="bold")
        head.append("\ndataset: ")
        head.append(eval_rec.dataset_id, style="dim")
        head.append("    created: ")
        head.append(eval_rec.created_at.strftime("%Y-%m-%d %H:%M"), style="dim")
        if eval_rec.updated_at and eval_rec.updated_at != eval_rec.created_at:
            head.append("    updated: ")
            head.append(eval_rec.updated_at.strftime("%Y-%m-%d %H:%M"), style="dim")
        header.update(head)
        self.query_one("#eval-inputs", Static).update(_render_dict(eval_rec.inputs))
        self.query_one("#eval-outputs", Static).update(_render_dict(eval_rec.outputs))
        self.query_one("#eval-refs", Static).update(_render_dict(eval_rec.refs))
        self.query_one("#eval-scores", Static).update(_render_dict(eval_rec.scores))
        self.query_one("#eval-metadata", Static).update(_render_dict(eval_rec.metadata))
        if eval_rec.trace_ids:
            traces_text = Text()
            for i, tid in enumerate(eval_rec.trace_ids):
                if i > 0:
                    traces_text.append("\n")
                traces_text.append(tid, style="dim")
            self.query_one("#eval-traces", Static).update(traces_text)
        else:
            self.query_one("#eval-traces", Static).update(
                Text("(none)", style="dim")
            )

    # ----- annotation fetch + render -----

    @work(thread=True, exclusive=True, group="eval-annotations")
    def _fetch_annotations(self) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.list_eval_annotations(
            self._experiment_id, self._dataset_id, self._eval_id
        )
        self.app.call_from_thread(self._on_annotations_result, result)

    def _on_annotations_result(self, result: Result[Any]) -> None:
        if not result.ok:
            self._annotations = []
            self._refresh_annotations_table()
            err = result.error
            self._lumlflow_app.show_toast(
                f"Annotation load failed: {err.message if err else 'error'}",
                severity="error",
            )
            return
        self._annotations = list(result.unwrap())
        self._refresh_annotations_table()

    def _refresh_annotations_table(self) -> None:
        try:
            table = self.query_one("#eval-annotations-table", DataTable)
        except Exception:
            return
        table.clear()
        if not self._annotations:
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
        for ann in self._annotations:
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

    # ----- yank id -----

    def action_yank(self) -> None:
        self._lumlflow_app.show_toast(
            f"eval id: {self._eval_id}", severity="info", duration=2.5
        )

    # ----- annotation create / edit / delete -----

    def action_annotate(self) -> None:
        dialog = AnnotationDialog(title="New eval annotation")
        self._editing_annotation_id = None
        self.app.push_screen(dialog, callback=self._on_annotation_dialog_result)

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
        if not self._annotations:
            return None
        try:
            table = self.query_one("#eval-annotations-table", DataTable)
        except Exception:
            return None
        if table.row_count == 0:
            return None
        try:
            row_index = table.cursor_row
            if not (0 <= row_index < len(self._annotations)):
                return None
            return self._annotations[row_index]
        except Exception:
            return None

    def _on_annotation_dialog_result(
        self, result: AnnotationDialogResult | None
    ) -> None:
        if result is None:
            self._editing_annotation_id = None
            return
        if result.mode == "create":
            create_body = CreateAnnotation(
                name=result.name,
                annotation_kind=result.kind,
                value_type=result.value_type,
                value=result.value,
                rationale=result.rationale,
            )
            self._run_create_annotation(create_body)
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

    @work(thread=True, group="eval-annotation-create")
    def _run_create_annotation(self, body: CreateAnnotation) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.create_eval_annotation(
            self._experiment_id, self._dataset_id, self._eval_id, body
        )
        self.app.call_from_thread(
            self._on_annotation_mutation_result, result, "created"
        )

    @work(thread=True, group="eval-annotation-update")
    def _run_update_annotation(
        self, annotation_id: str, body: UpdateAnnotation
    ) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.update_eval_annotation(
            self._experiment_id, annotation_id, body
        )
        self.app.call_from_thread(
            self._on_annotation_mutation_result, result, "updated"
        )

    def _on_annotation_mutation_result(
        self, result: Result[Any], verb: str
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
        self._fetch_annotations()

    def _on_annotation_delete_confirmed(
        self, annotation_id: str, confirmed: bool | None
    ) -> None:
        if not confirmed:
            return
        self._run_delete_annotation(annotation_id)

    @work(thread=True, group="eval-annotation-delete")
    def _run_delete_annotation(self, annotation_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.delete_eval_annotation(
            self._experiment_id, annotation_id
        )
        self.app.call_from_thread(
            self._on_annotation_delete_result, result, annotation_id
        )

    def _on_annotation_delete_result(
        self, result: Result[Any], annotation_id: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "delete failed"
            self._lumlflow_app.show_toast(
                f"Delete failed: {msg}", severity="error"
            )
            return
        self._annotations = [
            a for a in self._annotations if a.id != annotation_id
        ]
        self._refresh_annotations_table()
        self._lumlflow_app.show_toast(
            "Annotation deleted.", severity="success", duration=2.0
        )


__all__ = (
    "EvalDetailScreen",
    "_render_dict",
)
