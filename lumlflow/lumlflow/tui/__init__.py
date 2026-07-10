"""Terminal UI for Lumlflow.

This package implements `lumlflow tui` — a keyboard-first terminal UI
over the same handler layer the web backend uses. The TUI is
server-less and in-process: it imports the handler classes and talks to
SQLite directly via a shared `ThreadSafeTracker`.
"""

from lumlflow.tui.app import LumlflowApp
from lumlflow.tui.data import (
    DataFacade,
    FacadeError,
    Result,
    run_in_thread,
    run_in_worker,
)
from lumlflow.tui.keymap import Command, KeymapRegistry, build_default_registry
from lumlflow.tui.live_refresh import LiveRefreshable, LiveRefreshScheduler
from lumlflow.tui.theme import (
    LUML_DARK,
    LUML_LIGHT,
    SemanticPalette,
    ThemeBundle,
    get_theme_bundle,
)

__all__ = [
    "Command",
    "DataFacade",
    "FacadeError",
    "KeymapRegistry",
    "LUML_DARK",
    "LUML_LIGHT",
    "LiveRefreshScheduler",
    "LiveRefreshable",
    "LumlflowApp",
    "Result",
    "SemanticPalette",
    "ThemeBundle",
    "build_default_registry",
    "get_theme_bundle",
    "run_in_thread",
    "run_in_worker",
]
