import io
import zipfile
from pathlib import Path

import pytest

from luml.artifacts._base import ArtifactManifest
from luml.artifacts.experiment import (
    ExperimentReference,
    save_experiment,
)
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def experiment_with_data(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="test-exp", tags=["test", "unit"])
    tracker.log_static("learning_rate", 0.001, experiment_id=exp_id)
    tracker.log_dynamic("loss", 0.5, step=0, experiment_id=exp_id)
    tracker.log_dynamic("loss", 0.3, step=1, experiment_id=exp_id)
    tracker.log_attachment("config.json", '{"key": "value"}', experiment_id=exp_id)
    tracker.end_experiment(exp_id)
    return tracker, exp_id


def test_save_experiment_returns_reference(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert isinstance(ref, ExperimentReference)
    assert Path(ref.path).exists()


def test_save_experiment_auto_path(
    experiment_with_data: tuple[ExperimentTracker, str],
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id)
    assert Path(ref.path).exists()
    Path(ref.path).unlink()


def test_tar_contains_expected_files(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    files = ref.list_files()
    assert "manifest.json" in files
    assert "exp.db.zip" in files
    assert "attachments.tar" in files
    assert "attachments.index.json" in files


def test_db_zip_contains_exp_db(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    db_zip_bytes = ref.extract_file("exp.db.zip")
    with zipfile.ZipFile(io.BytesIO(db_zip_bytes)) as zf:
        assert "exp.db" in zf.namelist()


def test_manifest_content(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    manifest = ref.get_manifest()
    assert isinstance(manifest, ArtifactManifest)
    assert manifest.artifact_type == "experiment"
    assert manifest.name == "test-exp"
    assert manifest.payload.local_experiment_id == exp_id
    assert manifest.payload.tags == ["test", "unit"]


def test_reference_validates(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert ref.validate() is True


def test_save_without_attachments(tracker: ExperimentTracker, tmp_path: Path) -> None:
    exp_id = tracker.start_experiment()
    tracker.log_static("key", "value", experiment_id=exp_id)
    tracker.end_experiment(exp_id)

    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert ref.validate() is True
    assert "manifest.json" in ref.list_files()
    assert "exp.db.zip" in ref.list_files()
