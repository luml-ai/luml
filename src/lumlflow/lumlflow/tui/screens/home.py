"""The home screen of the TUI.

Per SPEC.md the home screen *is* the Groups list — a synthetic
"All experiments" entry plus every experiment group, with search,
sort, lazy pagination, drill-in, edit and delete. `HomeScreen` is
kept as an alias of `GroupsScreen` so existing references and
type checks (`isinstance(app.screen, HomeScreen)`) remain valid
while the real implementation lives in `groups.py`.
"""

from lumlflow.tui.screens.groups import GroupsScreen


class HomeScreen(GroupsScreen):
    """Alias: the home screen is the Groups screen."""
