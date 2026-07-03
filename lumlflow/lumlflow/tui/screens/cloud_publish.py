"""Cloud publish flow — auth → org → orbit → collection → upload.

A guided modal flow backed by `AuthHandler`, `LumlHandler` and
`ArtifactHandler` via the `DataFacade`. The screen presents one *step*
at a time inside a fixed two-panel layout: a status sidebar that lists
the chosen target so far (so the user can always see what they are
publishing where), and a body that swaps between dialogs as the user
progresses.

The screen runs in one of two modes:

- **experiment mode** (constructed with `experiment_id`): publishes a
  tracked experiment / its linked models — reached with `p` from the
  experiments list or the experiment detail screen.
- **manual mode** (no `experiment_id`): uploads an arbitrary artifact
  file chosen from disk — reached with `u` from anywhere. The upload
  step swaps the type/embed options for a file-path field, mirroring
  the web UI's "add artifact" dialog.

Steps (driven by `_step`):

1. ``auth``         — prompt for / validate an API key (`AuthHandler`).
2. ``org``          — pick an organization (`LumlHandler`).
3. ``orbit``        — pick an orbit inside that organization.
4. ``collection``   — pick a collection inside that orbit.
5. ``upload``       — choose upload type / artifact metadata and start
   the upload via `ArtifactHandler`. The progress is read from the
   shared `ProgressStore` keyed by a job id, exactly the way the web
   SSE endpoint does.
6. ``done``         — terminal success or error summary.

Every facade call runs on a Textual worker thread; the event loop is
never blocked. Errors come back as `Result.failure(...)` and are
surfaced in-place (inline at the field for validation errors, as a
toast plus the body's status line for unreachable / unauthorized
errors). Cloud features degrade gracefully: a failure here does not
break the rest of the TUI.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import (
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    RadioButton,
    RadioSet,
    Static,
)

from lumlflow.schemas.luml import (
    ArtifactIn,
    Collection,
    Orbit,
    Organization,
    UploadArtifactForm,
    UploadFileForm,
    UploadModelForm,
    UploadType,
)
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment
from lumlflow.tui.widgets.path_suggester import PathSuggester

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp


# Step identifiers — drive which body the screen renders. Kept as a
# plain Literal so refactors are obvious if a step is renamed.
_Step = Literal[
    "auth",
    "org",
    "orbit",
    "collection",
    "upload",
    "progress",
    "done",
]


_STEP_ORDER: tuple[_Step, ...] = (
    "auth",
    "org",
    "orbit",
    "collection",
    "upload",
    "progress",
    "done",
)


_STEP_LABELS: dict[_Step, str] = {
    "auth": "API key",
    "org": "Organization",
    "orbit": "Orbit",
    "collection": "Collection",
    "upload": "Upload",
    "progress": "Uploading",
    "done": "Done",
}


# Progress poll cadence — fast enough that the bar moves smoothly, slow
# enough not to drown the worker pool. The chunked-upload progress
# handler updates the store on every chunk, so a 10Hz read is plenty.
_PROGRESS_POLL_SECONDS = 0.1


@dataclass
class _PublishContext:
    """Selections gathered as the user walks the flow.

    None until the corresponding step is completed. The terminal state
    has all required fields set (`organization`, `orbit`, `collection`,
    `upload_type`, `artifact_name`).

    `experiment_id` is None in *manual* mode — the flow then uploads a
    user-chosen file from disk (`file_path`) instead of anything
    derived from a tracked experiment. `model_id` is set in *model*
    mode — publishing one specific linked model of the experiment.
    """

    experiment_id: str | None
    experiment_name: str
    file_path: str | None = None
    model_id: str | None = None
    model_name: str | None = None
    organization: Organization | None = None
    orbit: Orbit | None = None
    collection: Collection | None = None
    upload_type: UploadType = UploadType.AUTO
    embed_experiment: bool = False
    artifact_name: str | None = None
    artifact_description: str | None = None
    artifact_tags: list[str] = field(default_factory=list)
    job_id: str | None = None
    final_message: str | None = None
    final_success: bool | None = None


class CloudPublishScreen(BaseScreen):
    """Guided modal flow for publishing an experiment to the LUML cloud.

    The screen is structured as a tiny state machine — `_step` selects
    which body widget is mounted. Each step lazy-loads its data (orgs
    → orbits → collections) so the user never waits on a step they have
    not reached. On the upload step a background worker drives the
    `ArtifactHandler.upload_artifact` call while a polling timer reads
    the `ProgressStore` to refresh a `ProgressBar`.
    """

    DEFAULT_CSS = """
    CloudPublishScreen {
        layout: vertical;
    }
    CloudPublishScreen #publish-body {
        height: 1fr;
        layout: horizontal;
    }
    CloudPublishScreen #publish-sidebar {
        width: 32;
        border-right: solid $panel;
        padding: 1 1;
    }
    CloudPublishScreen #publish-main {
        width: 1fr;
        padding: 1 2;
        layout: vertical;
    }
    CloudPublishScreen .step-title {
        text-style: bold;
        padding-bottom: 1;
    }
    CloudPublishScreen .field-label {
        padding-top: 1;
    }
    CloudPublishScreen #publish-error {
        color: $error;
        padding-top: 1;
        height: auto;
    }
    CloudPublishScreen #publish-error.-empty {
        display: none;
    }
    CloudPublishScreen #publish-action-hint {
        color: $text-muted;
        padding-top: 1;
    }
    CloudPublishScreen .pick-list {
        height: 1fr;
        border: solid $panel;
    }
    CloudPublishScreen #publish-embed-row {
        height: auto;
        display: none;
    }
    CloudPublishScreen #publish-embed-radio {
        height: auto;
    }
    CloudPublishScreen #publish-progress {
        margin-top: 1;
        width: 1fr;
    }
    CloudPublishScreen .step-sidebar-row {
        height: 1;
    }
    CloudPublishScreen .step-sidebar-active {
        text-style: bold;
        color: $accent;
    }
    CloudPublishScreen .step-sidebar-done {
        color: $success;
    }
    CloudPublishScreen .step-sidebar-pending {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "back_or_cancel", "Back", show=False),
        Binding("ctrl+c", "back_or_cancel", "Cancel", show=False),
    ]

    breadcrumb_label = "Publish to cloud"

    @property
    def _is_manual(self) -> bool:
        """True when uploading a user-chosen file, not an experiment."""

        return self._ctx.experiment_id is None

    @property
    def _is_model(self) -> bool:
        """True when publishing one specific linked model."""

        return (
            self._ctx.experiment_id is not None
            and self._ctx.model_id is not None
        )

    def __init__(
        self,
        *,
        facade: DataFacade | None,
        experiment_id: str | None = None,
        experiment_name: str | None = None,
        model_id: str | None = None,
        model_name: str | None = None,
        breadcrumb_prefix: tuple[BreadcrumbSegment, ...] = (),
        id: str | None = None,
        # Test seam: deterministic job id so progress lookups in tests
        # can hit a known key. Production code generates a uuid4 hex.
        job_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._ctx = _PublishContext(
            experiment_id=experiment_id,
            experiment_name=experiment_name or "",
            model_id=model_id,
            model_name=model_name,
        )
        self._breadcrumb_prefix = breadcrumb_prefix
        self._step: _Step = "auth"
        self._job_id_factory = job_id_factory
        # Cached fetched lists (only what the current step needs).
        self._orgs: list[Organization] = []
        self._orbits: list[Orbit] = []
        self._collections: list[Collection] = []
        # True once the current step's body is fully mounted. Fetch
        # callbacks arrive on the app's message pump while the body
        # swap runs on the screen's, so a result can land before,
        # during, or after the swap; this flag makes exactly one
        # writer populate the picker in every interleaving.
        self._body_ready: bool = False
        # Active timer for progress polling — cancelled on teardown.
        self._poll_timer: Any = None

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="publish-body"):
            with Vertical(id="publish-sidebar"):
                yield Static(
                    self._sidebar_text(),
                    id="publish-sidebar-text",
                )
            with Vertical(id="publish-main"):
                # The main pane is rebuilt every time the step changes,
                # so we don't compose anything here — `_render_step()`
                # mounts widgets directly.
                yield Container(id="publish-step-container")

    def on_mount(self) -> None:
        # Decide which step we land on by asking the auth handler whether
        # there is already a stored API key. Going via the facade keeps
        # the worker-thread offload and `Result` mapping consistent.
        self._fetch_initial_auth_state()

    def on_unmount(self) -> None:
        if self._poll_timer is not None:
            try:
                self._poll_timer.stop()
            except Exception:
                pass

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        return (
            *self._breadcrumb_prefix,
            BreadcrumbSegment("Upload" if self._is_manual else "Publish"),
        )

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global",)

    # ----- facade plumbing -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        return getattr(self.app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- sidebar -----

    def _sidebar_text(self) -> Text:
        """Build the always-visible target summary on the left rail.

        Lists every step with a status marker (●/○) so the user can
        see at a glance what is still pending and what has been chosen.
        """

        text = Text()
        if self._is_manual:
            text.append("Uploading file\n", style="dim")
            file_label = (
                Path(self._ctx.file_path).name
                if self._ctx.file_path
                else "(choose a file)"
            )
            text.append(file_label, style="bold")
        elif self._is_model:
            text.append("Publishing model\n", style="dim")
            text.append(
                self._ctx.model_name or self._ctx.model_id or "",
                style="bold",
            )
        else:
            text.append("Publishing\n", style="dim")
            text.append(self._ctx.experiment_name, style="bold")
        text.append("\n\n")
        # Per-step progress markers. The current step is bold; completed
        # steps show their selection on the next line. Plain colour
        # names (not CSS variables) so the rich `Text` renderer accepts
        # them — `Static.update(Text(...))` does not run CSS expansion.
        for step in _STEP_ORDER:
            if step == "done":
                continue
            label = _STEP_LABELS[step]
            done = self._step_value(step)
            if step == self._step:
                text.append("● ", style="bold cyan")
                text.append(label, style="bold cyan")
            elif done is not None:
                text.append("✓ ", style="green")
                text.append(label, style="green")
            else:
                text.append("○ ", style="dim")
                text.append(label, style="dim")
            text.append("\n")
            if done is not None and step != self._step:
                text.append(f"   {done}\n", style="dim")
        return text

    def _step_value(self, step: _Step) -> str | None:
        """Human-readable selection for a completed step, if any."""

        if step == "auth":
            # The auth step has no displayable artefact — once we leave
            # it we treat it as done.
            past_auth = ("org", "orbit", "collection", "upload", "progress", "done")
            if self._step in past_auth:
                return "stored"
            return None
        if step == "org":
            return self._ctx.organization.name if self._ctx.organization else None
        if step == "orbit":
            return self._ctx.orbit.name if self._ctx.orbit else None
        if step == "collection":
            return self._ctx.collection.name if self._ctx.collection else None
        if step == "upload":
            if self._step in ("progress", "done"):
                if self._is_manual:
                    return (
                        Path(self._ctx.file_path).name
                        if self._ctx.file_path
                        else "file"
                    )
                if self._is_model:
                    return self._ctx.model_name or "model"
                return self._ctx.upload_type.value
            return None
        if step == "progress":
            if self._step == "done":
                return "complete" if self._ctx.final_success else "error"
            return None
        return None

    def _refresh_sidebar(self) -> None:
        try:
            self.query_one("#publish-sidebar-text", Static).update(
                self._sidebar_text()
            )
        except Exception:
            pass

    # ----- step rendering -----

    def _set_step(self, step: _Step) -> None:
        self._step = step
        self._refresh_sidebar()
        self._render_step()

    def _render_step(self) -> None:
        """Replace the body widgets with the ones for `self._step`.

        `Widget.remove()` schedules removal asynchronously, so a naive
        loop followed by an immediate `mount(...)` collides on shared
        `id`s (Textual rejects duplicate ids in the same parent).
        `Container.remove_children` returns an `AwaitRemove` we await
        via `call_later` so the new widgets only mount after the old
        ones are gone.
        """

        try:
            container = self.query_one("#publish-step-container", Container)
        except Exception:
            return
        # Cancel any progress poller when leaving the progress step.
        if self._step != "progress" and self._poll_timer is not None:
            try:
                self._poll_timer.stop()
            except Exception:
                pass
            self._poll_timer = None
        # The new body is not queryable until the swap completes; any
        # fetch result arriving in between is cached and re-applied by
        # the swap instead of being rendered into a half-built body.
        self._body_ready = False
        self.call_later(self._swap_step_children, container)

    async def _swap_step_children(self, container: Container) -> None:
        """Await removal of the old body, then mount the new one."""

        await container.remove_children()
        body = self._build_step_body()
        await container.mount(*body)
        # A fetch result that landed before this point was only cached
        # (its populate call was gated on `_body_ready`); render it now
        # so the fresh picker is never silently empty.
        self._body_ready = True
        self._apply_cached_step_data()
        # Focus the most useful widget on the new step.
        self.call_after_refresh(self._focus_default_widget)

    def _apply_cached_step_data(self) -> None:
        if self._step == "org" and self._orgs:
            self._populate_org_list()
        elif self._step == "orbit" and self._orbits:
            self._populate_orbit_list()
        elif self._step == "collection" and self._collections:
            self._populate_collection_list()

    def _build_step_body(self) -> list[Any]:
        builders: dict[_Step, Callable[[], list[Any]]] = {
            "auth": self._build_auth_body,
            "org": self._build_org_body,
            "orbit": self._build_orbit_body,
            "collection": self._build_collection_body,
            "upload": self._build_upload_body,
            "progress": self._build_progress_body,
            "done": self._build_done_body,
        }
        return builders[self._step]()

    def _focus_default_widget(self) -> None:
        try:
            if self._step == "auth":
                self.query_one("#publish-api-key-input", Input).focus()
            elif self._step == "upload" and self._is_manual:
                self.query_one("#publish-file-path-input", Input).focus()
            elif self._step == "upload" and self._is_model:
                self.query_one("#publish-embed-radio", RadioSet).focus()
            elif self._step == "upload":
                self.query_one("#publish-artifact-name-input", Input).focus()
            elif self._step in ("org", "orbit", "collection"):
                view = self.query_one(f"#publish-{self._step}-list", ListView)
                view.focus()
        except Exception:
            pass

    # ----- step: auth -----

    def _build_auth_body(self) -> list[Any]:
        return [
            Static("Step 1 · LUML API key", classes="step-title"),
            Label(
                "Validated against LUML and stored locally.",
                id="publish-auth-help",
            ),
            Label("API key", classes="field-label"),
            Input(
                placeholder="dfs_…",
                password=True,
                id="publish-api-key-input",
            ),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[Enter] Validate · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "publish-api-key-input":
            self._submit_api_key(event.input.value)

    def _submit_api_key(self, value: str) -> None:
        key = value.strip()
        if not key:
            self._set_error("API key is required.")
            return
        self._set_error(None)
        self._run_set_api_key(key)

    @work(thread=True, group="publish-auth")
    def _run_set_api_key(self, api_key: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.set_api_key(api_key)
        self.app.call_from_thread(self._on_api_key_result, result)

    def _on_api_key_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            message = err.message if err else "Failed to validate API key"
            if err and err.code == 401:
                self._set_error(f"Invalid API key — {message}")
            else:
                # 502 and friends carry a complete, self-describing
                # message from the handler (URL + underlying error).
                self._set_error(message)
            return
        self._lumlflow_app.show_toast(
            "API key validated.", severity="success", duration=1.5
        )
        self._set_step("org")
        self._fetch_orgs()

    # ----- initial auth state -----

    @work(thread=True, group="publish-auth")
    def _fetch_initial_auth_state(self) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.has_api_key()
        self.app.call_from_thread(self._on_initial_auth_state, result)

    def _on_initial_auth_state(self, result: Result[Any]) -> None:
        # Mount the initial step body — even on failure we show the
        # auth step (the user can always set a new key from there).
        if result.ok and result.unwrap():
            self._set_step("org")
            self._fetch_orgs()
        else:
            self._render_step()

    # ----- step: organization -----

    def _build_org_body(self) -> list[Any]:
        return [
            Static("Step 2 · Organization", classes="step-title"),
            Label(
                "Pick the organization that will own this artifact.",
                id="publish-org-help",
            ),
            ListView(id="publish-org-list", classes="pick-list"),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[↑/↓] Choose · [Enter] Select · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    @work(thread=True, group="publish-org")
    def _fetch_orgs(self) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.list_organizations()
        self.app.call_from_thread(self._on_orgs_result, result)

    def _on_orgs_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            message = err.message if err else "Failed to list organizations"
            # 401 → gate failure; bounce back to auth so the user can
            # re-enter the key without losing the rest of the screen.
            if err and err.code == 401:
                self._lumlflow_app.show_toast(
                    "API key required.",
                    severity="warning",
                )
                # Set the state first; defer the error display so it
                # lands after the new auth body has been mounted.
                self._set_step("auth")
                self.call_after_refresh(self._set_error, message)
            else:
                self._set_error(message)
            return
        self._orgs = list(result.unwrap() or [])
        # Only render when the step body is fully mounted — otherwise
        # the swap re-applies this cache once mounting completes.
        if self._body_ready:
            self._populate_org_list()

    def _populate_org_list(self) -> None:
        """Render `_orgs` into the picker (no-op until it is mounted)."""

        try:
            view = self.query_one("#publish-org-list", ListView)
        except Exception:
            return
        view.clear()
        if not self._orgs:
            view.append(
                ListItem(Static("(no organizations)"), id="publish-org-empty")
            )
            return
        for org in self._orgs:
            view.append(
                ListItem(
                    Static(org.name),
                    id=f"publish-org-{_safe_id(org.id)}",
                )
            )
        view.index = 0

    # ----- step: orbit -----

    def _build_orbit_body(self) -> list[Any]:
        return [
            Static("Step 3 · Orbit", classes="step-title"),
            Label(
                "Pick the orbit (workspace).",
                id="publish-orbit-help",
            ),
            ListView(id="publish-orbit-list", classes="pick-list"),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[↑/↓] Choose · [Enter] Select · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    @work(thread=True, group="publish-orbit")
    def _fetch_orbits(self) -> None:
        facade = self.facade
        if facade is None or self._ctx.organization is None:
            return
        result = facade.list_orbits(self._ctx.organization.id)
        self.app.call_from_thread(self._on_orbits_result, result)

    def _on_orbits_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            message = err.message if err else "Failed to list orbits"
            self._set_error(message)
            return
        self._orbits = list(result.unwrap() or [])
        # Only render when the step body is fully mounted — otherwise
        # the swap re-applies this cache once mounting completes.
        if self._body_ready:
            self._populate_orbit_list()

    def _populate_orbit_list(self) -> None:
        """Render `_orbits` into the picker (no-op until it is mounted)."""

        try:
            view = self.query_one("#publish-orbit-list", ListView)
        except Exception:
            return
        view.clear()
        if not self._orbits:
            view.append(
                ListItem(Static("(no orbits)"), id="publish-orbit-empty")
            )
            return
        for orbit in self._orbits:
            view.append(
                ListItem(
                    Static(orbit.name),
                    id=f"publish-orbit-{_safe_id(orbit.id)}",
                )
            )
        view.index = 0

    # ----- step: collection -----

    def _build_collection_body(self) -> list[Any]:
        return [
            Static("Step 4 · Collection", classes="step-title"),
            Label(
                "Pick the destination collection.",
                id="publish-collection-help",
            ),
            ListView(id="publish-collection-list", classes="pick-list"),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[↑/↓] Choose · [Enter] Select · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    @work(thread=True, group="publish-collection")
    def _fetch_collections(self) -> None:
        facade = self.facade
        if (
            facade is None
            or self._ctx.organization is None
            or self._ctx.orbit is None
        ):
            return
        result = facade.list_collections(
            self._ctx.organization.id, self._ctx.orbit.id
        )
        self.app.call_from_thread(self._on_collections_result, result)

    def _on_collections_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            message = err.message if err else "Failed to list collections"
            self._set_error(message)
            return
        page = result.unwrap()
        self._collections = list(page.items if page is not None else [])
        # Only render when the step body is fully mounted — otherwise
        # the swap re-applies this cache once mounting completes.
        if self._body_ready:
            self._populate_collection_list()

    def _populate_collection_list(self) -> None:
        """Render `_collections` into the picker (no-op until mounted)."""

        try:
            view = self.query_one("#publish-collection-list", ListView)
        except Exception:
            return
        view.clear()
        if not self._collections:
            view.append(
                ListItem(
                    Static("(no collections)"),
                    id="publish-collection-empty",
                )
            )
            return
        for col in self._collections:
            view.append(
                ListItem(
                    Static(f"{col.name}  ·  {col.type}"),
                    id=f"publish-collection-{_safe_id(col.id)}",
                )
            )
        view.index = 0

    # ----- upload-type highlight → embed row visibility -----

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "publish-upload-type-list":
            return
        try:
            row = self.query_one("#publish-embed-row", Vertical)
        except Exception:
            return
        # Index 1 is type=model — the only type where embedding is a
        # user decision rather than derived (`auto`) or moot.
        row.display = event.list_view.index == 1

    # ----- ListView selection handler shared by org/orbit/collection -----

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_id = event.list_view.id
        if list_id == "publish-org-list":
            self._select_org_at(event.list_view.index)
        elif list_id == "publish-orbit-list":
            self._select_orbit_at(event.list_view.index)
        elif list_id == "publish-collection-list":
            self._select_collection_at(event.list_view.index)

    def _select_org_at(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(self._orgs)):
            return
        self._ctx.organization = self._orgs[index]
        self._set_step("orbit")
        self._fetch_orbits()

    def _select_orbit_at(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(self._orbits)):
            return
        self._ctx.orbit = self._orbits[index]
        self._set_step("collection")
        self._fetch_collections()

    def _select_collection_at(self, index: int | None) -> None:
        if index is None or not (0 <= index < len(self._collections)):
            return
        self._ctx.collection = self._collections[index]
        self._set_step("upload")

    # ----- step: upload -----

    def _build_upload_body(self) -> list[Any]:
        if self._is_manual:
            return self._build_manual_upload_body()
        if self._is_model:
            return self._build_model_upload_body()
        return [
            Static("Step 5 · Upload options", classes="step-title"),
            Label("Upload type", classes="field-label"),
            ListView(
                ListItem(
                    Static("auto · embed a single model, else models + archive"),
                    id="publish-type-auto",
                ),
                ListItem(
                    Static("model · linked models only"),
                    id="publish-type-model",
                ),
                ListItem(
                    Static("experiment · archive only"),
                    id="publish-type-experiment",
                ),
                id="publish-upload-type-list",
                classes="pick-list",
            ),
            # Embedding is only a real question for type=model — `auto`
            # decides it from the number of linked models (the same
            # logic the web UI uses) and `experiment` never embeds. The
            # row stays hidden until the model type is highlighted.
            Vertical(
                Label(
                    "Embed the experiment inside the model file?",
                    classes="field-label",
                ),
                self._build_embed_radio(),
                id="publish-embed-row",
            ),
            Label("Artifact name (optional)", classes="field-label"),
            Input(
                value=self._ctx.experiment_name,
                placeholder="My artifact",
                id="publish-artifact-name-input",
            ),
            Label("Description (optional)", classes="field-label"),
            Input(
                placeholder="Short summary of this artifact",
                id="publish-artifact-desc-input",
            ),
            Label("Tags (comma separated, optional)", classes="field-label"),
            Input(
                placeholder="prod, baseline",
                id="publish-artifact-tags-input",
            ),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[Tab] Field · [Enter] Start upload · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    @staticmethod
    def _build_embed_radio() -> RadioSet:
        return RadioSet(
            RadioButton("no · model file as-is", value=True),
            RadioButton("yes · bundle the experiment", value=False),
            id="publish-embed-radio",
        )

    def _build_model_upload_body(self) -> list[Any]:
        """Upload form for model mode: one linked model + metadata."""

        return [
            Static(
                f"Step 5 · Publish model · {self._ctx.model_name or ''}",
                classes="step-title",
            ),
            Label(
                "Embed the experiment inside the model file?",
                classes="field-label",
            ),
            self._build_embed_radio(),
            Label("Artifact name (optional)", classes="field-label"),
            Input(
                value=self._ctx.model_name or "",
                placeholder="Defaults to the model name",
                id="publish-artifact-name-input",
            ),
            Label("Description (optional)", classes="field-label"),
            Input(
                placeholder="Short summary of this artifact",
                id="publish-artifact-desc-input",
            ),
            Label("Tags (comma separated, optional)", classes="field-label"),
            Input(
                placeholder="prod, baseline",
                id="publish-artifact-tags-input",
            ),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[Tab] Field · [Enter] Start upload · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    def _build_manual_upload_body(self) -> list[Any]:
        """Upload form for manual mode: a file from disk + metadata."""

        return [
            Static("Step 5 · File & metadata", classes="step-title"),
            Label(
                "Model (.luml/.fnnx/.pyfnx/.dfs), experiment archive, "
                "or dataset (.tar).",
                id="publish-file-help",
            ),
            Label("File path", classes="field-label"),
            Input(
                placeholder="/path/to/model.luml",
                id="publish-file-path-input",
                suggester=PathSuggester(),
            ),
            Label("Artifact name (optional)", classes="field-label"),
            Input(
                placeholder="Defaults to the file name",
                id="publish-artifact-name-input",
            ),
            Label("Description (optional)", classes="field-label"),
            Input(
                placeholder="Short summary of this artifact",
                id="publish-artifact-desc-input",
            ),
            Label("Tags (comma separated, optional)", classes="field-label"),
            Input(
                placeholder="prod, baseline",
                id="publish-artifact-tags-input",
            ),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[Tab] Field · [Enter] Start upload · [Esc] Back",
                id="publish-action-hint",
            ),
        ]

    def _read_upload_form(self) -> bool:
        """Pull values from the upload-step widgets into `_ctx`.

        Returns False (with an inline error) when something invalid was
        entered; True when the context is ready to drive an upload.
        """

        if self._is_manual:
            return self._read_manual_upload_form()
        if self._is_model:
            return self._read_model_upload_form()
        try:
            type_view = self.query_one("#publish-upload-type-list", ListView)
            embed_radio = self.query_one("#publish-embed-radio", RadioSet)
            name_input = self.query_one("#publish-artifact-name-input", Input)
            desc_input = self.query_one("#publish-artifact-desc-input", Input)
            tags_input = self.query_one("#publish-artifact-tags-input", Input)
        except Exception:
            return False
        type_index = type_view.index or 0
        upload_type = (UploadType.AUTO, UploadType.MODEL, UploadType.EXPERIMENT)[
            type_index
        ]
        self._ctx.upload_type = upload_type
        # Embedding is only the user's call for type=model; `auto`
        # derives it from the linked-model count and `experiment`
        # never embeds (mirrors the web UI / ArtifactHandler logic).
        self._ctx.embed_experiment = (
            upload_type == UploadType.MODEL
            and embed_radio.pressed_index == 1
        )
        self._ctx.artifact_name = name_input.value.strip() or None
        self._ctx.artifact_description = desc_input.value.strip() or None
        self._ctx.artifact_tags = [
            t.strip() for t in tags_input.value.split(",") if t.strip()
        ]
        return True

    def _read_model_upload_form(self) -> bool:
        try:
            embed_radio = self.query_one("#publish-embed-radio", RadioSet)
            name_input = self.query_one("#publish-artifact-name-input", Input)
            desc_input = self.query_one("#publish-artifact-desc-input", Input)
            tags_input = self.query_one("#publish-artifact-tags-input", Input)
        except Exception:
            return False
        self._ctx.embed_experiment = embed_radio.pressed_index == 1
        self._ctx.artifact_name = name_input.value.strip() or None
        self._ctx.artifact_description = desc_input.value.strip() or None
        self._ctx.artifact_tags = [
            t.strip() for t in tags_input.value.split(",") if t.strip()
        ]
        return True

    def _read_manual_upload_form(self) -> bool:
        try:
            path_input = self.query_one("#publish-file-path-input", Input)
            name_input = self.query_one("#publish-artifact-name-input", Input)
            desc_input = self.query_one("#publish-artifact-desc-input", Input)
            tags_input = self.query_one("#publish-artifact-tags-input", Input)
        except Exception:
            return False
        raw_path = path_input.value.strip()
        if not raw_path:
            self._set_error("A file path is required.")
            path_input.focus()
            return False
        path = Path(raw_path).expanduser()
        if not path.is_file():
            self._set_error(f"No such file: {path}")
            path_input.focus()
            return False
        self._set_error(None)
        self._ctx.file_path = str(path)
        self._ctx.artifact_name = name_input.value.strip() or None
        self._ctx.artifact_description = desc_input.value.strip() or None
        self._ctx.artifact_tags = [
            t.strip() for t in tags_input.value.split(",") if t.strip()
        ]
        self._refresh_sidebar()
        return True

    # ----- step: progress -----

    def _build_progress_body(self) -> list[Any]:
        return [
            Static("Step 6 · Uploading", classes="step-title"),
            Static("Starting upload…", id="publish-progress-status"),
            ProgressBar(id="publish-progress", total=100, show_eta=False),
            Static("", id="publish-error", classes="-empty"),
            Static(
                "[Esc] Cancel and return",
                id="publish-action-hint",
            ),
        ]

    def _start_upload(self) -> None:
        facade = self.facade
        if facade is None:
            self._set_error("Cloud features are unavailable.")
            return
        ctx = self._ctx
        if (
            ctx.organization is None
            or ctx.orbit is None
            or ctx.collection is None
        ):
            # Defensive — UI flow forbids reaching here without these.
            self._set_error("Target is incomplete.")
            return
        job_id = self._job_id_factory()
        ctx.job_id = job_id
        facade.progress_store.create(job_id)
        artifact = ArtifactIn(
            name=ctx.artifact_name,
            description=ctx.artifact_description,
            tags=ctx.artifact_tags or None,
        )
        if ctx.experiment_id is None:
            if ctx.file_path is None:
                self._set_error("A file path is required.")
                return
            file_form = UploadFileForm(
                file_path=ctx.file_path,
                organization_id=ctx.organization.id,
                orbit_id=ctx.orbit.id,
                collection_id=ctx.collection.id,
                artifact=artifact,
            )
            self._set_step("progress")
            self._run_file_upload(file_form, job_id)
        elif ctx.model_id is not None:
            model_form = UploadModelForm(
                model_id=ctx.model_id,
                experiment_id=ctx.experiment_id,
                embed_experiment=ctx.embed_experiment,
                organization_id=ctx.organization.id,
                orbit_id=ctx.orbit.id,
                collection_id=ctx.collection.id,
                artifact=artifact,
            )
            self._set_step("progress")
            self._run_model_upload(model_form, job_id)
        else:
            form = UploadArtifactForm(
                upload_type=ctx.upload_type,
                embed_experiment=ctx.embed_experiment,
                experiment_id=ctx.experiment_id,
                organization_id=ctx.organization.id,
                orbit_id=ctx.orbit.id,
                collection_id=ctx.collection.id,
                artifact=artifact,
            )
            self._set_step("progress")
            self._run_upload(form, job_id)
        # Poll the shared progress store on a timer; the worker runs
        # the upload synchronously and we read its progress out-of-band.
        self._poll_timer = self.set_interval(
            _PROGRESS_POLL_SECONDS, self._poll_progress
        )

    @work(thread=True, group="publish-upload")
    def _run_upload(self, form: UploadArtifactForm, job_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.upload_artifact(form, job_id)
        self.app.call_from_thread(self._on_upload_done, result, job_id)

    @work(thread=True, group="publish-upload")
    def _run_file_upload(self, form: UploadFileForm, job_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.upload_file_artifact(form, job_id)
        self.app.call_from_thread(self._on_upload_done, result, job_id)

    @work(thread=True, group="publish-upload")
    def _run_model_upload(self, form: UploadModelForm, job_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.upload_model_artifact(form, job_id)
        self.app.call_from_thread(self._on_upload_done, result, job_id)

    def _on_upload_done(self, result: Result[Any], _job_id: str) -> None:
        # The artifact handler swallows its own exceptions and writes
        # the failure into the progress store, so `result.ok` will be
        # True even on upload errors; we read the final state from the
        # store. Only an unexpected facade-level failure (e.g. tracker
        # raised) will fail `result`.
        if not result.ok:
            message = result.error.message if result.error else "Upload failed"
            self._finish(False, message)
            return
        # Trigger one last poll so any final progress update lands.
        self._poll_progress()

    def _poll_progress(self) -> None:
        facade = self.facade
        if facade is None or self._ctx.job_id is None:
            return
        job = facade.progress_store.get(self._ctx.job_id)
        if job is None:
            return
        try:
            bar = self.query_one("#publish-progress", ProgressBar)
            status = self.query_one("#publish-progress-status", Static)
        except Exception:
            return
        bar.update(progress=job.percent)
        if job.status == "running":
            status.update(f"Uploading… {job.percent}%")
            return
        if job.status == "complete":
            self._finish(True, "Upload complete.")
            return
        if job.status == "error":
            self._finish(False, job.error or "Upload failed")
            return

    # ----- step: done -----

    def _build_done_body(self) -> list[Any]:
        ctx = self._ctx
        success = bool(ctx.final_success)
        title = "✓ Upload complete" if success else "✗ Upload failed"
        message = ctx.final_message or ("" if success else "Upload did not complete.")
        return [
            Static(title, classes="step-title"),
            Static(message, id="publish-done-message"),
            Static(
                "[Esc] Close",
                id="publish-action-hint",
            ),
        ]

    def _finish(self, success: bool, message: str) -> None:
        self._ctx.final_success = success
        self._ctx.final_message = message
        # Stop the polling timer.
        if self._poll_timer is not None:
            try:
                self._poll_timer.stop()
            except Exception:
                pass
            self._poll_timer = None
        if success:
            self._lumlflow_app.show_toast(
                "Published to cloud.", severity="success", duration=2.0
            )
        else:
            self._lumlflow_app.show_toast(
                f"Publish failed: {message}", severity="error"
            )
        self._set_step("done")

    # ----- inline error helper -----

    def _set_error(self, message: str | None) -> None:
        try:
            label = self.query_one("#publish-error", Static)
        except Exception:
            return
        if message:
            label.update(message)
            label.remove_class("-empty")
        else:
            label.update("")
            label.add_class("-empty")

    # ----- Enter / Esc -----

    def on_key(self, event) -> None:
        # The Enter key drives the per-step "confirm" action. Inside an
        # Input we let the input handle it (and the Submitted handler
        # below picks up auth submissions); on list/upload steps we
        # delegate to a state-specific handler so the screen always
        # advances on a clear primary action.
        if event.key == "enter":
            focused = self.focused
            if isinstance(focused, Input):
                # Auth step routes via on_input_submitted; upload step
                # treats any Input.Submitted as "start the upload".
                if self._step == "upload":
                    if self._read_upload_form():
                        self._start_upload()
                        event.stop()
                return
            if self._step == "upload":
                if self._read_upload_form():
                    self._start_upload()
                    event.stop()

    def action_back_or_cancel(self) -> None:
        """Esc / Ctrl-C: step back, or close the screen.

        On the `progress` step Esc cancels the current poll cycle and
        returns to the upload form (the upload itself runs in a worker
        and is left to complete — its result is then ignored from the
        UI). On the terminal `done` step Esc closes the screen.
        """

        if self._step == "auth":
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            return
        if self._step == "org":
            self._set_step("auth")
            return
        if self._step == "orbit":
            self._ctx.orbit = None
            self._set_step("org")
            return
        if self._step == "collection":
            self._ctx.collection = None
            self._set_step("orbit")
            return
        if self._step == "upload":
            self._set_step("collection")
            return
        if self._step == "progress":
            # Stop the poller but leave the upload running — there is no
            # cancellation API on the artifact handler. Going back to the
            # upload form lets the user retry without losing context.
            if self._poll_timer is not None:
                try:
                    self._poll_timer.stop()
                except Exception:
                    pass
                self._poll_timer = None
            self._set_step("upload")
            return
        if self._step == "done":
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            return


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_id(value: str) -> str:
    """Return a CSS-safe widget id fragment.

    Org/orbit/collection ids are not guaranteed to be plain ascii; this
    keeps Textual happy with the constructed `id=…` strings.
    """

    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


__all__ = ("CloudPublishScreen",)
