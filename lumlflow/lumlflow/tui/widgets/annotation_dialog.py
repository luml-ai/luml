"""Annotation editor dialog for spans and evals.

The dialog enforces the `CreateAnnotation` contract: a name, an
`AnnotationKind` (feedback / expectation), a `AnnotationValueType`
(int / bool / string), and a value parsable as that type. The value
input is validated live so the user sees the exact problem (e.g.
"not a valid integer") before submitting. An optional rationale field
is exposed for richer notes.

Used by the trace detail screen for span annotations (this task) and
will be reused by the evals tab in a follow-up.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from textual.binding import Binding
from textual.widgets import Input, Label, RadioButton, RadioSet, Static

from lumlflow.schemas.annotations import (
    Annotation,
    AnnotationKind,
    AnnotationValueType,
)
from lumlflow.tui.widgets.modal import BaseDialog


@dataclass(frozen=True)
class AnnotationDialogResult:
    """Submitted annotation values.

    `mode` is `"create"` for a new annotation (all fields filled) and
    `"update"` when editing an existing one (only `value` and
    `rationale` are mutable per the handler's `UpdateAnnotation`).
    """

    mode: str
    name: str
    kind: AnnotationKind
    value_type: AnnotationValueType
    value: int | bool | str
    rationale: str | None = None


def _coerce_value(
    value_type: AnnotationValueType, raw: str
) -> tuple[int | bool | str | None, str | None]:
    """Coerce the raw input string to the chosen value type.

    Returns `(coerced_value, error_message)`. On success `error_message`
    is `None`. On failure `coerced_value` is `None` and `error_message`
    spells out exactly why the value failed (e.g. "not a valid
    integer"), so the dialog can surface it inline.
    """

    text = raw.strip()
    if value_type == AnnotationValueType.STRING:
        return text, None
    if value_type == AnnotationValueType.INT:
        if not text:
            return None, "Integer value is required."
        try:
            return int(text), None
        except ValueError:
            return None, f"{text!r} is not a valid integer."
    if value_type == AnnotationValueType.BOOL:
        lowered = text.lower()
        if lowered in ("true", "t", "yes", "y", "1"):
            return True, None
        if lowered in ("false", "f", "no", "n", "0"):
            return False, None
        return None, "Boolean value must be true/false (or yes/no, 1/0)."
    return None, f"Unknown value type: {value_type}"


class AnnotationDialog(BaseDialog["AnnotationDialogResult | None"]):
    """Create or edit a single annotation.

    In **create** mode the user picks the name, kind, value-type and
    value. In **edit** mode (passed `existing=...`) the name / kind /
    value-type are read-only (the handler's `UpdateAnnotation` only
    accepts `value` and `rationale`).
    """

    DEFAULT_CSS = """
    AnnotationDialog .field-label {
        padding-top: 1;
        text-style: bold;
    }
    AnnotationDialog #annotation-kind, AnnotationDialog #annotation-vtype {
        height: 3;
    }
    AnnotationDialog #annotation-value-hint {
        color: $text-muted;
        padding-top: 0;
    }
    AnnotationDialog #annotation-validation {
        color: $error;
        padding-top: 1;
    }
    AnnotationDialog #annotation-validation.-ok {
        color: $success;
    }
    AnnotationDialog .readonly-field {
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "confirm", "Save", show=False),
    ]

    confirm_label = "Save"
    cancel_label = "Cancel"

    def __init__(
        self,
        *,
        title: str = "Annotation",
        existing: Annotation | None = None,
        default_kind: AnnotationKind = AnnotationKind.FEEDBACK,
        default_value_type: AnnotationValueType = AnnotationValueType.STRING,
    ) -> None:
        super().__init__(title=title)
        self._existing = existing
        if existing is not None:
            self._mode = "update"
            self._annotation_name = existing.name or ""
            self._kind = existing.annotation_kind
            self._value_type = existing.value_type
            self._initial_value = str(existing.value)
            self._initial_rationale = existing.rationale or ""
        else:
            self._mode = "create"
            self._annotation_name = ""
            self._kind = default_kind
            self._value_type = default_value_type
            self._initial_value = ""
            self._initial_rationale = ""

    def compose_body(self) -> Iterable:
        yield Label("Name", classes="field-label")
        if self._mode == "create":
            yield Input(
                value=self._annotation_name,
                placeholder="e.g. quality, latency_p95",
                id="annotation-name",
            )
        else:
            yield Static(self._annotation_name, classes="readonly-field")

        yield Label("Kind", classes="field-label")
        if self._mode == "create":
            with RadioSet(id="annotation-kind"):
                yield RadioButton(
                    "feedback",
                    value=self._kind == AnnotationKind.FEEDBACK,
                    id="kind-feedback",
                )
                yield RadioButton(
                    "expectation",
                    value=self._kind == AnnotationKind.EXPECTATION,
                    id="kind-expectation",
                )
        else:
            yield Static(self._kind.value, classes="readonly-field")

        yield Label("Value type", classes="field-label")
        if self._mode == "create":
            with RadioSet(id="annotation-vtype"):
                yield RadioButton(
                    "string",
                    value=self._value_type == AnnotationValueType.STRING,
                    id="vtype-string",
                )
                yield RadioButton(
                    "int",
                    value=self._value_type == AnnotationValueType.INT,
                    id="vtype-int",
                )
                yield RadioButton(
                    "bool",
                    value=self._value_type == AnnotationValueType.BOOL,
                    id="vtype-bool",
                )
        else:
            yield Static(self._value_type.value, classes="readonly-field")

        yield Label("Value", classes="field-label")
        yield Input(
            value=self._initial_value,
            placeholder=self._value_hint(),
            id="annotation-value",
        )
        yield Static(self._value_hint(), id="annotation-value-hint")

        yield Label("Rationale (optional)", classes="field-label")
        yield Input(
            value=self._initial_rationale,
            placeholder="Short explanation (optional)",
            id="annotation-rationale",
        )

        yield Static("", id="annotation-validation")

    def _value_hint(self) -> str:
        if self._value_type == AnnotationValueType.INT:
            return "Integer (e.g. 1, 42, -3)"
        if self._value_type == AnnotationValueType.BOOL:
            return "Boolean (true/false, yes/no, 1/0)"
        return "Free-text string"

    def on_mount(self) -> None:
        super().on_mount()
        try:
            if self._mode == "create":
                self.query_one("#annotation-name", Input).focus()
            else:
                self.query_one("#annotation-value", Input).focus()
        except Exception:
            pass
        self._run_validation()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        pressed = event.pressed
        label = pressed.label.plain if pressed is not None else ""
        if event.radio_set.id == "annotation-kind":
            if label == "feedback":
                self._kind = AnnotationKind.FEEDBACK
            elif label == "expectation":
                self._kind = AnnotationKind.EXPECTATION
        elif event.radio_set.id == "annotation-vtype":
            if label == "string":
                self._value_type = AnnotationValueType.STRING
            elif label == "int":
                self._value_type = AnnotationValueType.INT
            elif label == "bool":
                self._value_type = AnnotationValueType.BOOL
            try:
                hint = self.query_one("#annotation-value-hint", Static)
                hint.update(self._value_hint())
                self.query_one("#annotation-value", Input).placeholder = (
                    self._value_hint()
                )
            except Exception:
                pass
            self._run_validation()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "annotation-value":
            self._run_validation()

    def _run_validation(self) -> None:
        try:
            raw = self.query_one("#annotation-value", Input).value
            note = self.query_one("#annotation-validation", Static)
        except Exception:
            return
        _value, err = _coerce_value(self._value_type, raw)
        if err is None:
            note.update("✓ value parses")
            note.add_class("-ok")
        else:
            note.update(f"✗ {err}")
            note.remove_class("-ok")

    def action_confirm(self) -> None:
        try:
            value_input = self.query_one("#annotation-value", Input)
            rationale_input = self.query_one("#annotation-rationale", Input)
        except Exception:
            return

        if self._mode == "create":
            try:
                name = self.query_one("#annotation-name", Input).value.strip()
            except Exception:
                name = self._annotation_name
            if not name:
                self.set_error("Name is required.")
                return
            self._annotation_name = name

        value, err = _coerce_value(self._value_type, value_input.value)
        if err is not None:
            self.set_error(err)
            value_input.focus()
            return
        # `value` is non-None when err is None for INT/BOOL; for STRING an
        # empty input is allowed and value is the empty string.
        assert value is not None or self._value_type == AnnotationValueType.STRING

        rationale = rationale_input.value.strip() or None
        self.dismiss(
            AnnotationDialogResult(
                mode=self._mode,
                name=self._annotation_name,
                kind=self._kind,
                value_type=self._value_type,
                value=value if value is not None else "",
                rationale=rationale,
            )
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


__all__ = (
    "AnnotationDialog",
    "AnnotationDialogResult",
)
