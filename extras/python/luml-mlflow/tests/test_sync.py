"""Tests for the sync orchestrator and Python API.

The :class:`LumlClient` is faked out: the sync layer interacts with it through
``client.collections`` and ``client.artifacts.upload``, both of which are
replaced by an in-memory ``FakeLumlClient``. This lets the tests assert on
combine-vs-separate behaviour, collection resolution, idempotency, and
write-back metadata without touching the real API.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from luml_mlflow.artifact_repo import LumlArtifactRepository
from luml_mlflow.meta import (
    LUML_ARTIFACT_IDS,
    LUML_ARTIFACT_URLS,
    LUML_COLLECTION_ID,
    LUML_ORBIT_ID,
    LUML_ORGANIZATION_ID,
    LUML_UPLOAD_ERROR,
    META_LUML_INTERNAL,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_NOT_UPLOADED,
    UPLOAD_STATUS_UPLOADED,
)
from luml_mlflow.store import LumlTrackingStore

# ``luml_mlflow.sync`` is also a public re-exported function, so resolve the
# submodule explicitly to avoid shadowing.
sync_mod = importlib.import_module("luml_mlflow.sync")


# ---------------------------------------------------------------- fakes


@dataclass
class FakeCollection:
    id: str
    name: str
    type: str
    description: str = ""
    orbit_id: str = "orbit-1"
    total_artifacts: int = 0
    created_at: str = "2024-01-01T00:00:00Z"


@dataclass
class FakeArtifact:
    id: str
    name: str
    file_path: str
    collection_id: str
    tags: list[str] | None = None


@dataclass
class FakeCollectionsResource:
    collections: dict[str, FakeCollection] = field(default_factory=dict)
    create_calls: list[dict[str, Any]] = field(default_factory=list)

    def get(self, value: str | None = None) -> FakeCollection | None:
        if value is None:
            return None
        for collection in self.collections.values():
            if collection.id == value or collection.name == value:
                return collection
        return None

    def create(
        self,
        description: str,
        name: str,
        type: Any,  # noqa: A002
        tags: list[str] | None = None,
    ) -> FakeCollection:
        type_value = getattr(type, "value", type)
        self.create_calls.append(
            {
                "description": description,
                "name": name,
                "type": type_value,
                "tags": tags,
            }
        )
        new_id = f"col-{len(self.collections) + 1}"
        col = FakeCollection(
            id=new_id, name=name, type=type_value, description=description
        )
        self.collections[new_id] = col
        return col


@dataclass
class FakeArtifactsResource:
    artifacts: list[FakeArtifact] = field(default_factory=list)
    upload_calls: list[dict[str, Any]] = field(default_factory=list)
    raise_on_upload: bool = False

    def upload(
        self,
        file_path: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        *,
        collection_id: str | None = None,
        on_progress: Any = None,
    ) -> FakeArtifact:
        if self.raise_on_upload:
            raise RuntimeError("simulated upload failure")
        self.upload_calls.append(
            {
                "file_path": file_path,
                "name": name,
                "tags": tags,
                "collection_id": collection_id,
            }
        )
        art = FakeArtifact(
            id=f"art-{len(self.artifacts) + 1}",
            name=name or Path(file_path).name,
            file_path=file_path,
            collection_id=collection_id or "",
            tags=tags,
        )
        self.artifacts.append(art)
        return art


@dataclass
class FakeLumlClient:
    collections: FakeCollectionsResource = field(
        default_factory=FakeCollectionsResource
    )
    artifacts: FakeArtifactsResource = field(default_factory=FakeArtifactsResource)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


@pytest.fixture
def fake_client() -> FakeLumlClient:
    return FakeLumlClient()


def _start_run(store: LumlTrackingStore, group: str = "fraud") -> str:
    existing = store.get_experiment_by_name(group)
    if existing is None:
        exp_id = store.create_experiment(group)
    else:
        exp_id = existing.experiment_id
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name=f"run-in-{group}",
    )
    return run.info.run_id


def _make_mlflow_model_dir(parent: Path, name: str = "model") -> Path:
    model_dir = parent / name
    model_dir.mkdir(parents=True)
    (model_dir / "MLmodel").write_text(
        "flavors:\n  python_function:\n    loader_module: m.l\n"
    )
    (model_dir / "weights.bin").write_bytes(b"\x00\x01\x02fake-weights")
    return model_dir


def _log_model(
    store: LumlTrackingStore, run_id: str, tmp_path: Path, name: str
) -> None:
    model_dir = _make_mlflow_model_dir(tmp_path, name=name)
    repo = LumlArtifactRepository(store._artifact_uri_for_run(run_id))
    repo.log_artifacts(str(model_dir), artifact_path=name)


# ---------------------------------------------------------------- single-model


def test_single_model_combined_artifact(
    store: LumlTrackingStore, fake_client: FakeLumlClient, tmp_path: Path
) -> None:
    run_id = _start_run(store)
    _log_model(store, run_id, tmp_path, "rf")

    result = sync_mod.sync(run_id, client=fake_client)

    assert result.status == UPLOAD_STATUS_UPLOADED
    assert len(result.artifact_ids) == 1
    assert len(fake_client.artifacts.upload_calls) == 1
    upload = fake_client.artifacts.upload_calls[0]
    # The single model is uploaded (embedded).
    assert upload["name"] == "rf"
    # The collection was created — mixed, named after the group.
    assert fake_client.collections.create_calls == [
        {
            "description": "MLflow experiment 'fraud'",
            "name": "fraud",
            "type": "mixed",
            "tags": None,
        }
    ]
    # Write-back metadata.
    assert store._tracker.get_experiment_upload_status(run_id) == (
        UPLOAD_STATUS_UPLOADED
    )
    meta = store._tracker.get_experiment_metadata(run_id)
    luml = meta[META_LUML_INTERNAL]
    assert luml[LUML_ARTIFACT_IDS] == result.artifact_ids
    assert luml[LUML_ARTIFACT_URLS] == result.artifact_urls
    assert luml[LUML_COLLECTION_ID] == result.collection_id
    assert luml[LUML_ORBIT_ID] == "orbit1"
    assert luml[LUML_ORGANIZATION_ID] == "org1"
    # URLs are built from the template.
    assert result.artifact_urls[0].endswith(f"/artifacts/{result.artifact_ids[0]}")
    assert "org1" in result.artifact_urls[0]
    assert "orbit1" in result.artifact_urls[0]


# ---------------------------------------------------------------- multi-model


def test_multi_model_separate_artifacts(
    store: LumlTrackingStore, fake_client: FakeLumlClient, tmp_path: Path
) -> None:
    run_id = _start_run(store)
    _log_model(store, run_id, tmp_path, "a")
    _log_model(store, run_id, tmp_path, "b")

    result = sync_mod.sync(run_id, client=fake_client)

    assert result.status == UPLOAD_STATUS_UPLOADED
    # 2 models + 1 experiment = 3 artifacts.
    assert len(result.artifact_ids) == 3
    names = [c["name"] for c in fake_client.artifacts.upload_calls]
    assert names == ["a", "b", "run-in-fraud"]


# --------------------------------------------------------------- zero-model


def test_zero_model_experiment_only(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    run_id = _start_run(store)

    result = sync_mod.sync(run_id, client=fake_client)

    assert result.status == UPLOAD_STATUS_UPLOADED
    assert len(result.artifact_ids) == 1
    names = [c["name"] for c in fake_client.artifacts.upload_calls]
    assert names == ["run-in-fraud"]


# ---------------------------------------------------------------- separate mode


def test_separate_mode_forces_decoupled_artifacts(
    store: LumlTrackingStore,
    fake_client: FakeLumlClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from luml_mlflow import config as config_mod

    monkeypatch.setenv("LUML_MLFLOW_UPLOAD_MODE", "separate")
    config_mod.reset_settings_cache()

    run_id = _start_run(store)
    _log_model(store, run_id, tmp_path, "rf")

    result = sync_mod.sync(run_id, client=fake_client)

    assert result.status == UPLOAD_STATUS_UPLOADED
    # One model + one experiment artifact (the auto-mode would combine these).
    assert len(result.artifact_ids) == 2
    names = [c["name"] for c in fake_client.artifacts.upload_calls]
    assert names == ["rf", "run-in-fraud"]


# ---------------------------------------------------------------- collections


def test_collection_reuse_when_already_mixed(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    fake_client.collections.collections["existing"] = FakeCollection(
        id="existing", name="fraud", type="mixed"
    )
    run_id = _start_run(store)
    sync_mod.sync(run_id, client=fake_client)
    # No new collection was created.
    assert fake_client.collections.create_calls == []


def test_collection_conflict_raises_by_default(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    fake_client.collections.collections["x"] = FakeCollection(
        id="x", name="fraud", type="model"
    )
    run_id = _start_run(store)

    result = sync_mod.sync(run_id, client=fake_client)

    assert result.status == UPLOAD_STATUS_FAILED
    assert result.error is not None
    assert "not 'mixed'" in result.error
    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_FAILED


def test_collection_conflict_suffix_creates_mlflow_named(
    store: LumlTrackingStore,
    fake_client: FakeLumlClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from luml_mlflow import config as config_mod

    monkeypatch.setenv("LUML_MLFLOW_COLLECTION_CONFLICT", "suffix")
    config_mod.reset_settings_cache()

    fake_client.collections.collections["x"] = FakeCollection(
        id="x", name="fraud", type="model"
    )
    run_id = _start_run(store)

    result = sync_mod.sync(run_id, client=fake_client)
    assert result.status == UPLOAD_STATUS_UPLOADED
    assert len(fake_client.collections.create_calls) == 1
    assert fake_client.collections.create_calls[0]["name"] == "fraud (mlflow)"
    assert fake_client.collections.create_calls[0]["type"] == "mixed"


# ---------------------------------------------------------------- local-only


def test_local_only_target_skipped(temp_store: Path) -> None:
    local = LumlTrackingStore("luml://local")
    exp_id = local.create_experiment("local-test")
    run = local.create_run(exp_id, user_id="u", start_time=0, tags=[], run_name="r")

    result = sync_mod.sync(run.info.run_id)

    assert result.skipped_reason == "local-only target"
    assert (
        local._tracker.get_experiment_upload_status(run.info.run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


# ---------------------------------------------------------------- idempotency


def test_already_uploaded_run_is_skipped(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    run_id = _start_run(store)
    first = sync_mod.sync(run_id, client=fake_client)
    assert first.status == UPLOAD_STATUS_UPLOADED

    fake_client.artifacts.upload_calls.clear()
    second = sync_mod.sync(run_id, client=fake_client)

    assert second.skipped_reason == "already uploaded"
    # No new uploads or collections were touched.
    assert fake_client.artifacts.upload_calls == []


def test_force_re_syncs(store: LumlTrackingStore, fake_client: FakeLumlClient) -> None:
    run_id = _start_run(store)
    sync_mod.sync(run_id, client=fake_client)
    fake_client.artifacts.upload_calls.clear()

    result = sync_mod.sync(run_id, client=fake_client, force=True)

    assert result.skipped_reason is None
    assert result.status == UPLOAD_STATUS_UPLOADED
    assert len(fake_client.artifacts.upload_calls) == 1


# ---------------------------------------------------------------- failure path


def test_upload_failure_marks_failed_with_error(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    fake_client.artifacts.raise_on_upload = True
    run_id = _start_run(store)

    result = sync_mod.sync(run_id, client=fake_client)

    assert result.status == UPLOAD_STATUS_FAILED
    assert result.error == "simulated upload failure"
    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_FAILED
    meta = store._tracker.get_experiment_metadata(run_id)
    assert meta[META_LUML_INTERNAL][LUML_UPLOAD_ERROR] == "simulated upload failure"


# ---------------------------------------------------------------- transitions


def test_status_transitions(store: LumlTrackingStore) -> None:
    """``not_uploaded`` → ``uploading`` (mid-sync) → ``uploaded`` (on success)."""
    run_id = _start_run(store)

    class TransitionCapturingClient(FakeLumlClient):
        def __init__(self) -> None:
            super().__init__()
            self.captured: list[str] = []

    client = TransitionCapturingClient()
    transitions: list[str] = []
    real_upload = client.artifacts.upload

    def capture_then_upload(*args: Any, **kwargs: Any) -> FakeArtifact:
        transitions.append(store._tracker.get_experiment_upload_status(run_id))
        return real_upload(*args, **kwargs)

    client.artifacts.upload = capture_then_upload  # type: ignore[assignment]
    assert (
        store._tracker.get_experiment_upload_status(run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )
    sync_mod.sync(run_id, client=client)
    assert transitions == ["uploading"]
    assert store._tracker.get_experiment_upload_status(run_id) == UPLOAD_STATUS_UPLOADED


# ---------------------------------------------------------------- sync_experiment


def test_sync_experiment_syncs_all_runs(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    r1 = _start_run(store, "fraud")
    r2 = _start_run(store, "fraud")
    _start_run(store, "abuse")  # different group

    results = sync_mod.sync_experiment("fraud", client=fake_client)

    ids = {r.run_id for r in results}
    assert ids == {r1, r2}
    assert all(r.status == UPLOAD_STATUS_UPLOADED for r in results)


def test_sync_experiment_unknown_returns_empty(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    assert sync_mod.sync_experiment("nope", client=fake_client) == []


# ---------------------------------------------------------------- status()


def test_status_after_upload_returns_metadata(
    store: LumlTrackingStore, fake_client: FakeLumlClient
) -> None:
    run_id = _start_run(store)
    sync_mod.sync(run_id, client=fake_client)
    snap = sync_mod.status(run_id)
    assert snap.status == UPLOAD_STATUS_UPLOADED
    assert len(snap.artifact_ids) == 1
    assert len(snap.artifact_urls) == 1
    assert snap.collection_id is not None


def test_status_initial_run_is_not_uploaded(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    snap = sync_mod.status(run_id)
    assert snap.status == UPLOAD_STATUS_NOT_UPLOADED
    assert snap.artifact_ids == []


# ---------------------------------------------------------------- exports


def test_public_api_exports_sync() -> None:
    import luml_mlflow

    assert luml_mlflow.sync is sync_mod.sync
    assert luml_mlflow.sync_experiment is sync_mod.sync_experiment
    assert luml_mlflow.status is sync_mod.status
