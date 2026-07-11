"""The `lumlflow tui` command must fail gracefully when the optional
`tui` extra (textual, textual-plotext) is not installed."""

import sys

import pytest
from lumlflow.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _purge_tui_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "lumlflow.tui" or name.startswith("lumlflow.tui."):
            monkeypatch.delitem(sys.modules, name)


def test_tui_command_hints_extra_when_textual_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _purge_tui_modules(monkeypatch)
    # A None entry in sys.modules makes `import textual` raise
    # ModuleNotFoundError, simulating an install without the extra.
    monkeypatch.setitem(sys.modules, "textual", None)

    result = runner.invoke(app, ["tui"])

    assert result.exit_code == 1
    assert "lumlflow[tui]" in result.output + result.stderr


def test_tui_command_reraises_internal_import_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _purge_tui_modules(monkeypatch)
    monkeypatch.setitem(sys.modules, "lumlflow.tui.keymap", None)

    result = runner.invoke(app, ["tui"])

    assert result.exit_code != 0
    assert "lumlflow[tui]" not in result.output + result.stderr
    assert isinstance(result.exception, ModuleNotFoundError)
