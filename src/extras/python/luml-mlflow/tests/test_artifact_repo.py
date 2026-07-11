"""Tests for the luml-backed MLflow ``ArtifactRepository``."""

import hashlib
import tempfile
from pathlib import Path
from typing import Any

import pytest
from luml_mlflow import artifact_repo
from luml_mlflow.artifact_repo import (
    FNNX_SUFFIX,
    MLMODEL_FILE_NAME,
    LumlArtifactRepository,
)
from luml_mlflow.store import LumlTrackingStore

FAKE_FNNX_BYTES = b"FNNX\x00fake-converted-model"


@pytest.fixture
def fake_converter(monkeypatch: pytest.MonkeyPatch) -> bytes:
    """Stub the fnnx conversion seam with deterministic bytes.

    The real converter (``fnnx.extras.mlflow``) is exercised in ``test_fnnx``;
    here we only care about the repository's routing/storage behavior, so the
    seam is replaced to keep these tests fast and independent of real models.
    """

    def _convert(
        model_dir: Path, output_path: Path, *, name: str | None = None
    ) -> Path:
        output_path.write_bytes(FAKE_FNNX_BYTES)
        return output_path

    monkeypatch.setattr(artifact_repo, "convert_mlflow_model_to_fnnx", _convert)
    return FAKE_FNNX_BYTES


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


@pytest.fixture
def run_id(store: LumlTrackingStore) -> str:
    exp_id = store.create_experiment("fraud")
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r1",
    )
    return run.info.run_id


@pytest.fixture
def repo(store: LumlTrackingStore, run_id: str) -> LumlArtifactRepository:
    """Repo wired to a freshly-created run on the test store."""
    artifact_uri = store._artifact_uri_for_run(run_id)
    return LumlArtifactRepository(artifact_uri)


def _make_mlflow_model_dir(parent: Path, name: str = "model") -> Path:
    model_dir = parent / name
    model_dir.mkdir(parents=True)
    (model_dir / MLMODEL_FILE_NAME).write_text(
        "flavors:\n  python_function:\n    loader_module: m.l\n"
    )
    (model_dir / "weights.bin").write_bytes(b"\x00\x01\x02fake-weights")
    (model_dir / "conda.yaml").write_text("dependencies: []\n")
    return model_dir


def test_artifact_uri_resolves_run_id(
    repo: LumlArtifactRepository, run_id: str
) -> None:
    assert repo.run_id == run_id


def test_log_single_file_becomes_luml_attachment(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
) -> None:
    payload = b"\x89PNG\r\n\x1a\nfake-png-bytes"
    src = tmp_path / "plot.png"
    src.write_bytes(payload)

    repo.log_artifact(str(src))

    attachments = store._tracker.list_attachments(experiment_id=run_id)
    assert [a.name for a in attachments] == ["plot.png"]
    assert store._tracker.get_attachment("plot.png", experiment_id=run_id) == payload
    assert store._tracker.get_models(experiment_id=run_id) == []


def test_log_single_file_with_artifact_path_keeps_subdir(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
) -> None:
    src = tmp_path / "data.json"
    src.write_bytes(b'{"a": 1}')

    repo.log_artifact(str(src), artifact_path="reports/2024")

    attachments = store._tracker.list_attachments(experiment_id=run_id)
    assert [a.name for a in attachments] == ["reports/2024/data.json"]


def test_log_artifacts_dir_without_mlmodel_logs_all_as_attachments(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
) -> None:
    src = tmp_path / "logs"
    src.mkdir()
    (src / "a.txt").write_text("aaa")
    nested = src / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("bbb")

    repo.log_artifacts(str(src))

    names = sorted(
        a.name for a in store._tracker.list_attachments(experiment_id=run_id)
    )
    assert names == ["a.txt", "nested/b.txt"]
    assert store._tracker.get_models(experiment_id=run_id) == []


def test_log_artifacts_mlflow_model_dir_logs_one_luml_model(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
    fake_converter: bytes,
) -> None:
    model_dir = _make_mlflow_model_dir(tmp_path, name="sklearn-model")

    repo.log_artifacts(str(model_dir), artifact_path="my-model")

    models = store._tracker.get_models(experiment_id=run_id)
    assert len(models) == 1
    logged = models[0]
    assert logged.name == "my-model"
    assert logged.path is not None
    assert logged.path.endswith(FNNX_SUFFIX)

    stored = (store._tracker.backend.base_path / logged.path).read_bytes()
    assert stored == fake_converter

    # No attachments — the model contents are not double-written.
    assert store._tracker.list_attachments(experiment_id=run_id) == []


def test_log_artifacts_model_dir_without_path_names_by_experiment_and_hash(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
    fake_converter: bytes,
) -> None:
    model_dir = _make_mlflow_model_dir(tmp_path, name="model")

    # No artifact_path: the MLflow 3.x log_model path. The model must be named
    # <experiment>-<fnnx hash>, not the generic "model".
    repo.log_artifacts(str(model_dir))

    [logged] = store._tracker.get_models(experiment_id=run_id)
    digest = hashlib.sha256(fake_converter).hexdigest()[:12]
    assert logged.name == f"fraud-{digest}"  # "fraud" == the run's experiment
    assert logged.path is not None and logged.path.endswith(f"{digest}{FNNX_SUFFIX}")


def test_log_model_dir_uses_name_from_artifact_uri(
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
    fake_converter: bytes,
) -> None:
    # The MLflow LoggedModel path carries log_model(name=...) on the artifact
    # URI; that name wins over the <experiment>-<hash> fallback.
    repo = LumlArtifactRepository(store._artifact_uri_for_run(run_id, model_name="rf"))
    model_dir = _make_mlflow_model_dir(tmp_path, name="model")

    repo.log_artifacts(str(model_dir))

    [logged] = store._tracker.get_models(experiment_id=run_id)
    assert logged.name == "rf"
    assert logged.path is not None and logged.path.endswith(f"rf{FNNX_SUFFIX}")


def test_log_artifacts_model_dir_cleans_up_temp(
    repo: LumlArtifactRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_converter: bytes,
) -> None:
    created: list[Path] = []
    real_tempdir = tempfile.TemporaryDirectory

    def _tracking_tempdir(*args: Any, **kwargs: Any) -> Any:
        td = real_tempdir(*args, **kwargs)
        created.append(Path(td.name))
        return td

    monkeypatch.setattr(tempfile, "TemporaryDirectory", _tracking_tempdir)
    model_dir = _make_mlflow_model_dir(tmp_path, name="x")

    repo.log_artifacts(str(model_dir))

    assert created, "expected the model-conversion temp dir to have been created"
    for path in created:
        assert not path.exists(), f"temp dir {path} should have been cleaned up"


def test_list_artifacts_returns_attachments_and_models(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
    fake_converter: bytes,
) -> None:
    (tmp_path / "loss.csv").write_text("step,value\n0,0.5\n")
    repo.log_artifact(str(tmp_path / "loss.csv"))
    model_dir = _make_mlflow_model_dir(tmp_path, name="m")
    repo.log_artifacts(str(model_dir), artifact_path="best-model")

    listing = repo.list_artifacts()
    paths = {fi.path for fi in listing}
    assert "loss.csv" in paths
    assert any(p.endswith(FNNX_SUFFIX) for p in paths)
    for fi in listing:
        assert not fi.is_dir


def test_list_artifacts_buckets_subdirectories(
    repo: LumlArtifactRepository,
    tmp_path: Path,
) -> None:
    (tmp_path / "a.txt").write_text("a")
    repo.log_artifact(str(tmp_path / "a.txt"), artifact_path="reports/q1")
    repo.log_artifact(str(tmp_path / "a.txt"), artifact_path="reports/q2")
    (tmp_path / "top.txt").write_text("top")
    repo.log_artifact(str(tmp_path / "top.txt"))

    root = {(fi.path, fi.is_dir) for fi in repo.list_artifacts()}
    assert ("top.txt", False) in root
    assert ("reports", True) in root

    nested = {fi.path for fi in repo.list_artifacts("reports")}
    assert nested == {"reports/q1", "reports/q2"}


def test_download_attachment_round_trips(
    repo: LumlArtifactRepository,
    tmp_path: Path,
) -> None:
    payload = b"some-binary-content-1234"
    src = tmp_path / "blob.bin"
    src.write_bytes(payload)
    repo.log_artifact(str(src))

    dst = tmp_path / "downloaded.bin"
    repo._download_file("blob.bin", str(dst))

    assert dst.read_bytes() == payload


def test_download_model_round_trips(
    repo: LumlArtifactRepository,
    store: LumlTrackingStore,
    run_id: str,
    tmp_path: Path,
    fake_converter: bytes,
) -> None:
    model_dir = _make_mlflow_model_dir(tmp_path, name="m")
    repo.log_artifacts(str(model_dir))

    [model] = store._tracker.get_models(experiment_id=run_id)
    assert model.path is not None
    remote = Path(model.path).name

    dst = tmp_path / "downloaded.fnnx"
    repo._download_file(remote, str(dst))

    assert dst.read_bytes() == fake_converter


def test_local_only_artifact_uri_still_writes_locally(
    temp_store: Path,
    tmp_path: Path,
) -> None:
    """Local-only target is still backed by the same local tracker."""
    assert temp_store.exists() or not temp_store.exists()  # fixture activation
    store = LumlTrackingStore("luml://local")
    exp_id = store.create_experiment("local-only")
    run = store.create_run(exp_id, user_id="u", start_time=0, tags=[], run_name="r")
    repo = LumlArtifactRepository(store._artifact_uri_for_run(run.info.run_id))

    src = tmp_path / "p.txt"
    src.write_text("local")
    repo.log_artifact(str(src))

    attachments = store._tracker.list_attachments(experiment_id=run.info.run_id)
    assert [a.name for a in attachments] == ["p.txt"]


def test_repo_rejects_non_luml_scheme() -> None:
    with pytest.raises(ValueError, match="luml://"):
        LumlArtifactRepository("file:///tmp/whatever")


def test_repo_rejects_malformed_artifact_uri() -> None:
    with pytest.raises(ValueError, match="runs/<run_id>/artifacts"):
        LumlArtifactRepository("luml://org1/orbit1/foo/bar")
