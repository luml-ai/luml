"""Tests for the ``luml-mlflow`` CLI.

The CLI orchestrates :mod:`luml_mlflow.sync`; tests cover the selection flags
(``--run`` / ``--experiment`` / ``--all``), error reporting, and the
local-only escape hatch.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from luml_mlflow.cli import app
from luml_mlflow.meta import UPLOAD_STATUS_NOT_UPLOADED, UPLOAD_STATUS_UPLOADED
from luml_mlflow.store import LumlTrackingStore
from typer.testing import CliRunner

from tests.test_sync import FakeLumlClient

runner = CliRunner()


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


def _start_run(store: LumlTrackingStore, group: str = "fraud") -> str:
    existing = store.get_experiment_by_name(group)
    exp_id = existing.experiment_id if existing else store.create_experiment(group)
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name=f"run-in-{group}",
    )
    return run.info.run_id


# ---------------------------------------------------------------- selection


def test_cli_sync_requires_one_selector(store: LumlTrackingStore) -> None:
    result = runner.invoke(app, ["sync"])
    # typer.BadParameter exits with code 2 (UsageError).
    assert result.exit_code != 0
    assert "exactly one of --run" in (result.stdout + result.stderr)


def test_cli_sync_selectors_are_mutually_exclusive(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    result = runner.invoke(app, ["sync", "--run", run_id, "--experiment", "fraud"])
    assert result.exit_code != 0
    assert "mutually exclusive" in (result.stdout + result.stderr)


# ---------------------------------------------------------------- --run


def test_cli_sync_single_run(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        result = runner.invoke(app, ["sync", "--run", run_id])

    assert result.exit_code == 0, result.stdout
    assert run_id in result.stdout
    assert "uploaded" in result.stdout
    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_UPLOADED


# ---------------------------------------------------------------- --experiment


def test_cli_sync_experiment_syncs_all_pending(store: LumlTrackingStore) -> None:
    r1 = _start_run(store, "fraud")
    r2 = _start_run(store, "fraud")
    other = _start_run(store, "abuse")
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        result = runner.invoke(app, ["sync", "--experiment", "fraud"])

    assert result.exit_code == 0, result.stdout
    assert r1 in result.stdout
    assert r2 in result.stdout
    # Different group — not synced.
    assert other not in result.stdout
    assert store._tracker.get_experiment_upload_status(r1) == UPLOAD_STATUS_UPLOADED
    assert (
        store._tracker.get_experiment_upload_status(other) == UPLOAD_STATUS_NOT_UPLOADED
    )


# ---------------------------------------------------------------- --all


def test_cli_sync_all_syncs_every_run(store: LumlTrackingStore) -> None:
    r1 = _start_run(store, "fraud")
    r2 = _start_run(store, "abuse")
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        result = runner.invoke(app, ["sync", "--all"])

    assert result.exit_code == 0, result.stdout
    assert r1 in result.stdout
    assert r2 in result.stdout
    assert store._tracker.get_experiment_upload_status(r1) == UPLOAD_STATUS_UPLOADED
    assert store._tracker.get_experiment_upload_status(r2) == UPLOAD_STATUS_UPLOADED


def test_cli_sync_no_runs_message(store: LumlTrackingStore) -> None:
    fake_client = FakeLumlClient()
    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        result = runner.invoke(app, ["sync", "--all"])
    assert result.exit_code == 0
    assert "No runs to sync." in result.stdout


# ---------------------------------------------------------------- local-only


def test_cli_sync_local_only_skipped(temp_store: Path) -> None:
    """Local-only runs are reported as skipped, never uploaded."""
    local = LumlTrackingStore("luml://local")
    exp_id = local.create_experiment("local-test")
    run = local.create_run(exp_id, user_id="u", start_time=0, tags=[], run_name="r")

    result = runner.invoke(app, ["sync", "--run", run.info.run_id])

    assert result.exit_code == 0, result.stdout
    assert "skipped" in result.stdout
    assert "local-only target" in result.stdout
    assert (
        local._tracker.get_experiment_upload_status(run.info.run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


def test_cli_sync_all_skips_local_only(temp_store: Path) -> None:
    local = LumlTrackingStore("luml://local")
    exp_id = local.create_experiment("local-test")
    run = local.create_run(exp_id, user_id="u", start_time=0, tags=[], run_name="r")

    # No client patching needed — local-only must not even attempt a client.
    result = runner.invoke(app, ["sync", "--all"])

    assert result.exit_code == 0, result.stdout
    assert "skipped" in result.stdout
    assert (
        local._tracker.get_experiment_upload_status(run.info.run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


# ---------------------------------------------------------------- status


def test_cli_status_reports_uploaded(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        runner.invoke(app, ["sync", "--run", run_id])

    result = runner.invoke(app, ["status", "--run", run_id])
    assert result.exit_code == 0, result.stdout
    assert "uploaded" in result.stdout
    assert "artifact_urls" in result.stdout


def test_cli_status_initial_is_not_uploaded(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    result = runner.invoke(app, ["status", "--run", run_id])
    assert result.exit_code == 0, result.stdout
    assert "not_uploaded" in result.stdout


# ---------------------------------------------------------------- force


def test_cli_force_re_syncs(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        # First sync.
        runner.invoke(app, ["sync", "--run", run_id])
        # Without --force this would be skipped.
        result = runner.invoke(app, ["sync", "--run", run_id, "--force"])

    assert result.exit_code == 0, result.stdout
    # Two uploads happened (once initial, once forced re-sync).
    assert len(fake_client.artifacts.upload_calls) == 2
