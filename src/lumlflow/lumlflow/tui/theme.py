"""Semantic theme tokens for the TUI.

The TUI ships its own tuned pair of themes (default dark, optional light)
rather than mirroring the web tokens verbatim. The web UI lives behind
high-contrast surfaces (near-black on pure white); a terminal occupying a
full screen for hours wants a calmer register — muted neutral surfaces, a
single blue accent, status conveyed by severity color. See
``Design / Theme`` in ``SPEC.md`` for the anchor values these themes
expose.

Each semantic role (experiment status, trace state, eval score gradient,
tag chip, diff highlight) keeps a fixed meaning across both themes; the
hexes are tuned per theme so they stay readable on each surface without
turning neon.
"""

from dataclasses import dataclass, field

from textual.theme import Theme


@dataclass(frozen=True)
class SemanticPalette:
    status_active: str
    status_completed: str
    status_error: str
    state_ok: str
    state_error: str
    state_in_progress: str
    state_unspecified: str
    diff_changed: str
    pulse: str
    tag_palette: tuple[str, ...]
    score_gradient: tuple[str, ...]


DARK_PALETTE = SemanticPalette(
    status_active="#5b9dff",
    status_completed="#6ec48a",
    status_error="#e07b7b",
    state_ok="#6ec48a",
    state_error="#e07b7b",
    state_in_progress="#dd9a5f",
    state_unspecified="#8a8f99",
    diff_changed="#d9b066",
    pulse="#e0c66a",
    tag_palette=(
        "#5b9dff",
        "#6ec48a",
        "#e07b7b",
        "#dd9a5f",
        "#b58ce0",
        "#5ec3b8",
        "#d986b8",
        "#9a8de0",
    ),
    score_gradient=(
        "#7a2e2e",
        "#c25656",
        "#e07b7b",
        "#dec07a",
        "#a8c97a",
        "#6ec48a",
        "#3e8a5f",
    ),
)


LIGHT_PALETTE = SemanticPalette(
    status_active="#2f6fed",
    status_completed="#2d7a4d",
    status_error="#b04444",
    state_ok="#2d7a4d",
    state_error="#b04444",
    state_in_progress="#b25e2a",
    state_unspecified="#5c626e",
    diff_changed="#9c6a1f",
    pulse="#b88f1d",
    tag_palette=(
        "#2f6fed",
        "#2d7a4d",
        "#b04444",
        "#b25e2a",
        "#7a3fb8",
        "#1f6b6b",
        "#b03c7a",
        "#5e3fb8",
    ),
    score_gradient=(
        "#7a2e2e",
        "#c25656",
        "#e07b7b",
        "#d0a44a",
        "#7aa84a",
        "#2d7a4d",
        "#1f5236",
    ),
)


def _palette_variables(palette: SemanticPalette) -> dict[str, str]:
    vars_: dict[str, str] = {
        "status-active": palette.status_active,
        "status-completed": palette.status_completed,
        "status-error": palette.status_error,
        "state-ok": palette.state_ok,
        "state-error": palette.state_error,
        "state-in-progress": palette.state_in_progress,
        "state-unspecified": palette.state_unspecified,
        "diff-changed": palette.diff_changed,
        "pulse": palette.pulse,
    }
    for i, color in enumerate(palette.tag_palette):
        vars_[f"tag-{i}"] = color
    for i, color in enumerate(palette.score_gradient):
        vars_[f"score-{i}"] = color
    return vars_


# Dark anchors stay in a muted register: the background is a dark slate
# (not pure black) and the foreground a soft off-white (not pure white).
# ``panel`` is one notch lighter than ``surface`` so framed panels read
# as raised cards with visible borders.
LUML_DARK = Theme(
    name="luml-dark",
    primary="#5b9dff",
    secondary="#2a2e38",
    accent="#5b9dff",
    warning="#dd9a5f",
    error="#e07b7b",
    success="#6ec48a",
    foreground="#c8ccd4",
    background="#14161b",
    surface="#1b1e24",
    panel="#232730",
    dark=True,
    variables=_palette_variables(DARK_PALETTE),
)


# Light anchors mirror the dark pair: ``panel`` is one notch darker than
# ``surface`` so borders remain visible against white surfaces.
LUML_LIGHT = Theme(
    name="luml-light",
    primary="#2f6fed",
    secondary="#dfe2e8",
    accent="#2f6fed",
    warning="#b25e2a",
    error="#b04444",
    success="#2d7a4d",
    foreground="#2b2f36",
    background="#f7f8fa",
    surface="#ffffff",
    panel="#eceef2",
    dark=False,
    variables=_palette_variables(LIGHT_PALETTE),
)


@dataclass(frozen=True)
class ThemeBundle:
    dark: Theme = field(default_factory=lambda: LUML_DARK)
    light: Theme = field(default_factory=lambda: LUML_LIGHT)
    dark_palette: SemanticPalette = field(default_factory=lambda: DARK_PALETTE)
    light_palette: SemanticPalette = field(default_factory=lambda: LIGHT_PALETTE)

    def palette(self, *, dark: bool) -> SemanticPalette:
        return self.dark_palette if dark else self.light_palette


def get_theme_bundle() -> ThemeBundle:
    return ThemeBundle()
