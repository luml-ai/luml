"""Pilot tests for the shared edit / confirm / sort dialogs.

These dialogs back the Groups, Experiments and Models edit/delete
flows (and the sort chooser used by every list screen), so they have
to render and submit consistently regardless of which screen pushes
them. Tests drive the dialog in isolation via `App.push_screen` so
they are decoupled from any list screen.
"""

from __future__ import annotations

import pytest
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
    SortChooserDialog,
    SortChooserResult,
)
from textual.app import App, ComposeResult
from textual.widgets import Input, Static


class _Harness(App[None]):
    """Minimal app harness that lets a test push any modal and read its result."""

    def compose(self) -> ComposeResult:
        yield Static("harness", id="root")

    def push(self, screen, callback=None):
        self.push_screen(screen, callback=callback)


@pytest.mark.parametrize("destructive", [False, True])
async def test_confirm_dialog_enter_returns_true(destructive: bool) -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {}
        app.push(
            ConfirmDialog(
                title="Delete?",
                message="Are you sure?",
                destructive=destructive,
            ),
            callback=lambda v: result.update(v=v),
        )
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()
        assert result.get("v") is True


async def test_confirm_dialog_escape_returns_false() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {}
        app.push(
            ConfirmDialog(title="Delete?", message="Sure?"),
            callback=lambda v: result.update(v=v),
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert result.get("v") is False


async def test_destructive_confirm_shows_cancel_first_in_layout() -> None:
    """Destructive dialogs should render Cancel before Confirm so the eye
    lands on the safe option."""

    app = _Harness()
    async with app.run_test() as pilot:
        app.push(
            ConfirmDialog(
                title="Delete?",
                message="permanent",
                destructive=True,
            )
        )
        await pilot.pause()
        # Confirm key text mentions [Esc] Cancel earlier than [Enter] Delete.
        # We use the children of the button container.
        from textual.containers import Horizontal

        buttons = app.screen.query_one("#dialog-buttons", Horizontal)
        labels = [str(child.render()) for child in buttons.children]
        assert labels[0].startswith("[Esc]") or "Cancel" in labels[0]


async def test_confirm_inline_error_renders() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        dialog = ConfirmDialog(title="t", message="m")
        app.push(dialog)
        await pilot.pause()
        dialog.set_error("cannot delete: linked experiments")
        await pilot.pause()
        err = app.screen.query_one("#dialog-error", Static)
        assert "linked experiments" in str(err.render())


async def test_edit_dialog_submits_changes() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {}
        dialog = EditEntityDialog(
            title="Edit",
            name="orig",
            description="d",
            tags=["x"],
        )
        app.push(dialog, callback=lambda v: result.update(v=v))
        await pilot.pause()
        name = app.screen.query_one("#edit-name", Input)
        name.value = "new"
        # Save via the explicit shortcut.
        await pilot.press("ctrl+s")
        await pilot.pause()
        v: EntityEditResult | None = result.get("v")
        assert isinstance(v, EntityEditResult)
        assert v.name == "new"


async def test_edit_dialog_empty_name_inline_error() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {"v": "untouched"}
        dialog = EditEntityDialog(title="Edit", name="orig")
        app.push(dialog, callback=lambda v: result.update(v=v))
        await pilot.pause()
        name = app.screen.query_one("#edit-name", Input)
        name.value = ""
        await pilot.press("ctrl+s")
        await pilot.pause()
        # The dialog must NOT have dismissed — error rendered inline.
        assert result["v"] == "untouched"
        err = app.screen.query_one("#dialog-error", Static)
        assert "required" in str(err.render()).lower()


async def test_edit_dialog_cancel_returns_none() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {}
        app.push(
            EditEntityDialog(title="Edit", name="orig"),
            callback=lambda v: result.update(v=v),
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert result.get("v") is None


async def test_sort_dialog_returns_selection() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {}
        app.push(
            SortChooserDialog(
                title="Sort",
                fields=[("name", "Name"), ("created_at", "Created")],
                current_field="created_at",
                current_order="desc",
            ),
            callback=lambda v: result.update(v=v),
        )
        await pilot.pause()
        # Move up to the first field (Name) and apply.
        await pilot.press("k")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        v: SortChooserResult | None = result.get("v")
        assert isinstance(v, SortChooserResult)
        assert v.field == "name"


async def test_sort_dialog_toggles_order() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        result: dict = {}
        app.push(
            SortChooserDialog(
                title="Sort",
                fields=[("name", "Name")],
                current_field="name",
                current_order="desc",
            ),
            callback=lambda v: result.update(v=v),
        )
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        v: SortChooserResult | None = result.get("v")
        assert isinstance(v, SortChooserResult)
        assert v.order == "asc"
