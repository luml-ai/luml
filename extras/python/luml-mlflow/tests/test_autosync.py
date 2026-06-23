"""Tests for the auto-sync-on-run-end trigger.

Auto-sync fires from ``LumlTrackingStore.update_run_info`` when a run moves to
a terminal status. It MUST never raise into user training code — failures are
swallowed, captured in ``upload_status=failed`` / ``luml.upload_error``, and
``mlflow.end_run()`` returns normally. Local-only targets are skipped silently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from luml_mlflow.meta import (
    LUML_UPLOAD_ERROR,
    META_LUML_INTERNAL,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_NOT_UPLOADED,
    UPLOAD_STATUS_UPLOADED,
)
from luml_mlflow.store import LumlTrackingStore
from mlflow.entities import RunStatus

from tests.test_sync import FakeLumlClient


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


# ----------------------------------------------------------------- success


def test_autosync_uploads_on_finished(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        store.update_run_info(run_id, RunStatus.FINISHED, end_time=1000, run_name=None)

    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_UPLOADED
    assert len(fake_client.artifacts.upload_calls) == 1


def test_autosync_fires_on_failed_too(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        store.update_run_info(run_id, RunStatus.FAILED, end_time=1000, run_name=None)

    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_UPLOADED


# ----------------------------------------------------------------- gating


def test_autosync_does_not_fire_on_non_terminal(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        store.update_run_info(run_id, RunStatus.RUNNING, end_time=None, run_name=None)

    assert fake_client.artifacts.upload_calls == []
    assert (
        store._tracker.get_experiment_upload_status(run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


def test_autosync_disabled_by_env(
    store: LumlTrackingStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from luml_mlflow import config as config_mod

    monkeypatch.setenv("LUML_MLFLOW_AUTOSYNC", "0")
    config_mod.reset_settings_cache()

    run_id = _start_run(store)
    fake_client = FakeLumlClient()

    with patch("luml_mlflow.sync._build_client", return_value=fake_client):
        store.update_run_info(run_id, RunStatus.FINISHED, end_time=1000, run_name=None)

    assert fake_client.artifacts.upload_calls == []
    assert (
        store._tracker.get_experiment_upload_status(run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


def test_autosync_skips_local_only_target(temp_store: Path) -> None:
    local = LumlTrackingStore("luml://local")
    exp_id = local.create_experiment("local-test")
    run = local.create_run(exp_id, user_id="u", start_time=0, tags=[], run_name="r")

    # No patch is needed — the local-only short-circuit must happen before any
    # client is built.
    local.update_run_info(
        run.info.run_id, RunStatus.FINISHED, end_time=1000, run_name=None
    )

    assert (
        local._tracker.get_experiment_upload_status(run.info.run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


# ----------------------------------------------------------------- failure


def test_autosync_failure_does_not_raise(store: LumlTrackingStore) -> None:
    """An upload failure during auto-sync must NOT propagate into user code."""
    run_id = _start_run(store)

    def _exploding_client(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("luml api unreachable")

    with patch("luml_mlflow.sync._build_client", side_effect=_exploding_client):
        # The call must return normally — auto-sync swallows the failure.
        store.update_run_info(run_id, RunStatus.FINISHED, end_time=1000, run_name=None)

    # And the failure is recorded so the user can see what happened.
    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_FAILED
    meta = store._tracker.get_experiment_metadata(run_id)
    assert "luml api unreachable" in (
        meta.get(META_LUML_INTERNAL, {}).get(LUML_UPLOAD_ERROR) or ""
    )
