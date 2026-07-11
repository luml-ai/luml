"""Main Textual application shell for the Lumlflow TUI."""

from collections import deque
from datetime import datetime

from textual.app import App, ComposeResult, ScreenError
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Input

from lumlflow.schemas.experiments import ExperimentDetails
from lumlflow.tui.clipboard import osc52_copy, read_system_clipboard
from lumlflow.tui.data import DataFacade
from lumlflow.tui.keymap import Command, KeymapRegistry, build_default_registry
from lumlflow.tui.live_refresh import LiveRefreshScheduler
from lumlflow.tui.run_manager import RunSpec
from lumlflow.tui.screens import BaseScreen, HomeScreen
from lumlflow.tui.screens.run_attach import (
    DEFAULT_ATTACH_TIMEOUT,
    RunAttachScreen,
)
from lumlflow.tui.theme import ThemeBundle, get_theme_bundle
from lumlflow.tui.widgets import (
    CommandPalette,
    ContextualFooter,
    HelpCheatsheet,
    PaletteEntry,
    StatusHeader,
    ToastHost,
)
from lumlflow.tui.widgets.breadcrumb import Breadcrumb
from lumlflow.tui.widgets.dialogs import ConfirmDialog
from lumlflow.tui.widgets.modal import DialogClosed, DialogOpened
from lumlflow.tui.widgets.toast import ToastSeverity

# Keys that act as commands outside text inputs but must be passed through
# to inputs as literal text. Inside an input we only intercept Esc / Enter / Tab.
_INPUT_PASSTHROUGH_CONTROLS = {"escape", "enter", "tab", "shift+tab"}


class LumlflowApp(App[None]):
    """Top-level Textual app.

    The shell wires the breadcrumb header, contextual footer, toast host,
    keymap-driven global bindings, and the dark/light theme. Screens are
    pushed via `push_screen` and their state is preserved via the
    `BaseScreen` snapshot/restore protocol.
    """

    CSS = """
    Screen {
        background: $background;
        color: $foreground;
    }
    """

    # Disable Textual's built-in command palette — we ship our own that is
    # driven by the keymap registry, so `:` and `Ctrl-p` should open our
    # palette and not the framework's. Without this flag, Textual's app
    # binding for `ctrl+p` takes priority over ours.
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        keymap: KeymapRegistry | None = None,
        theme_bundle: ThemeBundle | None = None,
        refresh_interval: float = 2.0,
        auto_refresh: bool = True,
        home_screen_factory=HomeScreen,
        run_spec: RunSpec | None = None,
        store_uri: str | None = None,
        attach_timeout: float = DEFAULT_ATTACH_TIMEOUT,
        show_first_run_hint: bool = True,
    ) -> None:
        super().__init__()
        # Facade is constructed lazily on first access if the caller did
        # not provide one. Tests typically pass an in-memory facade so
        # the app boots without touching the production tracker.
        self._facade: DataFacade | None = facade
        self.keymap = keymap or build_default_registry()
        self.theme_bundle = theme_bundle or get_theme_bundle()
        self.refresh_interval = refresh_interval
        # NB: `auto_refresh` is a reactive on `DOMNode`; we expose our
        # own toggle as `live_refresh_on` to avoid clobbering it.
        self.live_refresh_on = auto_refresh
        self._home_screen_factory = home_screen_factory
        self._open_dialog_count = 0
        self._refresh_scheduler = LiveRefreshScheduler(
            self, interval=refresh_interval
        )
        # Run-and-attach state. `run_spec` is set when `lumlflow tui <script>`
        # was invoked; on boot the app pushes a `RunAttachScreen` so the
        # script runs as a child and the TUI watches for its experiment.
        self._run_spec: RunSpec | None = run_spec
        self._store_uri: str | None = store_uri
        self._attach_timeout: float = attach_timeout
        self._active_run_screen: RunAttachScreen | None = None
        self._quit_in_progress: bool = False
        # `q` on home arms a short press-again-to-quit window.
        self._quit_armed: bool = False
        # Rolling log of toasts so a missed message isn't gone forever —
        # surfaced via the palette's "Recent messages" entry.
        self._recent_messages: deque[tuple[str, str, str]] = deque(maxlen=50)
        # Cross-screen experiment selection state. Per SPEC: selected
        # experiments survive navigation between groups so the user can
        # gather across groups then `c` to compare. The id-keyed dict
        # remembers each experiment's full details so the comparison
        # screen has the static/dynamic params + group name + status
        # without needing another fetch round-trip.
        self._selected_experiments: dict[str, ExperimentDetails] = {}
        # First-run discoverability: a one-shot toast pointing at `?` so
        # the user immediately knows where the cheat-sheet lives. Tests
        # disable it so toast assertions stay deterministic.
        self._show_first_run_hint = show_first_run_hint
        self._first_run_hint_shown = False
        # Chrome is rebuilt per screen, so persistent status that must
        # survive a screen push (the loading spinner state) is tracked
        # here and re-applied to the active screen's header on sync.
        self._loading_state = False
        # Browser-style screen history. `Ctrl+←` (and Esc/`q`) go back
        # a screen, pushing the popped screen onto `_forward_stack`;
        # `Ctrl+→` re-pushes the most recent one. Any fresh drill-in
        # invalidates the forward history. `_navigating_forward` guards
        # the re-push so it does not clear the very stack it reads from.
        self._forward_stack: list[BaseScreen] = []
        self._navigating_forward = False
        self._register_global_bindings()

    @property
    def facade(self) -> DataFacade:
        """The shared `DataFacade` instance used by every screen.

        Constructed lazily so an app instantiated with no facade still
        boots — useful for tests that only verify chrome / keymap.
        """

        if self._facade is None:
            self._facade = self._build_facade()
        return self._facade

    # ----- Chrome accessors -----
    #
    # The breadcrumb header, footer and toast host live on the active
    # ``BaseScreen`` (see ``BaseScreen.compose``). These accessors resolve
    # the chrome of the topmost ``BaseScreen`` in the stack so app-level
    # status updates reach whatever screen is currently showing — and
    # return ``None`` (callers no-op) when only a chrome-less overlay such
    # as a dialog or the command palette is active.

    def _chrome_screen(self) -> BaseScreen | None:
        for screen in reversed(self.screen_stack):
            if isinstance(screen, BaseScreen):
                return screen
        return None

    @property
    def _header(self) -> StatusHeader | None:
        screen = self._chrome_screen()
        if screen is None:
            return None
        try:
            return screen.query_one("#app-header", StatusHeader)
        except Exception:
            return None

    @property
    def _footer(self) -> ContextualFooter | None:
        screen = self._chrome_screen()
        if screen is None:
            return None
        try:
            return screen.query_one("#app-footer", ContextualFooter)
        except Exception:
            return None

    @property
    def _toast_host(self) -> ToastHost | None:
        screen = self._chrome_screen()
        if screen is None:
            return None
        try:
            return screen.query_one("#app-toasts", ToastHost)
        except Exception:
            return None

    def _build_facade(self) -> DataFacade:
        """Build the data facade against the CLI-resolved store.

        When the CLI passes a `store_uri` we bind the facade's tracker to
        exactly that store, so the TUI reads from the same place the CLI
        resolved, displayed, and shares with any launched child run —
        rather than re-deriving the path from settings (which depends on
        env vars, the working directory's `.env`, and lru-cache timing).
        """
        if self._store_uri is not None:
            from lumlflow.tracker import ThreadSafeTracker

            return DataFacade(tracker=ThreadSafeTracker(self._store_uri))
        return DataFacade()

    def _register_global_bindings(self) -> None:
        """Install bindings on this App for every `global`-scope command."""

        # Textual lets us set BINDINGS in subclasses but we want the
        # source of truth to be the keymap registry. We build bindings
        # programmatically and store them on the class.
        bindings: list[Binding] = []
        action_map = {
            "global.help": "show_help",
            "global.palette": "show_palette",
            "global.back": "back",
            "global.forward": "forward",
            "global.quit": "quit",
            "global.refresh_now": "refresh_now",
            "global.toggle_auto_refresh": "toggle_auto_refresh",
            "global.toggle_theme": "toggle_theme",
            "global.cycle_focus": "cycle_focus",
            "global.cycle_focus_back": "cycle_focus_back",
        }
        for cmd_id, action in action_map.items():
            if cmd_id not in self.keymap:
                continue
            cmd = self.keymap.get(cmd_id)
            for key in cmd.display_keys:
                # `q` follows the htop/lazygit convention: back on child
                # screens, quit (with a confirm re-press) on home — so it
                # routes through its own action rather than plain back.
                key_action = action
                if cmd_id == "global.back" and key == "q":
                    key_action = "back_or_quit"
                bindings.append(
                    Binding(
                        key=key,
                        action=key_action,
                        description=cmd.label,
                        show=cmd.show_in_footer and key == cmd.key,
                        id=cmd.id,
                    )
                )
        # `App._bindings` is the per-instance binding chain; reassigning
        # here ensures the registry-derived bindings replace the defaults.
        for binding in bindings:
            self._bindings.bind(
                binding.key,
                binding.action,
                description=binding.description,
                show=binding.show,
            )

    # ----- Composition -----

    def compose(self) -> ComposeResult:
        # The chrome (breadcrumb header, contextual footer, toast host) is
        # composed per-screen by ``BaseScreen`` so it stays visible above
        # every pushed screen — a screen mounted on the app's default
        # screen would be painted over by the next ``push_screen``. So the
        # app itself mounts nothing on its default screen.
        yield from ()

    def on_mount(self) -> None:
        self.register_theme(self.theme_bundle.dark)
        self.register_theme(self.theme_bundle.light)
        self.theme = self.theme_bundle.dark.name
        # Build the shared facade up front when a store was resolved by the
        # CLI. Screens read `app._facade` directly (they avoid the lazy
        # `facade` property to keep chrome-only tests filesystem-free), so
        # without this the home screen would find no facade and render the
        # empty state even when the store has runs.
        if self._facade is None and self._store_uri is not None:
            self._facade = self._build_facade()
        # The store path/URI is surfaced in the header by
        # `_sync_chrome_to_screen`, which runs after the home screen (and
        # its chrome) is mounted below.
        # Push the home screen so the breadcrumb / footer reflect a real screen.
        self.push_screen(self._home_screen_factory())
        # Run-and-attach: if a script was supplied on the CLI, layer the
        # `RunAttachScreen` on top of the home screen so the home is the
        # natural fallback once the run finishes (or the user pops the
        # screen). The screen itself owns the subprocess lifecycle.
        if self._run_spec is not None and self._store_uri is not None:
            run_screen = RunAttachScreen(
                facade=self._facade,
                spec=self._run_spec,
                store_uri=self._store_uri,
                attach_timeout=self._attach_timeout,
            )
            self._active_run_screen = run_screen
            self.push_screen(run_screen)
        # Sync immediately so tests + the first render see correct chrome.
        self.call_after_refresh(self._sync_chrome_to_screen)
        # Start the live-refresh scheduler. Ticks check the toggle / dialog
        # state, so it is safe to start even when auto-refresh is off.
        self._refresh_scheduler.start()
        # First-run discoverability: a single toast on launch pointing at
        # `?` and `:` so the user immediately knows where to start.
        if self._show_first_run_hint and not self._first_run_hint_shown:
            self._first_run_hint_shown = True
            self.call_after_refresh(self._show_first_run_hint_toast)

    # ----- Scopes / header sync -----

    def push_screen(self, screen, callback=None, wait_for_dismiss=False):  # type: ignore[override]
        """Push a screen and sync the chrome to it on next refresh.

        Textual delivers `ScreenResume` only to the Screen itself (it
        does not bubble to the App), so we hook here to keep the header
        and footer in sync with the active screen's breadcrumb/scopes.
        """

        # A fresh drill-in (any real screen push that is not a forward
        # replay) invalidates the forward history — you can't redo a
        # branch you've navigated away from. Overlays such as the help
        # sheet, command palette, and dialogs are not `BaseScreen`s, so
        # opening them leaves the history intact.
        if (
            isinstance(screen, BaseScreen)
            and not self._navigating_forward
        ):
            self._clear_forward_history()
        result = super().push_screen(
            screen,
            callback=callback,
            wait_for_dismiss=wait_for_dismiss,
        )
        self.call_after_refresh(self._sync_chrome_to_screen)
        return result

    def pop_screen(self):  # type: ignore[override]
        result = super().pop_screen()
        self.call_after_refresh(self._sync_chrome_to_screen)
        return result

    def _sync_chrome_to_screen(self) -> None:
        """Point the active screen's chrome at the current app state.

        Each screen carries its own header/footer, so on every push/pop
        we (re)apply the breadcrumb, footer scopes, store label, and the
        persistent status cluster (selection / loading / auto-refresh) to
        whatever screen is now on top.
        """

        screen = self._chrome_screen()
        if screen is None:
            return
        header = self._header
        if header is not None:
            header.set_breadcrumb(screen.breadcrumb_segments())
            if self._store_uri:
                header.set_store_label(self._store_uri)
            header.selection_count = len(self._selected_experiments)
            header.loading = self._loading_state
            header.auto_refresh_on = (
                self.live_refresh_on and not self.is_refresh_paused
            )
        footer = self._footer
        if footer is not None:
            footer.set_scopes(screen.footer_scopes())

    # ----- Modeless input rule -----

    def on_key(self, event) -> None:
        """Enforce the modeless input rule.

        Outside an input, single keys are commands (Textual handles via
        bindings). Inside a text input, every key must be literal text —
        except Esc, Enter, and Tab which remain controls. We mark the
        event as handled in pass-through cases so global bindings on
        printable keys don't steal letters typed in the input.
        """

        focused = self.focused
        if focused is None:
            return
        if not _is_text_input(focused):
            return
        if event.key in _INPUT_PASSTHROUGH_CONTROLS:
            return
        # Stop propagation so the App's key handler does not match a
        # printable character against a global binding.
        event.stop()

    # ----- Pause/resume auto-refresh around dialogs -----

    @property
    def is_refresh_paused(self) -> bool:
        """True when refresh must be paused — currently: any modal open.

        The scheduler reads this on each tick and skips the cycle while
        a dialog/editor is open so the underlying list does not shift
        under the dialog. The manual `r` key bypasses this gate.
        """

        return self._open_dialog_count > 0

    def on_dialog_opened(self, _: DialogOpened) -> None:
        self._open_dialog_count += 1
        header = self._header
        if header is not None:
            header.auto_refresh_on = (
                self.live_refresh_on if self._open_dialog_count == 0 else False
            )

    def on_dialog_closed(self, _: DialogClosed) -> None:
        self._open_dialog_count = max(0, self._open_dialog_count - 1)
        if self._open_dialog_count == 0:
            header = self._header
            if header is not None:
                header.auto_refresh_on = self.live_refresh_on

    # ----- Toast helper -----

    def show_toast(
        self,
        message: str,
        *,
        severity: ToastSeverity = "info",
        duration: float | None = None,
    ) -> None:
        # Record before display so the message survives even when no
        # toast host is mounted (e.g. a chrome-less overlay is active).
        self._recent_messages.append(
            (datetime.now().strftime("%H:%M:%S"), severity, message)
        )
        toast_host = self._toast_host
        if toast_host is not None:
            toast_host.push_toast(
                message, severity=severity, duration=duration
            )

    def action_messages(self) -> None:
        """Open the rolling log of recent toasts (palette entry)."""

        from lumlflow.tui.widgets.dialogs import MessageLogDialog

        self.push_screen(MessageLogDialog(list(self._recent_messages)))

    def _show_first_run_hint_toast(self) -> None:
        self.show_toast(
            "Press [?] for help · [:] for commands",
            severity="info",
            duration=5.0,
        )

    # ----- Clipboard -----

    @property
    def clipboard(self) -> str:
        """App clipboard with an OS-clipboard fallback for Ctrl+V.

        Textual's `Input` binds Ctrl+V to paste from the app-internal
        clipboard, which only ever holds text copied *inside* the app —
        so pasting an API key copied from a browser silently inserted
        nothing. Fall back to the system clipboard (wl-paste / xclip /
        xsel / pbpaste) when the internal one is empty. Terminal
        bracketed paste (Ctrl+Shift+V, right-click) is unaffected.
        """

        if self._clipboard:
            return self._clipboard
        return read_system_clipboard() or ""

    # ----- Yank (OSC52 clipboard) -----

    def yank_to_clipboard(self, value: str, *, label: str | None = None) -> None:
        """Copy `value` to the user's clipboard via OSC52 with a toast.

        Falls back gracefully when the terminal does not support OSC52,
        showing the value so the user can still see what would have
        been copied.
        """

        result = osc52_copy(value)
        if result.ok:
            shown = (
                f"Copied {label} to clipboard."
                if label
                else "Copied to clipboard."
            )
            self.show_toast(
                f"{shown}  {value}",
                severity="success",
                duration=2.0,
            )
        else:
            reason = result.reason or "clipboard unavailable"
            self.show_toast(
                f"Could not copy ({reason}). Value: {value}",
                severity="warning",
                duration=4.0,
            )

    # ----- Selection count surface -----

    def set_selection_count(self, count: int) -> None:
        header = self._header
        if header is not None:
            header.selection_count = count

    def set_loading(self, loading: bool) -> None:
        self._loading_state = loading
        header = self._header
        if header is not None:
            header.loading = loading

    # ----- Cross-screen experiment selection -----

    def toggle_experiment_selection(
        self, experiment: ExperimentDetails
    ) -> bool:
        """Toggle an experiment's membership in the comparison selection.

        Returns the new membership state (`True` if the experiment is
        now selected, `False` if it was removed). The selection survives
        navigation so the user can gather experiments across groups.
        """

        if experiment.id in self._selected_experiments:
            del self._selected_experiments[experiment.id]
            selected = False
        else:
            self._selected_experiments[experiment.id] = experiment
            selected = True
        self.set_selection_count(len(self._selected_experiments))
        return selected

    def is_experiment_selected(self, experiment_id: str) -> bool:
        return experiment_id in self._selected_experiments

    @property
    def selected_experiment_ids(self) -> list[str]:
        return list(self._selected_experiments.keys())

    @property
    def selected_experiments(self) -> dict[str, ExperimentDetails]:
        return dict(self._selected_experiments)

    def clear_experiment_selection(self) -> None:
        self._selected_experiments.clear()
        self.set_selection_count(0)

    # ----- Global actions -----

    def action_show_help(self) -> None:
        """Open the searchable help cheat-sheet derived from the keymap.

        The active screen's scopes are passed along so the sheet can
        lead with an "Available here" section — the direct answer to
        "what can I press right now".
        """

        if self._is_overlay_active(HelpCheatsheet, CommandPalette):
            return
        screen = self.screen
        scopes = (
            screen.footer_scopes()
            if isinstance(screen, BaseScreen)
            else ("global",)
        )
        self.push_screen(HelpCheatsheet(self.keymap, active_scopes=scopes))

    def action_show_palette(self) -> None:
        """Open the fuzzy command palette.

        The palette merges:
        - every registered command (with its binding shown), and
        - jump-to entries (screens that are always reachable + entities
          looked up via the facade as the user types).
        """

        if self._is_overlay_active(HelpCheatsheet, CommandPalette):
            return
        extra_entries = self._build_palette_jump_to_entries()
        palette = CommandPalette(
            registry=self.keymap,
            command_runner=self._invoke_command,
            extra_entries=extra_entries,
        )
        self.push_screen(palette)

    def _is_overlay_active(self, *types: type) -> bool:
        return isinstance(self.screen, tuple(types))

    def _build_palette_jump_to_entries(self) -> list[PaletteEntry]:
        """Return jump-to entries the palette shows alongside commands.

        The home screen is always reachable; richer jump-to (e.g. by
        group/experiment name via the facade) is left to the screen
        that drives the palette so the app shell stays handler-free.
        """

        entries: list[PaletteEntry] = [
            PaletteEntry(
                label="Groups (home)",
                description="Pop back to the home / Groups screen",
                kind="screen",
                invoke=self._jump_home,
                extra_search="navigation home groups",
            )
        ]
        # Screens may contribute their own jump-to entries via a
        # `palette_entries()` method on the active BaseScreen — this is
        # how the experiments / experiment-detail screens surface their
        # entities to the palette without the app shell needing to know
        # their schemas.
        screen = self.screen
        getter = getattr(screen, "palette_entries", None)
        if callable(getter):
            try:
                contributed = list(getter())
            except Exception:
                contributed = []
            entries.extend(contributed)
        return entries

    def _jump_home(self) -> None:
        """Pop back to the home screen (the bottom of the stack)."""

        # Don't pop past the root — Textual keeps a default screen at
        # the bottom of the stack and popping it would crash.
        self._clear_forward_history()
        while len(self.screen_stack) > 2:
            self.pop_screen()
        # The bottom of the stack is the home screen we pushed on
        # mount; nothing to do once we are there.

    def _invoke_command(self, command: Command) -> None:
        """Run the action attached to a `Command`.

        The palette dismisses itself before calling this; we map the
        command id back to its action and dispatch. Palette-only ids
        get special handling here.
        """

        # Palette-only / app-level actions.
        if command.id == "navigation.home":
            self._jump_home()
            return
        if command.id == "navigation.up":
            self.action_navigate_up()
            return
        if command.id == "selection.select_all":
            self._dispatch_screen_action(
                "select_all_visible",
                fallback_message="No selection target on this screen.",
            )
            return
        if command.id == "selection.clear":
            count = len(self._selected_experiments)
            self.clear_experiment_selection()
            if count:
                self.show_toast(
                    f"Cleared {count} selected.", severity="info", duration=1.5
                )
            return
        if command.id.startswith("refresh.interval_"):
            self.set_refresh_interval(
                float(command.id.rsplit("_", 1)[1])
            )
            return

        # For every other command we hand off to the action method on
        # the focused screen (if it exists) or fall back to the app.
        # Try both the namespaced action name (e.g. action_list_edit)
        # and the un-namespaced name (e.g. action_edit_focused) since
        # screens register short-name actions whose key bindings the
        # registry exposes with a namespace (e.g. list.edit → action_edit).
        candidate_names = self._candidate_action_names(command.id)
        target = self.screen
        for action_name in candidate_names:
            if hasattr(target, action_name):
                try:
                    getattr(target, action_name)()
                    return
                except Exception as exc:  # pragma: no cover - defensive
                    self.show_toast(
                        f"Could not run {command.label}: {exc}",
                        severity="error",
                    )
                    return
        for action_name in candidate_names:
            if hasattr(self, action_name):
                try:
                    getattr(self, action_name)()
                    return
                except Exception as exc:  # pragma: no cover - defensive
                    self.show_toast(
                        f"Could not run {command.label}: {exc}",
                        severity="error",
                    )
                    return
        self.show_toast(
            f"{command.label} is not available here.",
            severity="warning",
            duration=2.0,
        )

    @staticmethod
    def _candidate_action_names(command_id: str) -> tuple[str, ...]:
        """Return action method names to try for the given command id.

        Commands are registered as `scope.verb` (e.g. `global.toggle_theme`,
        `list.edit`); the screen / app action methods are typically named
        with just the verb (`action_toggle_theme`, `action_edit_focused`).
        We try both forms so the palette can dispatch to either style of
        action method without each screen having to register both names.
        """

        full = "action_" + command_id.replace(".", "_")
        candidates: list[str] = [full]
        if "." in command_id:
            _scope, verb = command_id.split(".", 1)
            short = "action_" + verb.replace(".", "_")
            if short != full:
                candidates.append(short)
            # For list-scope verbs like `list.edit`, screens often name
            # their actions with a `_focused` suffix (e.g. `edit_focused`,
            # `delete_focused`) because they operate on the focused row.
            with_suffix = f"action_{verb}_focused"
            if with_suffix not in candidates:
                candidates.append(with_suffix)
        return tuple(candidates)

    def _dispatch_screen_action(
        self,
        method: str,
        *,
        fallback_message: str,
    ) -> None:
        target = self.screen
        fn = getattr(target, method, None)
        if not callable(fn):
            self.show_toast(fallback_message, severity="warning", duration=2.0)
            return
        try:
            fn()
        except Exception as exc:  # pragma: no cover - defensive
            self.show_toast(
                f"Could not run: {exc}", severity="error"
            )

    def _go_back(self) -> bool:
        """Pop one screen, recording it so `Ctrl+→` can return to it.

        Textual keeps an always-present `_default` blank screen at the
        bottom of `screen_stack`, so a stack of `[_default, Home]` has
        length 2. Only pop when there is a child screen *above* home —
        otherwise Esc/`q` would reveal the blank default screen.
        Returns ``True`` when a screen was actually popped.

        The popped screen is *installed* before the pop: Textual removes
        an uninstalled screen as soon as it leaves the stack (closing its
        message pump), and re-pushing a removed screen leaves a dead
        screen on top of the stack that swallows every key — the app
        appears frozen. Installing keeps it suspended-but-alive until
        Forward consumes it or a fresh drill-in clears the history.
        """

        if len(self.screen_stack) <= 2:
            return False
        current = self.screen
        if isinstance(current, BaseScreen):
            try:
                self.install_screen(current, name=f"__forward-{id(current)}")
            except ScreenError:
                pass
        self.pop_screen()
        if isinstance(current, BaseScreen):
            self._forward_stack.append(current)
        return True

    def _clear_forward_history(self) -> None:
        """Drop the forward history, releasing the screens it kept alive."""

        for screen in self._forward_stack:
            try:
                self.uninstall_screen(screen)
            except ScreenError:
                pass
            if screen.is_running:
                screen.remove()
        self._forward_stack.clear()

    async def action_back(self) -> None:
        self._go_back()
        # On home there is nothing to pop: stay put rather than exit on Esc.

    def action_back_or_quit(self) -> None:
        """`q`: back on a child screen; on home, quit after a re-press.

        Users of htop / lazygit expect `q` at the top level to exit.
        A single accidental press must not kill the session, so the
        first `q` on home arms a short confirmation window instead.
        """

        if self._go_back():
            self._quit_armed = False
            return
        if self._quit_armed:
            self._quit_armed = False
            self.call_later(self.action_quit)
            return
        self._quit_armed = True
        self.show_toast(
            "Press q again to quit.", severity="info", duration=2.0
        )
        self.set_timer(2.0, self._disarm_quit)

    def _disarm_quit(self) -> None:
        self._quit_armed = False

    def action_forward(self) -> None:
        """Re-push the screen a previous Back navigated away from.

        Mirror of `_go_back`; no-op when the forward history is empty.
        The `_navigating_forward` guard stops the re-push from clearing
        the stack it is consuming. The screen was kept installed while
        it sat in the forward history; uninstall before re-pushing so a
        later normal Back can dispose of it.
        """

        if not self._forward_stack:
            return
        screen = self._forward_stack.pop()
        try:
            self.uninstall_screen(screen)
        except ScreenError:
            pass
        if not screen.is_running:
            # The screen died despite being installed (e.g. a shutdown
            # race) — pushing a dead screen would freeze the app.
            return
        self._navigating_forward = True
        try:
            self.push_screen(screen)
        finally:
            self._navigating_forward = False

    def action_navigate_up(self) -> None:
        """Pop one screen — palette mirror of Esc/`q`/`Ctrl+←`.

        Discoverable through `:` so users searching for "back" or
        "up" surface a real entry instead of relying on muscle memory
        for a key binding (no-hidden-shortcuts).
        """

        self._go_back()

    def on_breadcrumb_segment_clicked(
        self, event: Breadcrumb.SegmentClicked
    ) -> None:
        """Navigate to the clicked breadcrumb segment.

        The breadcrumb encodes the parent chain leaf-last. Clicking a
        non-leaf segment pops screens until the clicked label is the
        active screen's leaf — or until home, whichever comes first.
        Clicking the leaf is a no-op (the user is already there).
        """

        active = self.screen
        if isinstance(active, BaseScreen):
            segments = active.breadcrumb_segments()
            # Leaf == current screen; clicking it is a no-op.
            if event.index == len(segments) - 1:
                return
        target_label = event.segment.label
        # An explicit jump up the breadcrumb is a fresh navigation, so
        # the forward history no longer applies.
        self._clear_forward_history()
        # Pop until either the target is the leaf of the active screen
        # or we have reached home. Bound the loop by the stack size so
        # a mismatched label can't loop forever.
        guard = len(self.screen_stack)
        while guard > 0 and len(self.screen_stack) > 2:
            current = self.screen
            if isinstance(current, BaseScreen):
                segs = current.breadcrumb_segments()
                if segs and segs[-1].label == target_label:
                    return
            self.pop_screen()
            guard -= 1

    def action_refresh_now(self) -> None:
        # A manual refresh fires one cycle regardless of the live-refresh
        # toggle — the user explicitly asked for fresh data.
        self._refresh_scheduler.refresh_now()

    def set_refresh_interval(self, seconds: float) -> None:
        """Change the live-refresh cadence at runtime (palette presets)."""

        self.refresh_interval = seconds
        self._refresh_scheduler.set_interval(seconds)
        suffix = "" if self.live_refresh_on else " (auto-refresh is off — R to enable)"
        self.show_toast(
            f"Auto-refresh every {seconds:g}s.{suffix}",
            severity="info",
            duration=2.0,
        )

    def action_toggle_auto_refresh(self) -> None:
        self.live_refresh_on = not self.live_refresh_on
        header = self._header
        if header is not None:
            header.auto_refresh_on = (
                self.live_refresh_on and not self.is_refresh_paused
            )
        self.show_toast(
            f"Auto-refresh {'on' if self.live_refresh_on else 'off'}.",
            severity="info",
            duration=1.5,
        )

    def action_toggle_theme(self) -> None:
        current = self.theme
        new_name = (
            self.theme_bundle.light.name
            if current == self.theme_bundle.dark.name
            else self.theme_bundle.dark.name
        )
        self.theme = new_name

    def action_cycle_focus(self) -> None:
        """Cycle focus between the panes declared by the active screen.

        When the screen registers `focusable_panes` (e.g. trace detail's
        span tree + annotations), `Tab` cycles between those panes so
        the focused panel frame moves with the keystroke. Otherwise we
        fall back to Textual's standard descendant focus traversal.
        """

        screen = self.screen
        if isinstance(screen, BaseScreen) and screen.cycle_focus_pane(
            reverse=False
        ):
            return
        self.action_focus_next()

    def action_cycle_focus_back(self) -> None:
        screen = self.screen
        if isinstance(screen, BaseScreen) and screen.cycle_focus_pane(
            reverse=True
        ):
            return
        self.action_focus_previous()

    # ----- Run-and-attach quit lifecycle -----

    @property
    def has_active_run(self) -> bool:
        """True iff a run-attach screen owns a child process that is still alive."""

        run_screen = self._active_run_screen
        if run_screen is None:
            return False
        run = run_screen._run
        if run is None:
            return False
        return run.is_running

    async def action_quit(self) -> None:  # type: ignore[override]
        """Confirm-quit when a run is active.

        SPEC: "Ctrl-C is handled so it targets the run, not a half-broken
        teardown of the UI" — when the user hits Ctrl-C while a script is
        running, the RunAttachScreen's binding takes precedence and
        targets the child. This action is the fallback / palette path:
        we ask whether to terminate or detach the child before quitting.
        """

        if self._quit_in_progress:
            return
        if not self.has_active_run:
            await super().action_quit()
            return
        self._quit_in_progress = True
        dialog = ConfirmDialog(
            title="A run is still active",
            message=(
                "The training script launched with this TUI is still "
                "running. Quitting will leave it running in the "
                "background; cancel to keep watching it, or stop it "
                "explicitly with Ctrl-C / 's' on the run screen first."
            ),
            confirm_label="Quit (detach)",
            cancel_label="Cancel",
        )

        def _after(confirmed: bool | None) -> None:
            self._quit_in_progress = False
            if confirmed:
                # Detach: leave the child alone and exit the TUI.
                self.exit()

        self.push_screen(dialog, callback=_after)


def _is_text_input(widget: Widget) -> bool:
    """Return True if the focused widget is a text input."""

    if isinstance(widget, Input):
        return True
    # `TextArea` is the multi-line input — also pass through.
    try:
        from textual.widgets import TextArea  # type: ignore

        if isinstance(widget, TextArea):
            return True
    except ImportError:  # pragma: no cover
        pass
    return False


__all__: tuple[str, ...] = ("LumlflowApp",)
