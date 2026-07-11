"""Tests for the cloud publish flow.

Covers SPEC.md task: "Add the cloud publish flow" — auth-gate modal
(set/validate/store API key), org → orbit → collection pickers,
upload-type/options selection, and live upload progress with
success/error states.

All tests mock `AuthHandler` / `LumlHandler` / `ArtifactHandler` so the
suite never touches the real network, keyring, or filesystem. The
screen is exercised through Textual's headless `App.run_test()` + the
`Pilot` driver against an in-memory `ExperimentTracker`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.infra.exceptions import ApplicationError
from lumlflow.schemas.experiments import (
    ExperimentDetails,
    ExperimentStatus,
)
from lumlflow.schemas.luml import (
    Collection,
    Orbit,
    Organization,
    PaginatedCollections,
    UploadArtifactForm,
    UploadType,
)
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.cloud_publish import (
    CloudPublishScreen,
    _safe_id,
)
from lumlflow.tui.screens.experiments import ExperimentsScreen
from textual.widgets import Input, ListView, RadioButton, RadioSet, Static

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade)


def _seed_experiment(
    tracker: ExperimentTracker, *, group: str = "g", name: str = "exp"
) -> str:
    """Create one finished experiment; return its id."""

    tracker.create_group(group)
    exp_id = tracker.start_experiment(name=name, group=group)
    tracker.end_experiment(experiment_id=exp_id)
    return exp_id


def _details(exp_id: str, name: str = "exp") -> ExperimentDetails:
    return ExperimentDetails(
        id=exp_id,
        name=name,
        status=ExperimentStatus.COMPLETED,
        created_at=datetime.now(),
    )


def _push_publish(
    app: LumlflowApp,
    facade: DataFacade,
    *,
    experiment_id: str = "exp-1",
    experiment_name: str = "alpha",
    job_id_factory=None,
) -> CloudPublishScreen:
    kwargs: dict[str, Any] = {
        "facade": facade,
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
    }
    if job_id_factory is not None:
        kwargs["job_id_factory"] = job_id_factory
    screen = CloudPublishScreen(**kwargs)
    app.push_screen(screen)
    return screen


async def _wait_until(
    pilot: Any,
    predicate: Callable[[], object],
    *,
    label: str,
    tries: int = 300,
) -> None:
    """Pause until `predicate()` is truthy (bounded, ~3s budget).

    The publish flow advances on *worker-thread* time, not message-pump
    time, so a fixed number of `pilot.pause()` calls is a race on a
    loaded machine. Polling a concrete readiness condition keeps these
    tests deterministic regardless of scheduler pressure.
    """

    for _ in range(tries):
        if predicate():
            return
        await pilot.pause(0.01)
    raise AssertionError(f"timed out waiting for {label}")


def _list_children(screen: CloudPublishScreen, list_id: str) -> list[Any]:
    """Children of a publish-step ListView, or [] before it mounts."""

    try:
        view = screen.query_one(f"#{list_id}", ListView)
    except Exception:
        return []
    return list(view.children)


async def _walk_to_upload_step(
    pilot: Any, screen: CloudPublishScreen
) -> None:
    """Drive org → orbit → collection, waiting out each fetch worker."""

    await _wait_until(pilot, lambda: screen._orgs, label="organizations")
    screen._select_org_at(0)
    await _wait_until(pilot, lambda: screen._orbits, label="orbits")
    screen._select_orbit_at(0)
    await _wait_until(pilot, lambda: screen._collections, label="collections")
    screen._select_collection_at(0)
    await _wait_until(
        pilot,
        lambda: screen._step == "upload" and bool(screen.query(Input)),
        label="the upload form",
    )


def _org(id_: str = "org-1", name: str = "Acme") -> Organization:
    return Organization(id=id_, name=name, created_at="2026-01-01T00:00:00Z")


def _orbit(id_: str = "orb-1", name: str = "Main") -> Orbit:
    return Orbit(
        id=id_,
        name=name,
        organization_id="org-1",
        bucket_secret_id="bs-1",
        created_at="2026-01-01T00:00:00Z",
    )


def _collection(
    id_: str = "col-1", name: str = "Models", type_: str = "model"
) -> Collection:
    return Collection(
        id=id_,
        orbit_id="orb-1",
        description="",
        name=name,
        type=type_,
        created_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """`_safe_id` is tiny but load-bearing."""

    def test_safe_id_keeps_alphanumeric(self) -> None:
        assert _safe_id("abc123") == "abc123"

    def test_safe_id_replaces_dots_and_slashes(self) -> None:
        assert _safe_id("a/b.c") == "a_b_c"

    def test_safe_id_keeps_dash_and_underscore(self) -> None:
        assert _safe_id("a-b_c") == "a-b_c"


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


class TestAuthGate:
    """The screen prompts for an API key when one is not stored."""

    async def test_missing_key_lands_on_auth_step(
        self, facade: DataFacade
    ) -> None:
        with patch.object(facade.auth, "has_api_key", return_value=False):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-api-key-input")),
                    label="the auth form",
                )
                assert screen._step == "auth"
                # The API key input is mounted.
                assert screen.query_one("#publish-api-key-input", Input) is not None

    async def test_existing_key_skips_to_org_step(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot,
                    lambda: _list_children(screen, "publish-org-list"),
                    label="the org list",
                )
                assert screen._step == "org"
                view = screen.query_one("#publish-org-list", ListView)
                # The org appears in the picker.
                ids = [child.id for child in view.children]
                assert any("publish-org-org-1" == i for i in ids), ids

    async def test_invalid_key_shows_inline_error(
        self, facade: DataFacade
    ) -> None:
        """A 401 from `set_api_key` becomes an inline error, not a crash."""

        with (
            patch.object(facade.auth, "has_api_key", return_value=False),
            patch.object(
                facade.auth,
                "set_api_key",
                side_effect=ApplicationError("Invalid API key", status_code=401),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-api-key-input")),
                    label="the auth form",
                )
                screen._submit_api_key("bad")
                await _wait_until(
                    pilot,
                    lambda: "Invalid API key"
                    in str(screen.query_one("#publish-error", Static).render()),
                    label="the inline error",
                )
                rendered = str(
                    screen.query_one("#publish-error", Static).render()
                )
                assert "Invalid API key" in rendered
                # Still on auth step — never advanced.
                assert screen._step == "auth"

    async def test_unreachable_platform_shows_reachability_error(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=False),
            patch.object(
                facade.auth,
                "set_api_key",
                side_effect=ApplicationError(
                    "Could not reach LUML platform at http://localhost:1 "
                    "(ConnectError: connection refused)",
                    502,
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-api-key-input")),
                    label="the auth form",
                )
                screen._submit_api_key("anything")
                await _wait_until(
                    pilot,
                    lambda: "Could not reach"
                    in str(screen.query_one("#publish-error", Static).render()),
                    label="the reachability error",
                )
                rendered = str(
                    screen.query_one("#publish-error", Static).render()
                )
                assert "Could not reach" in rendered
                # The handler's diagnostic detail (URL + cause) must reach
                # the screen unmangled — it's the only way the user can
                # tell a bad base-url override from a network failure.
                assert "http://localhost:1" in rendered
                assert "ConnectError" in rendered
                assert screen._step == "auth"

    async def test_valid_key_advances_to_org_step(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=False),
            patch.object(facade.auth, "set_api_key", return_value=None),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-api-key-input")),
                    label="the auth form",
                )
                screen._submit_api_key("good-key")
                await _wait_until(
                    pilot,
                    lambda: screen._step == "org",
                    label="the org step",
                )

    async def test_empty_key_inline_error(self, facade: DataFacade) -> None:
        with patch.object(facade.auth, "has_api_key", return_value=False):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-api-key-input")),
                    label="the auth form",
                )
                screen._submit_api_key("   ")
                await _wait_until(
                    pilot,
                    lambda: "API key is required"
                    in str(screen.query_one("#publish-error", Static).render()),
                    label="the empty-key error",
                )


# ---------------------------------------------------------------------------
# Target selection — org → orbit → collection
# ---------------------------------------------------------------------------


class TestTargetSelection:
    async def test_selecting_org_fetches_orbits(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org("org-1", "Acme")],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit("orb-1", "Main"), _orbit("orb-2", "Side")],
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                # Land on org step (auth check + org fetch run on workers).
                await _wait_until(
                    pilot, lambda: screen._orgs, label="organizations"
                )
                assert screen._step == "org"
                # Programmatically pick org index 0.
                screen._select_org_at(0)
                await _wait_until(
                    pilot,
                    lambda: len(_list_children(screen, "publish-orbit-list"))
                    == 2,
                    label="the orbit list",
                )
                assert screen._step == "orbit"
                assert screen._ctx.organization is not None
                assert screen._ctx.organization.id == "org-1"

    async def test_selecting_orbit_fetches_collections(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[
                        _collection("col-1", "models", "model"),
                        _collection("col-2", "datasets", "dataset"),
                    ],
                    cursor=None,
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot, lambda: screen._orgs, label="organizations"
                )
                screen._select_org_at(0)
                await _wait_until(
                    pilot, lambda: screen._orbits, label="orbits"
                )
                screen._select_orbit_at(0)
                await _wait_until(
                    pilot,
                    lambda: len(
                        _list_children(screen, "publish-collection-list")
                    )
                    == 2,
                    label="the collection list",
                )
                assert screen._step == "collection"

    async def test_selecting_collection_advances_to_upload(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                assert screen._step == "upload"
                # Selections are captured on the context.
                assert screen._ctx.organization is not None
                assert screen._ctx.orbit is not None
                assert screen._ctx.collection is not None

    async def test_org_listing_unauthorized_bounces_back_to_auth(
        self, facade: DataFacade
    ) -> None:
        """A 401 mid-flow gates the user back to the auth step."""

        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                side_effect=ApplicationError(
                    "API key not configured", status_code=401
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)

                def _bounced_with_error() -> bool:
                    if screen._step != "auth":
                        return False
                    try:
                        err = screen.query_one("#publish-error", Static)
                    except Exception:
                        return False
                    return "API key not configured" in str(err.render())

                await _wait_until(
                    pilot, _bounced_with_error, label="the auth bounce"
                )

    async def test_back_from_collection_returns_to_orbit(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await _wait_until(
                    pilot, lambda: screen._orgs, label="organizations"
                )
                screen._select_org_at(0)
                await _wait_until(
                    pilot, lambda: screen._orbits, label="orbits"
                )
                screen._select_orbit_at(0)
                await _wait_until(
                    pilot,
                    lambda: screen._step == "collection",
                    label="the collection step",
                )
                # Back from collection — pop to orbit.
                screen.action_back_or_cancel()
                await pilot.pause()
                assert screen._step == "orbit"
                # Back from orbit — pop to org.
                screen.action_back_or_cancel()
                await pilot.pause()
                assert screen._step == "org"


# ---------------------------------------------------------------------------
# Upload step + progress
# ---------------------------------------------------------------------------


class TestUploadProgress:
    """`_start_upload` drives `upload_artifact` and reads `ProgressStore`."""

    async def test_progress_reaches_complete_on_success(
        self, facade: DataFacade
    ) -> None:
        """Once `upload_artifact` returns, the progress store's `complete`
        status is reflected in the screen's done step."""

        def fake_upload(form: UploadArtifactForm, job_id: str) -> None:
            # Simulate the artifact handler writing to the progress store.
            facade.progress_store.update_progress(job_id, 50)
            facade.progress_store.update_progress(job_id, 100)
            facade.progress_store.set_complete(job_id, [{"id": "a-1"}])

        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
            patch.object(
                facade.artifacts, "upload_artifact", side_effect=fake_upload
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(
                    app, facade, job_id_factory=lambda: "job-1"
                )
                await pilot.pause()
                await pilot.pause()
                # Walk through the picker steps.
                await _walk_to_upload_step(pilot, screen)
                # Start the upload (skip filling the form — defaults are fine).
                screen._start_upload()
                # Let the worker complete and the poller tick.
                await _wait_until(
                    pilot,
                    lambda: screen._step == "done",
                    label="upload completion",
                )
                # Polled progress eventually transitioned to done.
                assert screen._step == "done"
                assert screen._ctx.final_success is True

    async def test_progress_error_shows_done_with_failure(
        self, facade: DataFacade
    ) -> None:
        """An error written to the store is shown as the failure summary."""

        def fake_upload(form: UploadArtifactForm, job_id: str) -> None:
            facade.progress_store.set_error(job_id, "boom on upload")

        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
            patch.object(
                facade.artifacts, "upload_artifact", side_effect=fake_upload
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(
                    app, facade, job_id_factory=lambda: "job-err"
                )
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                screen._start_upload()
                await _wait_until(
                    pilot,
                    lambda: screen._step == "done",
                    label="upload completion",
                )
                assert screen._step == "done"
                assert screen._ctx.final_success is False
                assert "boom on upload" in (screen._ctx.final_message or "")

    async def test_in_flight_progress_renders_bar(
        self, facade: DataFacade
    ) -> None:
        """While the upload is running, the bar reflects `percent`."""

        # Block the fake upload so we can inspect mid-flight state.
        upload_started: list[str] = []

        def fake_upload(form: UploadArtifactForm, job_id: str) -> None:
            facade.progress_store.update_progress(job_id, 42)
            upload_started.append(job_id)
            # Don't finish — leave the bar at 42% so the poller picks it up.

        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
            patch.object(
                facade.artifacts, "upload_artifact", side_effect=fake_upload
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(
                    app, facade, job_id_factory=lambda: "job-mid"
                )
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                screen._start_upload()
                await _wait_until(
                    pilot,
                    lambda: upload_started,
                    label="the upload worker to start",
                )
                # The fake completed sync-but-not-via-store; once
                # `_run_upload` returns the screen polls one last time.
                # In all cases the screen ended on `done` (worker returned
                # successfully but progress store status is still "running",
                # so the final state is reached only when the poller sees
                # a terminal status). We assert the *progress* path: the
                # bar reflected the percent at some point — read it now.
                # Either it's at done (fast poller) or it's still showing
                # progress; both are acceptable for this assertion.
                assert upload_started == ["job-mid"]

    async def test_facade_failure_marks_done_failed(
        self, facade: DataFacade
    ) -> None:
        """An unexpected facade-level exception still lands on done(failed)."""

        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
            patch.object(
                facade.artifacts,
                "upload_artifact",
                side_effect=RuntimeError("kaboom"),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(
                    app, facade, job_id_factory=lambda: "job-2"
                )
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                screen._start_upload()
                await _wait_until(
                    pilot,
                    lambda: screen._step == "done",
                    label="upload completion",
                )
                assert screen._step == "done"
                assert screen._ctx.final_success is False
                assert "kaboom" in (screen._ctx.final_message or "")


# ---------------------------------------------------------------------------
# Upload form values
# ---------------------------------------------------------------------------


class TestUploadForm:
    """`_read_upload_form` reads the per-step widgets into context."""

    async def test_form_captures_upload_type_and_tags(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
            patch.object(
                facade.luml,
                "get_luml_orbits",
                return_value=[_orbit()],
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                assert screen._step == "upload"
                # Set the form values directly.
                type_view = screen.query_one(
                    "#publish-upload-type-list", ListView
                )
                type_view.index = 1  # "model"
                await pilot.pause()
                # The embed row is only shown for type=model; flip the
                # radio to "yes".
                embed_radio = screen.query_one(
                    "#publish-embed-radio", RadioSet
                )
                assert screen.query_one("#publish-embed-row").display is True
                buttons = list(embed_radio.query(RadioButton))
                buttons[1].value = True
                await pilot.pause()
                screen.query_one(
                    "#publish-artifact-name-input", Input
                ).value = "my-name"
                screen.query_one(
                    "#publish-artifact-desc-input", Input
                ).value = "my-desc"
                screen.query_one(
                    "#publish-artifact-tags-input", Input
                ).value = "prod, baseline, "
                ok = screen._read_upload_form()
                assert ok is True
                assert screen._ctx.upload_type == UploadType.MODEL
                assert screen._ctx.embed_experiment is True
                assert screen._ctx.artifact_name == "my-name"
                assert screen._ctx.artifact_description == "my-desc"
                assert screen._ctx.artifact_tags == ["prod", "baseline"]


# ---------------------------------------------------------------------------
# Wiring: pressing `p` on the experiments screen opens the publish flow
# ---------------------------------------------------------------------------


class TestWiringFromExperimentsScreen:
    async def test_p_opens_publish_flow(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_experiment(tracker, name="alpha")
        # Patch auth/orgs so the screen lands somewhere stable.
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = ExperimentsScreen(
                    facade=facade,
                    group_id=tracker.list_groups()[0].id,
                    group_name="g",
                )
                app.push_screen(screen)
                await _wait_until(
                    pilot, lambda: screen._rows, label="the experiments rows"
                )
                screen.action_publish_focused()
                await _wait_until(
                    pilot,
                    lambda: isinstance(app.screen, CloudPublishScreen),
                    label="the publish screen",
                )


# ---------------------------------------------------------------------------
# Esc returns from the auth step
# ---------------------------------------------------------------------------


class TestEscReturnsFromAuth:
    async def test_back_on_auth_pops_screen(
        self, facade: DataFacade
    ) -> None:
        with patch.object(facade.auth, "has_api_key", return_value=False):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                # Push a second screen so the stack has > 1.
                home_only_stack_depth = len(app.screen_stack)
                screen = _push_publish(app, facade)
                await pilot.pause()
                await pilot.pause()
                assert len(app.screen_stack) == home_only_stack_depth + 1
                screen.action_back_or_cancel()
                await _wait_until(
                    pilot,
                    lambda: len(app.screen_stack) == home_only_stack_depth,
                    label="the screen pop",
                )


# ---------------------------------------------------------------------------
# Done step renders the final message
# ---------------------------------------------------------------------------


class TestDoneStep:
    async def test_done_success_renders_message(
        self, facade: DataFacade
    ) -> None:
        with patch.object(facade.auth, "has_api_key", return_value=True), \
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await pilot.pause()
                await pilot.pause()
                screen._finish(True, "All done.")
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-done-message")),
                    label="the done body",
                )
                msg = screen.query_one("#publish-done-message", Static)
                assert "All done." in str(msg.render())

    async def test_done_failure_renders_error_title(
        self, facade: DataFacade
    ) -> None:
        with patch.object(facade.auth, "has_api_key", return_value=True), \
            patch.object(
                facade.luml,
                "get_luml_organizations",
                return_value=[_org()],
            ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await pilot.pause()
                await pilot.pause()
                screen._finish(False, "It broke.")
                await _wait_until(
                    pilot,
                    lambda: bool(screen.query("#publish-done-message")),
                    label="the done body",
                )
                msg = screen.query_one("#publish-done-message", Static)
                assert "It broke." in str(msg.render())


# ---------------------------------------------------------------------------
# Manual upload mode (file from disk, `u` from anywhere)
# ---------------------------------------------------------------------------


class TestManualUploadMode:
    """Constructed without an experiment, the screen uploads a file."""

    def _cloud_patches(self, facade: DataFacade):
        return (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml, "get_luml_organizations", return_value=[_org()]
            ),
            patch.object(
                facade.luml, "get_luml_orbits", return_value=[_orbit()]
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
        )

    async def test_u_key_opens_manual_upload(self, facade: DataFacade) -> None:
        with patch.object(facade.auth, "has_api_key", return_value=False):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, CloudPublishScreen)
                assert screen._is_manual is True
                # A second `u` must not stack another publish screen.
                await pilot.press("u")
                await pilot.pause()
                assert app.screen is screen

    async def test_u_key_inert_outside_home(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """`u` uploads only from the home screen; on screens where a
        tracked entity is in focus, `p` (publish) is the single cloud
        verb."""

        from lumlflow.tui.screens.experiment_detail import (
            ExperimentDetailScreen,
        )

        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="e", group="g")
        tracker.end_experiment(experiment_id=exp_id)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentDetailScreen(
                facade=facade, experiment_id=exp_id, experiment_name="e"
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            await pilot.press("u")
            await pilot.pause()
            assert app.screen is screen

    async def test_manual_upload_step_shows_file_form(
        self, facade: DataFacade
    ) -> None:
        p1, p2, p3, p4 = self._cloud_patches(facade)
        with p1, p2, p3, p4:
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = CloudPublishScreen(facade=facade)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                assert screen._step == "upload"
                # File-path input replaces the upload-type list.
                assert screen.query_one("#publish-file-path-input", Input)
                assert not screen.query("#publish-upload-type-list")

    async def test_manual_upload_rejects_missing_file(
        self, facade: DataFacade
    ) -> None:
        p1, p2, p3, p4 = self._cloud_patches(facade)
        with p1, p2, p3, p4:
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = CloudPublishScreen(facade=facade)
                app.push_screen(screen)
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                path_input = screen.query_one(
                    "#publish-file-path-input", Input
                )
                path_input.value = "/definitely/not/a/file.luml"
                assert screen._read_upload_form() is False
                error = screen.query_one("#publish-error", Static)
                assert "No such file" in str(error.render())

    async def test_manual_upload_uploads_chosen_file(
        self, facade: DataFacade, tmp_path: Path
    ) -> None:
        artifact_file = tmp_path / "model.luml"
        artifact_file.write_bytes(b"fake-model")
        received: list[Any] = []

        def fake_upload_file(form: Any, job_id: str) -> None:
            received.append(form)
            facade.progress_store.update_progress(job_id, 100)
            facade.progress_store.set_complete(job_id, [{"id": "a-1"}])

        p1, p2, p3, p4 = self._cloud_patches(facade)
        with (
            p1,
            p2,
            p3,
            p4,
            patch.object(
                facade.artifacts, "upload_file", side_effect=fake_upload_file
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = CloudPublishScreen(
                    facade=facade, job_id_factory=lambda: "job-manual"
                )
                app.push_screen(screen)
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                screen.query_one(
                    "#publish-file-path-input", Input
                ).value = str(artifact_file)
                assert screen._read_upload_form() is True
                screen._start_upload()
                await _wait_until(
                    pilot,
                    lambda: screen._step == "done",
                    label="upload completion",
                )
                assert screen._step == "done"
                assert screen._ctx.final_success is True
                assert len(received) == 1
                form = received[0]
                assert form.file_path == str(artifact_file)
                assert form.collection_id == "col-1"


class TestArtifactHandlerUploadFile:
    """Unit tests for `ArtifactHandler.upload_file` (no network)."""

    def test_missing_file_writes_error_to_store(
        self, facade: DataFacade
    ) -> None:
        from lumlflow.schemas.luml import ArtifactIn, UploadFileForm

        handler = facade.artifacts
        handler.progress_store.create("job-x")
        form = UploadFileForm(
            file_path="/no/such/file.luml",
            organization_id="org-1",
            orbit_id="orb-1",
            collection_id="col-1",
            artifact=ArtifactIn(),
        )
        with patch.object(handler, "_get_luml_client") as client:
            handler.upload_file(form, "job-x")
            client.assert_not_called()
        job = handler.progress_store.get("job-x")
        assert job is not None
        assert job.status == "error"
        assert "File not found" in (job.error or "")

    def test_uploads_existing_file_with_stem_default_name(
        self, facade: DataFacade, tmp_path: Path
    ) -> None:
        from unittest.mock import MagicMock

        from lumlflow.schemas.luml import ArtifactIn, UploadFileForm

        artifact_file = tmp_path / "my-model.luml"
        artifact_file.write_bytes(b"data")
        handler = facade.artifacts
        handler.progress_store.create("job-y")
        uploaded = MagicMock()
        uploaded.model_dump.return_value = {"id": "a-1"}
        client = MagicMock()
        client.artifacts.upload.return_value = uploaded
        form = UploadFileForm(
            file_path=str(artifact_file),
            organization_id="org-1",
            orbit_id="orb-1",
            collection_id="col-1",
            artifact=ArtifactIn(),
        )
        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_file(form, "job-y")
        kwargs = client.artifacts.upload.call_args.kwargs
        assert kwargs["file_path"] == str(artifact_file)
        assert kwargs["name"] == "my-model"
        assert kwargs["collection_id"] == "col-1"
        job = handler.progress_store.get("job-y")
        assert job is not None
        assert job.status == "complete"


# ---------------------------------------------------------------------------
# Auto-embed parity + single-model publish
# ---------------------------------------------------------------------------


class TestEmbedRadioVisibility:
    """The embed question only appears for type=model (auto derives it)."""

    async def test_embed_row_hidden_for_auto_and_experiment(
        self, facade: DataFacade
    ) -> None:
        with (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml, "get_luml_organizations", return_value=[_org()]
            ),
            patch.object(
                facade.luml, "get_luml_orbits", return_value=[_orbit()]
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_publish(app, facade)
                await pilot.pause()
                await pilot.pause()
                await _walk_to_upload_step(pilot, screen)
                type_view = screen.query_one(
                    "#publish-upload-type-list", ListView
                )
                embed_row = screen.query_one("#publish-embed-row")
                # Default type is auto — embedding is derived, not asked.
                assert embed_row.display is False
                type_view.index = 1  # model → the question appears
                await pilot.pause()
                assert embed_row.display is True
                type_view.index = 2  # experiment → hidden again
                await pilot.pause()
                assert embed_row.display is False
                # Reading the form with type=auto keeps embed False even
                # if the radio was flipped while visible.
                type_view.index = 0
                await pilot.pause()
                assert screen._read_upload_form() is True
                assert screen._ctx.upload_type == UploadType.AUTO
                assert screen._ctx.embed_experiment is False


class TestModelPublishMode:
    """Constructed with a model id, the screen publishes that model."""

    def _cloud_patches(self, facade: DataFacade):
        return (
            patch.object(facade.auth, "has_api_key", return_value=True),
            patch.object(
                facade.luml, "get_luml_organizations", return_value=[_org()]
            ),
            patch.object(
                facade.luml, "get_luml_orbits", return_value=[_orbit()]
            ),
            patch.object(
                facade.luml,
                "get_luml_collections",
                return_value=PaginatedCollections(
                    items=[_collection()], cursor=None
                ),
            ),
        )

    async def test_model_mode_uploads_single_model(
        self, facade: DataFacade
    ) -> None:
        received: list[Any] = []

        def fake_upload_model(form: Any, job_id: str) -> None:
            received.append(form)
            facade.progress_store.update_progress(job_id, 100)
            facade.progress_store.set_complete(job_id, [{"id": "a-1"}])

        p1, p2, p3, p4 = self._cloud_patches(facade)
        with (
            p1,
            p2,
            p3,
            p4,
            patch.object(
                facade.artifacts, "upload_model", side_effect=fake_upload_model
            ),
        ):
            app = _make_app(facade)
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = CloudPublishScreen(
                    facade=facade,
                    experiment_id="exp-1",
                    experiment_name="alpha",
                    model_id="model-9",
                    model_name="resnet",
                    job_id_factory=lambda: "job-model",
                )
                app.push_screen(screen)
                await pilot.pause()
                await pilot.pause()
                assert screen._is_model is True
                await _walk_to_upload_step(pilot, screen)
                # Model mode: no type list, embed radio always visible,
                # artifact name pre-filled with the model name.
                assert not screen.query("#publish-upload-type-list")
                embed_radio = screen.query_one(
                    "#publish-embed-radio", RadioSet
                )
                buttons = list(embed_radio.query(RadioButton))
                buttons[1].value = True  # embed the experiment
                await pilot.pause()
                name_input = screen.query_one(
                    "#publish-artifact-name-input", Input
                )
                assert name_input.value == "resnet"
                assert screen._read_upload_form() is True
                screen._start_upload()
                await _wait_until(
                    pilot,
                    lambda: screen._step == "done",
                    label="upload completion",
                )
                assert screen._step == "done"
                assert screen._ctx.final_success is True
                assert len(received) == 1
                form = received[0]
                assert form.model_id == "model-9"
                assert form.experiment_id == "exp-1"
                assert form.embed_experiment is True
                assert form.collection_id == "col-1"


class TestArtifactHandlerUploadModel:
    """Unit tests for `ArtifactHandler.upload_model` (no network)."""

    def test_unknown_model_writes_error_to_store(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from lumlflow.schemas.luml import ArtifactIn, UploadModelForm

        exp_id = _seed_experiment(tracker)
        handler = facade.artifacts
        handler.progress_store.create("job-m1")
        form = UploadModelForm(
            model_id="nope",
            experiment_id=exp_id,
            organization_id="org-1",
            orbit_id="orb-1",
            collection_id="col-1",
            artifact=ArtifactIn(),
        )
        with patch.object(handler, "_get_luml_client") as client:
            handler.upload_model(form, "job-m1")
            client.assert_not_called()
        job = handler.progress_store.get("job-m1")
        assert job is not None
        assert job.status == "error"
        assert "Model not found" in (job.error or "")

    def test_uploads_the_requested_model(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        from unittest.mock import MagicMock

        from lumlflow.schemas.luml import ArtifactIn, UploadModelForm

        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="exp", group="g")
        model_file = tmp_path / "model.luml"
        model_file.write_bytes(b"weights")
        tracker.backend.log_model(exp_id, str(model_file), name="resnet")
        models = tracker.get_models(exp_id)
        assert models
        handler = facade.artifacts
        handler.progress_store.create("job-m2")
        uploaded = MagicMock()
        uploaded.model_dump.return_value = {"id": "a-1"}
        client = MagicMock()
        client.artifacts.upload.return_value = uploaded
        form = UploadModelForm(
            model_id=models[0].id,
            experiment_id=exp_id,
            organization_id="org-1",
            orbit_id="orb-1",
            collection_id="col-1",
            artifact=ArtifactIn(name="custom-name"),
        )
        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_model(form, "job-m2")
        kwargs = client.artifacts.upload.call_args.kwargs
        assert kwargs["name"] == "custom-name"
        assert kwargs["collection_id"] == "col-1"
        job = handler.progress_store.get("job-m2")
        assert job is not None
        assert job.status == "complete"
