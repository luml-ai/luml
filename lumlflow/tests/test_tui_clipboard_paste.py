"""Ctrl+V paste support.

Textual's `Input` binds Ctrl+V to paste from the app-internal
clipboard, which only holds text copied inside the app — so pasting an
API key copied from a browser silently inserted nothing. The app now
falls back to the OS clipboard (wl-paste / xclip / xsel / pbpaste)
when the internal clipboard is empty.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from lumlflow.tracker import ThreadSafeTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui import clipboard as clipboard_module
from lumlflow.tui.clipboard import read_system_clipboard
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.cloud_publish import CloudPublishScreen
from textual.widgets import Input

# ---------------------------------------------------------------------------
# read_system_clipboard
# ---------------------------------------------------------------------------


class _Proc:
    def __init__(self, returncode: int, stdout: bytes) -> None:
        self.returncode = returncode
        self.stdout = stdout


class TestReadSystemClipboard:
    def test_returns_first_available_tool_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            clipboard_module.shutil,
            "which",
            lambda name: "/usr/bin/xclip" if name == "xclip" else None,
        )
        calls: list[tuple[str, ...]] = []

        def fake_run(command: tuple[str, ...], **kwargs: Any) -> _Proc:
            calls.append(tuple(command))
            return _Proc(0, b"dfs_secret")

        monkeypatch.setattr(clipboard_module.subprocess, "run", fake_run)
        assert read_system_clipboard() == "dfs_secret"
        assert calls == [("xclip", "-selection", "clipboard", "-o")]

    def test_returns_none_without_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            clipboard_module.shutil, "which", lambda name: None
        )
        assert read_system_clipboard() is None

    def test_skips_failing_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            clipboard_module.shutil,
            "which",
            lambda name: f"/usr/bin/{name}"
            if name in ("wl-paste", "xclip")
            else None,
        )

        def fake_run(command: tuple[str, ...], **kwargs: Any) -> _Proc:
            if command[0] == "wl-paste":
                raise subprocess.TimeoutExpired(cmd=command, timeout=0.5)
            return _Proc(0, b"from-xclip")

        monkeypatch.setattr(clipboard_module.subprocess, "run", fake_run)
        assert read_system_clipboard() == "from-xclip"

    def test_empty_output_is_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            clipboard_module.shutil,
            "which",
            lambda name: "/usr/bin/wl-paste" if name == "wl-paste" else None,
        )
        monkeypatch.setattr(
            clipboard_module.subprocess,
            "run",
            lambda command, **kwargs: _Proc(0, b""),
        )
        assert read_system_clipboard() is None


# ---------------------------------------------------------------------------
# Ctrl+V in the publish flow's API key input
# ---------------------------------------------------------------------------


def _make_app(tmp_path: Path) -> LumlflowApp:
    facade = DataFacade(
        tracker=ThreadSafeTracker(f"sqlite://{tmp_path / 'experiments'}")
    )
    return LumlflowApp(facade=facade)


async def _publish_screen_with_key_input(app: LumlflowApp, pilot: Any) -> Input:
    screen = CloudPublishScreen(facade=app.facade)
    app.push_screen(screen)
    for _ in range(200):
        if screen.query("#publish-api-key-input"):
            break
        await pilot.pause(0.01)
    key_input = screen.query_one("#publish-api-key-input", Input)
    key_input.focus()
    await pilot.pause()
    return key_input


class TestCtrlVPaste:
    async def test_ctrl_v_pastes_system_clipboard(
        self, tmp_path: Path
    ) -> None:
        app = _make_app(tmp_path)
        # has_api_key must be patched or a key stored on the dev machine
        # (keyring / ~/.luml.json) skips the auth step and its input.
        with (
            patch.object(app.facade.auth, "has_api_key", return_value=False),
            patch(
                "lumlflow.tui.app.read_system_clipboard",
                return_value="dfs_pasted_key",
            ),
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                key_input = await _publish_screen_with_key_input(app, pilot)
                await pilot.press("ctrl+v")
                await pilot.pause()
                assert key_input.value == "dfs_pasted_key"

    async def test_internal_clipboard_wins_over_system(
        self, tmp_path: Path
    ) -> None:
        app = _make_app(tmp_path)
        with (
            patch.object(app.facade.auth, "has_api_key", return_value=False),
            patch(
                "lumlflow.tui.app.read_system_clipboard",
                return_value="from-system",
            ),
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                key_input = await _publish_screen_with_key_input(app, pilot)
                app.copy_to_clipboard("from-app")
                await pilot.press("ctrl+v")
                await pilot.pause()
                assert key_input.value == "from-app"

    async def test_empty_everything_pastes_nothing(
        self, tmp_path: Path
    ) -> None:
        app = _make_app(tmp_path)
        with (
            patch.object(app.facade.auth, "has_api_key", return_value=False),
            patch(
                "lumlflow.tui.app.read_system_clipboard", return_value=None
            ),
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                key_input = await _publish_screen_with_key_input(app, pilot)
                await pilot.press("ctrl+v")
                await pilot.pause()
                assert key_input.value == ""
