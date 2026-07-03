"""Clipboard helpers for the TUI.

The `yank` action copies the focused item's id to the user's clipboard
using the **OSC52** escape sequence, which works through SSH because the
terminal emulator (running locally) handles it — no clipboard daemon
required. Some terminals do not support OSC52 (or it is disabled by the
user); the helper degrades gracefully so the caller can show an
explanatory toast instead of crashing.

Implementation:
- emit `ESC ] 52 ; c ; <base64-payload> BEL` on stdout when the active
  output is a TTY.
- payload is base64-encoded UTF-8 of the string to copy.
- the standard caps text length to a few KB; ids are short so we don't
  worry about chunking.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import IO


@dataclass(frozen=True)
class ClipboardResult:
    """Outcome of a clipboard write attempt."""

    ok: bool
    reason: str | None = None


def supports_osc52() -> bool:
    """Heuristic check for OSC52 support in the current terminal."""

    # If stdout is not a TTY (test harness, piped output), OSC52 can't
    # reach the terminal — there is no terminal to receive it.
    if not sys.stdout.isatty():
        return False
    # `TERM=dumb` and `TERM=unknown` short-circuit since they explicitly
    # disclaim terminal capabilities.
    term = os.environ.get("TERM", "").lower()
    if term in ("", "dumb", "unknown"):
        return False
    # Known terminals that ship with OSC52 enabled by default. This is
    # an allowlist; unknown terminals get an attempt + graceful fallback.
    return True


def osc52_copy(text: str, *, stream: IO[str] | None = None) -> ClipboardResult:
    """Copy `text` to the user's clipboard via OSC52.

    Returns a `ClipboardResult` describing the outcome. The function
    does not raise; callers (the `yank` action) surface the result via
    a toast so the no-hidden-shortcuts invariant holds even when the
    terminal cannot accept the sequence.
    """

    if not text:
        return ClipboardResult(ok=False, reason="nothing to copy")
    out: IO[str] = stream if stream is not None else sys.stdout
    if not supports_osc52() and out is sys.stdout:
        return ClipboardResult(
            ok=False,
            reason="terminal does not support OSC52",
        )
    try:
        payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
        # Standard OSC52 sequence: `ESC ] 52 ; c ; <payload> BEL`.
        # `c` targets the clipboard selection (vs `p`/`s` for primary/select).
        out.write(f"\x1b]52;c;{payload}\x07")
        out.flush()
    except Exception as exc:  # pragma: no cover - terminal/IO weirdness
        return ClipboardResult(ok=False, reason=str(exc))
    return ClipboardResult(ok=True)


# OSC52 cannot *read* the clipboard (terminals disable it for security),
# so reading goes through the platform's CLI tools instead. Ordered by
# platform prevalence; the first available tool that succeeds wins.
_READ_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("wl-paste", "--no-newline"),
    ("xclip", "-selection", "clipboard", "-o"),
    ("xsel", "--clipboard", "--output"),
    ("pbpaste",),
)


def read_system_clipboard(timeout: float = 0.5) -> str | None:
    """Best-effort read of the OS clipboard via common CLI tools.

    Returns `None` when no tool is available or none produced text —
    callers treat that as an empty clipboard, never an error.
    """

    for command in _READ_COMMANDS:
        if shutil.which(command[0]) is None:
            continue
        try:
            proc = subprocess.run(
                command, capture_output=True, timeout=timeout
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        try:
            text = proc.stdout.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if text:
            return text
    return None


__all__ = [
    "ClipboardResult",
    "osc52_copy",
    "read_system_clipboard",
    "supports_osc52",
]
