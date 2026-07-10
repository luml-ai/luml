"""Tests for the filesystem PathSuggester used by path inputs."""

from __future__ import annotations

from pathlib import Path

from lumlflow.tui.widgets.path_suggester import PathSuggester


class TestPathSuggester:
    async def test_completes_unique_prefix(self, tmp_path: Path) -> None:
        (tmp_path / "model.luml").write_bytes(b"x")
        suggester = PathSuggester()
        value = str(tmp_path / "mod")
        suggestion = await suggester.get_suggestion(value)
        assert suggestion == str(tmp_path / "model.luml")
        # The typed value is a strict prefix, as the Input ghost requires.
        assert suggestion.startswith(value)

    async def test_directory_completes_with_trailing_slash(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "checkpoints").mkdir()
        suggester = PathSuggester()
        suggestion = await suggester.get_suggestion(str(tmp_path / "check"))
        assert suggestion == str(tmp_path / "checkpoints") + "/"

    async def test_first_match_alphabetically(self, tmp_path: Path) -> None:
        (tmp_path / "run-b.luml").write_bytes(b"x")
        (tmp_path / "run-a.luml").write_bytes(b"x")
        suggester = PathSuggester()
        suggestion = await suggester.get_suggestion(str(tmp_path / "run"))
        assert suggestion == str(tmp_path / "run-a.luml")

    async def test_no_match_returns_none(self, tmp_path: Path) -> None:
        suggester = PathSuggester()
        assert await suggester.get_suggestion(str(tmp_path / "zzz")) is None

    async def test_missing_parent_returns_none(self, tmp_path: Path) -> None:
        suggester = PathSuggester()
        value = str(tmp_path / "no" / "such" / "dir" / "x")
        assert await suggester.get_suggestion(value) is None

    async def test_empty_and_trailing_slash_return_none(
        self, tmp_path: Path
    ) -> None:
        suggester = PathSuggester()
        assert await suggester.get_suggestion("") is None
        assert await suggester.get_suggestion(str(tmp_path) + "/") is None

    async def test_exact_match_returns_none(self, tmp_path: Path) -> None:
        # Nothing left to complete — no ghost text.
        (tmp_path / "model.luml").write_bytes(b"x")
        suggester = PathSuggester()
        assert (
            await suggester.get_suggestion(str(tmp_path / "model.luml"))
            is None
        )
