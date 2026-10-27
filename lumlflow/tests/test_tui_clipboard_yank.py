"""OSC52 clipboard writes must reach the terminal stream Textual renders to."""

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from lumlflow.tracker import ThreadSafeTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.clipboard import osc52_copy, supports_osc52, terminal_stream
from lumlflow.tui.data import DataFacade


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def app(tmp_path: Path) -> LumlflowApp:
    facade = DataFacade(
        tracker=ThreadSafeTracker(f"sqlite://{tmp_path / 'experiments'}")
    )
    return LumlflowApp(facade=facade, show_first_run_hint=False)


@pytest.mark.parametrize(
    ("value", "sequence"),
    [("hello", "\x1b]52;c;aGVsbG8=\x07"), ("雪", "\x1b]52;c;6Zuq\x07")],
)
async def test_yank_reaches_terminal_during_textual_capture(
    app: LumlflowApp,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    sequence: str,
) -> None:
    terminal = _Terminal()
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    async with app.run_test():
        assert sys.stdout is not terminal
        assert sys.stdout.isatty()
        with patch.object(app, "show_toast") as toast:
            app.yank_to_clipboard(value, label="id")
        assert terminal.getvalue() == sequence
        toast.assert_called_once_with(
            f"Copied id to clipboard.  {value}", severity="success", duration=2.0
        )


@pytest.mark.parametrize("terminal", [None, io.StringIO()])
async def test_yank_warns_without_real_terminal(
    app: LumlflowApp,
    monkeypatch: pytest.MonkeyPatch,
    terminal: io.StringIO | None,
) -> None:
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    async with app.run_test():
        assert sys.stdout.isatty()
        assert supports_osc52() is False
        with patch.object(app, "show_toast") as toast:
            app.yank_to_clipboard("hello")
        toast.assert_called_once_with(
            "Could not copy (terminal does not support OSC52). Value: hello",
            severity="warning",
            duration=4.0,
        )
        if terminal is not None:
            assert terminal.getvalue() == ""


@pytest.mark.parametrize("operation", ["write", "flush"])
async def test_yank_warns_on_terminal_io_failure(
    app: LumlflowApp,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    terminal = _Terminal()
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    async with app.run_test():
        with (
            patch.object(terminal, operation, side_effect=OSError("terminal closed")),
            patch.object(app, "show_toast") as toast,
        ):
            app.yank_to_clipboard("hello")
        toast.assert_called_once_with(
            "Could not copy (terminal closed). Value: hello",
            severity="warning",
            duration=4.0,
        )


def test_terminal_stream_is_the_one_textual_renders_to() -> None:
    expected = sys.__stdout__ if sys.platform == "win32" else sys.__stderr__
    assert terminal_stream() is expected


def test_apple_terminal_does_not_emit_osc52(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = _Terminal()
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert supports_osc52() is False
    assert osc52_copy("hello").ok is False
    assert terminal.getvalue() == ""


@pytest.mark.parametrize("term", ["", "dumb", "unknown"])
def test_unsupported_terminal_does_not_emit_osc52(
    monkeypatch: pytest.MonkeyPatch, term: str
) -> None:
    terminal = _Terminal()
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", term)
    assert supports_osc52() is False
    assert osc52_copy("hello").ok is False
    assert terminal.getvalue() == ""


def test_empty_yank_does_not_emit_osc52(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = _Terminal()
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    assert osc52_copy("").ok is False
    assert terminal.getvalue() == ""


def test_closed_terminal_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = _Terminal()
    terminal.close()
    monkeypatch.setattr(sys, "__stderr__", terminal)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    with patch.object(terminal, "isatty", side_effect=ValueError("terminal closed")):
        assert supports_osc52() is False
        assert osc52_copy("hello").ok is False
