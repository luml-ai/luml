"""Filesystem path completion for text inputs.

Textual `Input` shows a `Suggester`'s completion as ghost text that the
user accepts with `→` at the end of the line. This suggester completes
the trailing component of a filesystem path, preserving whatever prefix
form the user typed (`~`, relative, or absolute) so the ghost text
lines up exactly with the typed value. Directories complete with a
trailing `/` so the user can keep typing into them.
"""

from __future__ import annotations

from pathlib import Path

from textual.suggester import Suggester


class PathSuggester(Suggester):
    """Complete the trailing component of a filesystem path."""

    def __init__(self) -> None:
        # No cache: the filesystem changes underneath us, and the value
        # space is unbounded anyway. Case-sensitive to match POSIX paths.
        super().__init__(use_cache=False, case_sensitive=True)

    async def get_suggestion(self, value: str) -> str | None:
        if not value or value.endswith("/") or value == "~":
            return None
        expanded = Path(value).expanduser()
        prefix = expanded.name
        if not prefix:
            return None
        try:
            matches = sorted(
                entry.name
                for entry in expanded.parent.iterdir()
                if entry.name.startswith(prefix)
            )
        except OSError:
            return None
        if not matches:
            return None
        completed = matches[0]
        suggestion = value + completed[len(prefix) :]
        try:
            if (expanded.parent / completed).is_dir():
                suggestion += "/"
        except OSError:
            pass
        return suggestion if suggestion != value else None


__all__ = ("PathSuggester",)
