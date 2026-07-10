"""Tests for the TUI theme palette.

The contract here mirrors the second task in ``SPEC.md`` ("Soften the TUI
theme palette"): the muted dark/light pair must register on the app, the
dark background must not be pure black, the light foreground must not be
pure white, and the ``t`` toggle must switch between them.
"""

from lumlflow.tui import LumlflowApp
from lumlflow.tui.theme import (
    LUML_DARK,
    LUML_LIGHT,
    get_theme_bundle,
)


def _hex(value: str | None) -> str:
    assert value is not None
    return value.lower()


def test_dark_theme_anchors_are_muted() -> None:
    """The muted-register contract from the Design section.

    The dark theme must never bottom out at pure black background or
    top out at pure white foreground.
    """

    assert _hex(LUML_DARK.background) != "#000000"
    assert _hex(LUML_DARK.foreground) != "#ffffff"


def test_light_theme_anchors_are_muted() -> None:
    """The light theme's foreground stays off-black."""

    assert _hex(LUML_LIGHT.foreground) != "#000000"


def test_panel_border_visible_against_surface() -> None:
    """``$panel`` (used for borders) must differ from ``$surface``.

    Every framed panel in the TUI uses ``border: round $panel`` (or
    ``solid $panel``) on a ``$surface`` background. If the two colors
    matched, borders would disappear.
    """

    assert _hex(LUML_DARK.surface) != _hex(LUML_DARK.panel)
    assert _hex(LUML_LIGHT.surface) != _hex(LUML_LIGHT.panel)


def test_theme_bundle_exposes_both_themes() -> None:
    bundle = get_theme_bundle()
    assert bundle.dark is LUML_DARK
    assert bundle.light is LUML_LIGHT


async def test_both_themes_register_on_app_boot() -> None:
    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        themes = app.available_themes
        assert "luml-dark" in themes
        assert "luml-light" in themes
        # Default boot is the muted dark theme.
        assert app.theme == "luml-dark"


async def test_theme_toggle_switches_between_dark_and_light() -> None:
    """``Ctrl+T`` must cycle the two registered themes.

    A chorded key rather than bare ``t`` — the detail screen uses ``t``
    as the Traces tab mnemonic, so a single-letter theme toggle would
    overlap with tab navigation.
    """

    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "luml-dark"
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.theme == "luml-light"
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.theme == "luml-dark"


def test_semantic_palette_keeps_role_invariants() -> None:
    """Tag and score palette sizes must stay stable across themes.

    Production code indexes into ``tag_palette`` modulo its length and
    relies on a fixed-size ``score_gradient`` for heatmap stops. Tuning
    the colors must not change the counts.
    """

    bundle = get_theme_bundle()
    assert len(bundle.dark_palette.tag_palette) == len(
        bundle.light_palette.tag_palette
    )
    assert len(bundle.dark_palette.score_gradient) == len(
        bundle.light_palette.score_gradient
    )
