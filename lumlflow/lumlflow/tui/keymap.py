"""Central keymap registry.

Bindings are registered here once and consumed by the footer, the help
cheat-sheet, the command palette, and the inline key affordances. This
is the single source of truth behind the no-hidden-shortcuts invariant.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Literal

from textual.binding import Binding

Scope = Literal[
    "global",
    "list",
    "actions",
    "selection",
    "models",
    "metrics",
    "attachments",
    "annotations",
    "tabs",
    "span_tree",
    "dialog",
    "input",
]


@dataclass(frozen=True)
class Command:
    """A registered, discoverable action.

    The same instance feeds the footer, `?` cheat-sheet, command palette
    list, and any inline key affordance attached to a widget.
    """

    id: str
    key: str
    label: str
    description: str
    scope: Scope = "global"
    group: str = "General"
    show_in_footer: bool = True
    palette_only: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def display_keys(self) -> tuple[str, ...]:
        return (self.key, *self.aliases)

    def to_binding(self, action: str | None = None) -> Binding:
        """Build a Textual Binding for this command.

        `action` is the action method name to invoke; defaults to the
        command id with dots replaced by underscores.
        """

        action_name = action or self.id.replace(".", "_")
        return Binding(
            key=self.key,
            action=action_name,
            description=self.label,
            show=self.show_in_footer,
            id=self.id,
        )


class KeymapRegistry:
    """Registry of every discoverable command in the app."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> Command:
        if command.id in self._commands:
            raise ValueError(f"Command id already registered: {command.id}")
        self._commands[command.id] = command
        return command

    def register_many(self, commands: Iterable[Command]) -> None:
        for command in commands:
            self.register(command)

    def get(self, command_id: str) -> Command:
        return self._commands[command_id]

    def __contains__(self, command_id: str) -> bool:
        return command_id in self._commands

    def __iter__(self) -> Iterator[Command]:
        return iter(self._commands.values())

    def __len__(self) -> int:
        return len(self._commands)

    def all(self) -> list[Command]:
        return list(self._commands.values())

    def by_scope(self, scope: Scope) -> list[Command]:
        return [c for c in self._commands.values() if c.scope == scope]

    def footer_for(self, scopes: Iterable[Scope]) -> list[Command]:
        wanted = set(scopes)
        return [
            c
            for c in self._commands.values()
            if c.show_in_footer and not c.palette_only and c.scope in wanted
        ]

    def palette_entries(self) -> list[Command]:
        return [c for c in self._commands.values() if not c.palette_only or True]


def build_default_registry() -> KeymapRegistry:
    """Build the registry containing the v1 keymap contract from SPEC.md."""

    registry = KeymapRegistry()

    # Global commands (any non-input context).
    registry.register_many(
        [
            Command(
                id="global.help",
                key="question_mark",
                label="Help",
                description="Open help / searchable keymap cheat-sheet",
                scope="global",
                group="Global",
            ),
            Command(
                id="global.palette",
                key="colon",
                label="Command palette",
                description="Jump-to + run any registered action",
                scope="global",
                group="Global",
                aliases=("ctrl+p",),
            ),
            # Screen history is driven by Ctrl+arrows only. Plain arrows
            # stay in-widget (cursor / scroll) — DataTable, Tree, and the
            # scroll containers all bind them, so a plain-arrow Back alias
            # fired only when focus happened to be somewhere without its
            # own arrow binding, which made navigation feel random.
            Command(
                id="global.back",
                key="escape",
                label="Back",
                description="Cancel input · close overlay · go back a screen",
                scope="global",
                group="Global",
                aliases=("q", "ctrl+left"),
            ),
            Command(
                id="global.forward",
                key="ctrl+right",
                label="Forward",
                description="Go forward to the screen you came back from",
                scope="global",
                group="Global",
                show_in_footer=False,
            ),
            Command(
                id="global.quit",
                key="ctrl+c",
                label="Quit",
                description="Quit (confirm if a run is active)",
                scope="global",
                group="Global",
                show_in_footer=False,
            ),
            Command(
                id="global.refresh_now",
                key="r",
                label="Refresh",
                description="Refresh now",
                scope="global",
                group="Refresh",
            ),
            Command(
                id="global.toggle_auto_refresh",
                key="R",
                label="Auto-refresh",
                description="Toggle live auto-refresh",
                scope="global",
                group="Refresh",
                show_in_footer=False,
            ),
            Command(
                id="global.upload",
                key="u",
                label="Upload",
                description="Upload an artifact file from disk to luml cloud",
                scope="global",
                group="Cloud",
            ),
            # Ctrl+T, not bare `t`: the experiment-detail screen uses
            # `t` as the Traces tab mnemonic, so a bare-letter theme
            # toggle either shadowed the tab jump or flipped the theme
            # by surprise depending on the screen. A chorded key keeps
            # single letters free for navigation verbs.
            Command(
                id="global.toggle_theme",
                key="ctrl+t",
                label="Theme",
                description="Toggle theme (dark/light)",
                scope="global",
                group="Global",
                show_in_footer=False,
            ),
            Command(
                id="global.cycle_focus",
                key="tab",
                label="Next pane",
                description="Move focus between panes",
                scope="global",
                group="Focus",
                show_in_footer=False,
            ),
            Command(
                id="global.cycle_focus_back",
                key="shift+tab",
                label="Prev pane",
                description="Move focus to previous pane",
                scope="global",
                group="Focus",
                show_in_footer=False,
            ),
        ]
    )

    # Lists and tables.
    registry.register_many(
        [
            Command(
                id="list.down",
                key="j",
                label="Down",
                description="Move row down",
                scope="list",
                group="Navigation",
                aliases=("down",),
                show_in_footer=False,
            ),
            Command(
                id="list.up",
                key="k",
                label="Up",
                description="Move row up",
                scope="list",
                group="Navigation",
                aliases=("up",),
                show_in_footer=False,
            ),
            Command(
                id="list.half_page_down",
                key="ctrl+d",
                label="Half-page down",
                description="Move half a page down",
                scope="list",
                group="Navigation",
                aliases=("pagedown",),
                show_in_footer=False,
            ),
            Command(
                id="list.half_page_up",
                key="ctrl+u",
                label="Half-page up",
                description="Move half a page up",
                scope="list",
                group="Navigation",
                aliases=("pageup",),
                show_in_footer=False,
            ),
            Command(
                id="list.first",
                key="g",
                label="First",
                description="Jump to first row",
                scope="list",
                group="Navigation",
                show_in_footer=False,
            ),
            Command(
                id="list.last",
                key="G",
                label="Last",
                description="Jump to last row",
                scope="list",
                group="Navigation",
                show_in_footer=False,
            ),
            Command(
                id="list.open",
                key="enter",
                label="Open",
                description="Open / drill in",
                scope="list",
                group="Navigation",
            ),
            # Selection / bulk verbs live in their own scope so they only
            # appear in the footer on screens that actually support
            # multi-select (the experiments list) — showing "[Space]
            # Select" on Groups was a lie.
            Command(
                id="list.select",
                key="space",
                label="Select",
                description="Toggle selection (multi-select)",
                scope="selection",
                group="Selection",
            ),
            Command(
                id="list.search",
                key="/",
                label="Search",
                description="Incremental free-text search",
                scope="list",
                group="Find",
            ),
            Command(
                id="list.filter",
                key="f",
                label="Filter",
                description="Advanced filter editor (DSL, live-validated)",
                scope="list",
                group="Find",
            ),
            Command(
                id="list.sort",
                key="s",
                label="Sort",
                description="Sort field/order chooser",
                scope="list",
                group="Find",
            ),
            # Edit/delete are "actions" rather than plain "list" so
            # browse-only tables (the traces / evals tabs, where `e`
            # means the Evals tab) don't advertise keys they don't have.
            Command(
                id="list.edit",
                key="e",
                label="Edit",
                description="Edit focused item (name/description/tags)",
                scope="actions",
                group="Actions",
            ),
            Command(
                id="list.delete",
                key="d",
                label="Delete",
                description="Delete focused item (with confirm)",
                scope="actions",
                group="Actions",
            ),
            Command(
                id="list.annotate",
                key="a",
                label="Annotate",
                description="Annotate the focused span / eval",
                scope="annotations",
                group="Annotations",
            ),
            Command(
                id="annotations.edit_annotation",
                key="e",
                label="Edit",
                description="Edit the focused annotation",
                scope="annotations",
                group="Annotations",
            ),
            Command(
                id="annotations.delete_annotation",
                key="d",
                label="Delete",
                description="Delete the focused annotation (with confirm)",
                scope="annotations",
                group="Annotations",
            ),
            Command(
                id="annotations.yank",
                key="y",
                label="Yank id",
                description="Copy the focused span / eval id",
                scope="annotations",
                group="Annotations",
                show_in_footer=False,
            ),
            Command(
                id="list.compare",
                key="c",
                label="Compare",
                description="Compare selected items",
                scope="selection",
                group="Selection",
            ),
            Command(
                id="list.publish",
                key="p",
                label="Publish",
                description="Publish focused/selected to cloud",
                scope="selection",
                group="Selection",
            ),
            Command(
                id="list.yank",
                key="y",
                label="Yank id",
                description="Copy focused item id to clipboard (OSC52)",
                scope="list",
                group="Actions",
            ),
        ]
    )

    # Experiment-detail tabs. Lowercase letters are the primary keys (they
    # line up with the visible tab labels); the numeric position and the
    # uppercase variant are aliases.
    for i, (mnemonic, name) in enumerate(
        [
            ("o", "Overview"),
            ("m", "Metrics"),
            ("t", "Traces"),
            ("e", "Evals"),
            ("a", "Attachments"),
        ],
        start=1,
    ):
        registry.register(
            Command(
                id=f"tabs.jump_{name.lower()}",
                key=mnemonic,
                label=name,
                description=f"Jump to {name} tab",
                scope="tabs",
                group="Tabs",
                aliases=(str(i), mnemonic.upper()),
                # The tab bar itself shows every label with its number
                # and highlighted mnemonic — repeating all five in the
                # footer only crowded out the hints that have no other
                # on-screen surface.
                show_in_footer=False,
            )
        )

    registry.register_many(
        [
            Command(
                id="tabs.prev",
                key="[",
                label="Prev tab",
                description="Previous tab",
                scope="tabs",
                group="Tabs",
                show_in_footer=False,
            ),
            Command(
                id="tabs.next",
                key="]",
                label="Next tab",
                description="Next tab",
                scope="tabs",
                group="Tabs",
                show_in_footer=False,
            ),
        ]
    )

    # Metrics tab: zoom into a single chart + chart-shaping toggles.
    # Scoped to "metrics" so the hints only show while the Metrics tab
    # is the active surface.
    registry.register_many(
        [
            Command(
                id="metrics.zoom",
                key="enter",
                label="Zoom",
                description="Open the focused mini-chart in the zoom view",
                scope="metrics",
                group="Metrics",
            ),
            Command(
                id="metrics.grid_nav",
                key="up",
                label="Move between charts",
                description=(
                    "Arrow keys (or h/j/k/l) move between mini-charts; "
                    "Enter zooms, Esc returns"
                ),
                scope="metrics",
                group="Metrics",
                aliases=("down", "left", "right"),
                show_in_footer=False,
            ),
            Command(
                id="metrics.toggle_smoothing",
                key="S",
                label="Smoothing",
                description="Toggle exponential moving average on the zoomed metric",
                scope="metrics",
                group="Metrics",
            ),
            Command(
                id="metrics.toggle_log_scale",
                key="L",
                label="Log scale",
                description="Toggle log-scale Y axis on the zoomed metric",
                scope="metrics",
                group="Metrics",
            ),
            Command(
                id="metrics.toggle_x_axis",
                key="X",
                label="X axis",
                description="Toggle X axis between step and wall-clock",
                scope="metrics",
                group="Metrics",
            ),
        ]
    )

    # Overview tab: verbs on the linked-models table.
    registry.register_many(
        [
            Command(
                id="models.edit",
                key="enter",
                label="Edit model",
                description="Edit the focused linked model (name/description/tags)",
                scope="models",
                group="Models",
            ),
            Command(
                id="models.delete",
                key="d",
                label="Delete model",
                description="Delete the focused linked model (with confirm)",
                scope="models",
                group="Models",
            ),
            Command(
                id="models.publish",
                key="p",
                label="Publish model",
                description="Publish the focused linked model to luml cloud",
                scope="models",
                group="Models",
            ),
            Command(
                id="models.yank",
                key="y",
                label="Yank id",
                description="Copy the focused model id",
                scope="models",
                group="Models",
                show_in_footer=False,
            ),
        ]
    )

    # Attachments tab: preview / save-to-disk / yank on the file tree.
    registry.register_many(
        [
            Command(
                id="attachments.preview",
                key="enter",
                label="Preview",
                description="Preview the focused attachment inline",
                scope="attachments",
                group="Attachments",
            ),
            Command(
                id="attachments.save",
                key="s",
                label="Save to disk",
                description="Save the focused attachment to a local path",
                scope="attachments",
                group="Attachments",
                aliases=("w",),
            ),
            Command(
                id="attachments.yank",
                key="y",
                label="Yank path",
                description="Copy the focused attachment path",
                scope="attachments",
                group="Attachments",
                show_in_footer=False,
            ),
        ]
    )

    # Span tree navigation.
    registry.register_many(
        [
            Command(
                id="span_tree.collapse",
                key="h",
                label="Collapse",
                description="Collapse current node",
                scope="span_tree",
                group="Span tree",
                aliases=("left",),
                show_in_footer=False,
            ),
            Command(
                id="span_tree.expand",
                key="l",
                label="Expand",
                description="Expand current node",
                scope="span_tree",
                group="Span tree",
                aliases=("right",),
                show_in_footer=False,
            ),
            Command(
                id="span_tree.show_detail",
                key="enter",
                label="Show detail",
                description="Show span detail in the adjacent pane",
                scope="span_tree",
                group="Span tree",
            ),
        ]
    )

    # Dialog / input control keys.
    registry.register_many(
        [
            Command(
                id="dialog.confirm",
                key="enter",
                label="Confirm",
                description="Confirm / submit",
                scope="dialog",
                group="Dialog",
            ),
            Command(
                id="dialog.cancel",
                key="escape",
                label="Cancel",
                description="Cancel and return to navigation",
                scope="dialog",
                group="Dialog",
            ),
            Command(
                id="dialog.next_field",
                key="tab",
                label="Next field",
                description="Next field",
                scope="dialog",
                group="Dialog",
                show_in_footer=False,
            ),
            Command(
                id="dialog.prev_field",
                key="shift+tab",
                label="Prev field",
                description="Previous field",
                scope="dialog",
                group="Dialog",
                show_in_footer=False,
            ),
        ]
    )

    # Palette-only actions — no global key binding, but discoverable
    # via `:` and `?`. SPEC: "Select-all / clear are available via the
    # palette."
    registry.register_many(
        [
            Command(
                id="selection.select_all",
                key="",
                label="Select all (current page)",
                description="Mark every experiment on this screen for comparison",
                scope="global",
                group="Selection",
                show_in_footer=False,
                palette_only=True,
            ),
            Command(
                id="selection.clear",
                key="",
                label="Clear selection",
                description="Unselect every experiment queued for comparison",
                scope="global",
                group="Selection",
                show_in_footer=False,
                palette_only=True,
            ),
            Command(
                id="navigation.home",
                key="",
                label="Go to Groups (home)",
                description="Pop back to the home / Groups screen",
                scope="global",
                group="Navigation",
                show_in_footer=False,
                palette_only=True,
            ),
            Command(
                id="navigation.up",
                key="",
                label="Navigate up",
                description="Pop the current screen — same as Esc/`q`/`Ctrl+←`",
                scope="global",
                group="Navigation",
                show_in_footer=False,
                palette_only=True,
            ),
            Command(
                id="global.messages",
                key="",
                label="Recent messages",
                description="Show the last status messages (toasts)",
                scope="global",
                group="Global",
                show_in_footer=False,
                palette_only=True,
            ),
        ]
    )

    # Live-refresh cadence presets — palette-only so users can slow the
    # polling on a sluggish store (or speed it up) without restarting.
    for seconds in (1, 2, 10):
        registry.register(
            Command(
                id=f"refresh.interval_{seconds}",
                key="",
                label=f"Refresh every {seconds}s",
                description=f"Set the live auto-refresh interval to {seconds}s",
                scope="global",
                group="Refresh",
                show_in_footer=False,
                palette_only=True,
            )
        )

    return registry
