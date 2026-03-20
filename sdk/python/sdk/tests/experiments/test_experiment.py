import io
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from luml.artifacts.model import ModelReference
from luml.experiments.backends.data_types import (
    Experiment,
)
from luml.experiments.tracker import ExperimentTracker
from tests.conftest import _exp_db, _meta_db


def _setup_group(tracker: ExperimentTracker) -> str:
    tracker.start_experiment(name="exp", group="sort-test-group")
    tracker.log_dynamic("loss", 0.5, step=0)
    tracker.log_static("lr", 0.01)
    return next(g.id for g in tracker.list_groups() if g.name == "sort-test-group")


class TestLogExperiment:
    def test_start_creates_retrievable_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="my_exp")

        exp = tracker.get_experiment_record(exp_id)

        assert exp is not None
        assert exp.id == exp_id
        assert exp.name == "my_exp"
        assert exp.status == "active"

    def test_start_creates_experiment_db_file(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        exp_id = tracker.start_experiment()
        assert (tmp_path / "experiments" / exp_id / "exp.db").exists()

    def test_start_with_custom_id(self, tracker: ExperimentTracker) -> None:
        experiment_id = "my-fixed-id"

        exp_id = tracker.start_experiment(experiment_id=experiment_id, name="fixed")
        assert exp_id == experiment_id

        exp = tracker.get_experiment_record(experiment_id)
        assert exp is not None

    def test_start_with_tags_persists(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="tagged", tags=["v1", "prod"])

        exp = tracker.get_experiment_record(exp_id)

        assert exp.tags == ["v1", "prod"]

    def test_start_with_group_creates_group_and_links(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="grouped", group="cv-experiments")

        groups = tracker.list_groups()
        group = next((g for g in groups if g.name == "cv-experiments"), None)
        assert group is not None

        exp = tracker.get_experiment_record(exp_id)
        assert exp.group_id == group.id

    def test_start_sets_current_experiment_id(self, tracker: ExperimentTracker) -> None:
        assert tracker.current_experiment_id is None
        exp_id = tracker.start_experiment()
        assert tracker.current_experiment_id == exp_id

    def test_end_sets_status_completed(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.end_experiment(exp_id)

        exp = tracker.get_experiment_record(exp_id)
        assert exp.status == "completed"

    def test_end_clears_current_experiment_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.end_experiment(exp_id)
        assert tracker.current_experiment_id is None

    def test_end_with_explicit_id_does_not_clear_current(
        self,
        tracker: ExperimentTracker,
    ) -> None:
        id1 = tracker.start_experiment(name="current")
        id2 = tracker.start_experiment(name="other")
        tracker.end_experiment(id1)
        assert tracker.current_experiment_id == id2

    def test_end_saves_static_params(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("lr", 0.01)
        tracker.log_static("batch", 64)
        tracker.end_experiment(exp_id)

        exp = tracker.get_experiment_record(exp_id)
        assert exp.static_params["lr"] == pytest.approx(0.01)
        assert exp.static_params["batch"] == 64

    def test_end_saves_dynamic_params_last_values(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 1.0, step=0)
        tracker.log_dynamic("loss", 0.4, step=1)
        tracker.log_dynamic("acc", 0.95, step=1)
        tracker.end_experiment(exp_id)

        exp = tracker.get_experiment_record(exp_id)
        assert exp.dynamic_params["loss"] == pytest.approx(0.4)
        assert exp.dynamic_params["acc"] == pytest.approx(0.95)

    def test_end_records_duration(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.end_experiment(exp_id)

        exp = tracker.get_experiment_record(exp_id)
        assert exp.duration is not None
        assert exp.duration >= 0.0

    def test_end_without_active_experiment_raises(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.end_experiment()


class TestExperimentWithModel:
    def test_logged_model_appears_in_get_models(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        model_ref = ModelReference(str(dummy_model_file))
        tracker.log_model(model_ref, name="baseline", tags=["v1"])

        models = tracker.get_models(exp_id)
        assert len(models) == 1
        assert models[0].name == "baseline"
        assert models[0].tags == ["v1"]
        assert models[0].experiment_id == exp_id

    def test_two_model_versions_have_distinct_ids(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        second_model_file = tmp_path / "model_v2.luml"
        with tarfile.open(second_model_file, "w") as tar:
            data = b"updated weights"
            info = tarfile.TarInfo(name="model.bin")
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))

        tracker.log_model(ModelReference(str(dummy_model_file)), name="v1")
        tracker.log_model(ModelReference(str(second_model_file)), name="v2")

        models = tracker.get_models(exp_id)
        assert len(models) == 2
        assert len({m.id for m in models}) == 2
        assert {m.name for m in models} == {"v1", "v2"}

    def test_full_experiment_with_model_params_and_metrics(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        """A realistic scenario: log hyperparams, train metrics, a model, and
        verify get_experiment returns everything together."""
        tracker, exp_id = tracker_with_experiment

        tracker.log_static("lr", 0.01)
        tracker.log_static("architecture", "resnet18")
        tracker.log_static("batch_size", 64)

        for step in range(5):
            tracker.log_dynamic("loss", 1.0 - step * 0.15, step=step)
            tracker.log_dynamic("acc", 0.5 + step * 0.1, step=step)

        tracker.log_model(
            ModelReference(str(dummy_model_file)), name="final-model", tags=["prod"]
        )

        tracker.end_experiment(exp_id)

        data = tracker.get_experiment(exp_id)
        assert data.static_params["lr"] == pytest.approx(0.01)
        assert data.static_params["architecture"] == "resnet18"
        assert len(data.dynamic_metrics["loss"]) == 5
        assert len(data.dynamic_metrics["acc"]) == 5

        exp_record = tracker.get_experiment_record(exp_id)
        assert exp_record.status == "completed"
        assert exp_record.dynamic_params["loss"] == pytest.approx(0.4)
        assert exp_record.dynamic_params["acc"] == pytest.approx(0.9)

        models = tracker.get_models(exp_id)
        assert len(models) == 1
        assert models[0].name == "final-model"


class TestGetExperiment:
    def test_get_experiment_returns_all_data(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_static("lr", 0.001)
        tracker.log_static("arch", "resnet")
        tracker.log_dynamic("loss", 0.5, step=0)
        tracker.log_dynamic("loss", 0.3, step=1)
        tracker.log_attachment("note.txt", "hello")

        data = tracker.get_experiment(exp_id)

        assert data.experiment_id == exp_id
        assert data.metadata.name == "scenario_exp"
        assert data.metadata.status == "active"
        assert data.static_params["lr"] == 0.001
        assert data.static_params["arch"] == "resnet"
        assert len(data.dynamic_metrics["loss"]) == 2
        assert data.dynamic_metrics["loss"][0] == {"value": 0.5, "step": 0}
        assert data.dynamic_metrics["loss"][1] == {"value": 0.3, "step": 1}
        assert "note.txt" in data.attachments

    def test_get_experiment_empty_returns_defaults(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        data = tracker.get_experiment(exp_id)

        assert data.experiment_id == exp_id
        assert data.static_params == {}
        assert data.dynamic_metrics == {}
        assert data.attachments == {}

    def test_get_experiment_not_found(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError):
            tracker.get_experiment("nonexistent-id")


class TestListExperiments:
    def test_list_experiments_metadata_matches_db(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        id1 = tracker.start_experiment(name="exp_1", tags=["baseline"])
        tracker.log_static("lr", 0.01)
        tracker.end_experiment(id1)

        id2 = tracker.start_experiment(name="exp_2")
        tracker.end_experiment(id2)

        experiments = tracker.list_experiments()
        ids = {e.id for e in experiments}
        assert id1 in ids
        assert id2 in ids

        conn = _meta_db(tmp_path)
        db_count = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        conn.close()
        assert db_count == len(experiments)

        exp1 = next(e for e in experiments if e.id == id1)
        assert isinstance(exp1, Experiment)
        assert exp1.name == "exp_1"
        assert exp1.status == "completed"
        assert exp1.tags == ["baseline"]
        assert exp1.static_params == {"lr": 0.01}

    def test_list_experiments_running_status(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="active")

        experiments = tracker.list_experiments()
        exp = next(e for e in experiments if e.id == exp_id)
        assert exp.status == "active"

        tracker.end_experiment(exp_id)

    def test_list_experiments_dynamic_params_after_end(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="metrics_exp")
        tracker.log_dynamic("loss", 0.5, step=0)
        tracker.log_dynamic("loss", 0.2, step=1)
        tracker.log_dynamic("acc", 0.9, step=0)
        tracker.end_experiment(exp_id)

        experiments = tracker.list_experiments()
        exp = next(e for e in experiments if e.id == exp_id)
        assert exp.dynamic_params == {"loss": 0.2, "acc": 0.9}


class TestDeleteExperiment:
    def test_delete_removes_from_meta_db(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.end_experiment(exp_id)

        tracker.delete_experiment(exp_id)

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT id FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        conn.close()
        assert row is None

    def test_delete_removes_experiment_directory(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("file.txt", "data")
        tracker.end_experiment(exp_id)

        exp_dir = tmp_path / "experiments" / exp_id
        assert exp_dir.exists()

        tracker.delete_experiment(exp_id)

        assert not exp_dir.exists()

    def test_delete_makes_data_inaccessible(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_static("key", "value")
        tracker.end_experiment(exp_id)

        tracker.delete_experiment(exp_id)

        with pytest.raises(ValueError):
            tracker.get_experiment(exp_id)

    def test_delete_removes_from_listing(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.end_experiment(exp_id)

        tracker.delete_experiment(exp_id)

        experiments = tracker.list_experiments()
        assert all(e.id != exp_id for e in experiments)


class TestGetExperimentMetricHistory:
    def test_returns_logged_steps_in_order(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_dynamic("loss", 1.0, step=0, experiment_id=exp_id)
        tracker.log_dynamic("loss", 0.5, step=1, experiment_id=exp_id)
        tracker.log_dynamic("loss", 0.2, step=2, experiment_id=exp_id)

        history = tracker.get_experiment_metric_history(exp_id, "loss")

        assert len(history) == 3
        assert history[0]["step"] == 0
        assert history[0]["value"] == pytest.approx(1.0)
        assert history[1]["step"] == 1
        assert history[1]["value"] == pytest.approx(0.5)
        assert history[2]["step"] == 2
        assert history[2]["value"] == pytest.approx(0.2)

    def test_each_entry_has_required_keys(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("acc", 0.9, step=1, experiment_id=exp_id)

        history = tracker.get_experiment_metric_history(exp_id, "acc")

        assert len(history) == 1
        entry = history[0]
        assert "value" in entry
        assert "step" in entry
        assert "logged_at" in entry

    def test_returns_empty_list_for_unknown_key(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        history = tracker.get_experiment_metric_history(exp_id, "nonexistent")

        assert history == []

    def test_only_returns_matching_key(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("loss", 0.5, step=1, experiment_id=exp_id)
        tracker.log_dynamic("acc", 0.9, step=1, experiment_id=exp_id)

        history = tracker.get_experiment_metric_history(exp_id, "loss")

        assert len(history) == 1
        assert history[0]["value"] == pytest.approx(0.5)

    def test_value_step_and_logged_at_are_populated(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_dynamic("f1", 0.75, step=5, experiment_id=exp_id)

        history = tracker.get_experiment_metric_history(exp_id, "f1")

        assert len(history) == 1
        assert history[0]["value"] == pytest.approx(0.75)
        assert history[0]["step"] == 5
        assert history[0]["logged_at"] is not None

    def test_end_experiment_captures_last_step_values(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        for step in range(10):
            tracker.log_dynamic("loss", 1.0 - step * 0.1, step=step)
            tracker.log_dynamic("val_loss", 1.2 - step * 0.1, step=step)

        tracker.end_experiment(exp_id)

        exp = tracker.get_experiment_record(exp_id)
        assert exp.dynamic_params["loss"] == pytest.approx(0.1)
        assert exp.dynamic_params["val_loss"] == pytest.approx(0.3)


class TestGetAttachment:
    def test_get_attachment_text_roundtrip(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_attachment("config.json", '{"lr": 0.001}')

        result = tracker.get_attachment("config.json")
        assert result == b'{"lr": 0.001}'

        file_path = tmp_path / "experiments" / exp_id / "attachments" / "config.json"
        assert file_path.exists()
        assert file_path.read_text() == '{"lr": 0.001}'

    def test_get_attachment_binary_roundtrip(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        payload = b"\x00\x01\x02\xff"

        tracker.log_attachment("data.bin", payload, binary=True)

        result = tracker.get_attachment("data.bin")
        assert result == payload

        file_path = tmp_path / "experiments" / exp_id / "attachments" / "data.bin"
        assert file_path.exists()
        assert file_path.read_bytes() == payload

    def test_get_attachment_persisted_in_db(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_attachment("file.txt", "content", experiment_id=exp_id)

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT name, file_path FROM attachments WHERE name = 'file.txt'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "file.txt"
        assert row[1] == "file.txt"

    def test_get_attachment_not_found(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        with pytest.raises(ValueError, match="not found"):
            tracker.get_attachment("does_not_exist.txt")

    def test_get_attachment_requires_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.get_attachment("missing.txt")


class TestLogExperimentAttachment:
    def test_text_file_saved_to_disk(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("notes.txt", "hello world")

        file_path = tmp_path / "experiments" / exp_id / "attachments" / "notes.txt"
        assert file_path.exists()
        assert file_path.read_text() == "hello world"

    def test_text_file_recorded(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("config.json", '{"key": "val"}')

        data = tracker.get_experiment(exp_id)
        assert "config.json" in data.attachments

    def test_binary_file_saved_to_disk(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        payload = b"\x00\x01\x02\xff\xfe"
        tracker.log_attachment("data.bin", payload, binary=True)

        file_path = tmp_path / "experiments" / exp_id / "attachments" / "data.bin"
        assert file_path.exists()
        assert file_path.read_bytes() == payload

    def test_nested_path_creates_subdirectory(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("plots/loss_curve.svg", "<svg/>")

        file_path = (
            tmp_path
            / "experiments"
            / exp_id
            / "attachments"
            / "plots"
            / "loss_curve.svg"
        )
        assert file_path.exists()
        assert file_path.read_text() == "<svg/>"

    def test_overwrite_existing_attachment(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("report.txt", "version 1")
        tracker.log_attachment("report.txt", "version 2")

        file_path = tmp_path / "experiments" / exp_id / "attachments" / "report.txt"
        assert file_path.read_text() == "version 2"
        assert tracker.get_attachment("report.txt") == b"version 2"

    def test_multiple_attachments_stored_independently(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("a.txt", "aaa")
        tracker.log_attachment("b.txt", "bbb")
        tracker.log_attachment("c.txt", "ccc")

        data = tracker.get_experiment(exp_id)
        assert set(data.attachments.keys()) == {"a.txt", "b.txt", "c.txt"}

    def test_get_attachment_returns_bytes(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        tracker.log_attachment("result.json", '{"score": 0.99}')

        result = tracker.get_attachment("result.json")
        assert result == b'{"score": 0.99}'

    def test_get_attachment_not_found_raises(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        with pytest.raises(ValueError, match="not found"):
            tracker.get_attachment("nonexistent.txt")

    def test_requires_active_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_attachment("file.txt", "data")

    def test_explicit_experiment_id(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="e1")
        other_id = tracker.start_experiment(name="e2")

        tracker.log_attachment("note.txt", "for e1", experiment_id=exp_id)

        data_exp = tracker.get_experiment(exp_id)
        data_other = tracker.get_experiment(other_id)

        assert "note.txt" in data_exp.attachments
        assert "note.txt" not in data_other.attachments

    def test_attachment_in_get_experiment_data(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_attachment("config.yaml", "lr: 0.001")

        data = tracker.get_experiment(exp_id)
        assert "config.yaml" in data.attachments


class TestLinkToModel:
    def test_raises_without_active_experiment(
        self, tracker: ExperimentTracker, dummy_model_file: Path
    ) -> None:
        model_ref = ModelReference(str(dummy_model_file))

        with pytest.raises(ValueError, match="No active experiment"):
            tracker.link_to_model(model_ref)

    def test_raises_when_export_attachments_returns_none(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, _ = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "export_attachments", lambda _: None)
        model_ref = ModelReference(str(dummy_model_file))

        with pytest.raises(ValueError, match="No attachments found"):
            tracker.link_to_model(model_ref)

    def test_raises_for_non_disk_exp_db(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, _ = tracker_with_experiment
        tracker.log_attachment("file.txt", "data")
        monkeypatch.setattr(
            tracker.backend, "export_experiment_db", lambda _: MagicMock()
        )
        model_ref = ModelReference(str(dummy_model_file))

        with pytest.raises(NotImplementedError):
            tracker.link_to_model(model_ref)

    def test_metadata_appended_to_model_file(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, _ = tracker_with_experiment
        tracker.log_attachment("config.txt", "lr=0.01")
        model_ref = ModelReference(str(dummy_model_file))

        tracker.link_to_model(model_ref)

        with tarfile.open(dummy_model_file, "r") as tar:
            names = tar.getnames()

        assert any(n.startswith("meta-") and n.endswith(".json") for n in names)
        assert any(n.endswith("exp.db.zip") for n in names)
        assert any(n.endswith("attachments.tar") for n in names)
        assert any(n.endswith("attachments.index.json") for n in names)

    def test_uses_explicit_experiment_id(
        self,
        tracker: ExperimentTracker,
        dummy_model_file: Path,
    ) -> None:
        id1 = tracker.start_experiment(name="exp1")
        id2 = tracker.start_experiment(name="exp2")  # noqa: F841 — becomes current
        tracker.log_attachment("note.txt", "data", experiment_id=id1)
        model_ref = ModelReference(str(dummy_model_file))

        tracker.link_to_model(model_ref, experiment_id=id1)

        with tarfile.open(dummy_model_file, "r") as tar:
            names = tar.getnames()

        assert any(n.startswith("meta-") and n.endswith(".json") for n in names)
        assert any(n.endswith("exp.db.zip") for n in names)

    def test_temp_zip_cleaned_up(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, _ = tracker_with_experiment
        tracker.log_attachment("file.txt", "data")
        captured: list[str] = []

        original_ntf = tempfile.NamedTemporaryFile

        def capturing_ntf(*args, **kwargs):
            ntf = original_ntf(*args, **kwargs)
            captured.append(ntf.name)
            return ntf

        monkeypatch.setattr(
            "luml.experiments.tracker.NamedTemporaryFile", capturing_ntf
        )
        model_ref = ModelReference(str(dummy_model_file))

        tracker.link_to_model(model_ref)

        assert len(captured) == 1
        assert not Path(captured[0]).exists()


class TestResolveExperimentSortColumn:
    def test_returns_none_for_standard_column(self, tracker: ExperimentTracker) -> None:
        group_id = _setup_group(tracker)

        for col in ("name", "created_at", "status", "tags", "duration"):
            assert tracker.resolve_experiment_sort_column(group_id, col) is None

    def test_returns_dynamic_params_for_metric_key(
        self, tracker: ExperimentTracker
    ) -> None:
        group_id = _setup_group(tracker)

        result = tracker.resolve_experiment_sort_column(group_id, "loss")

        assert result == "dynamic_params"

    def test_returns_static_params_for_param_key(
        self, tracker: ExperimentTracker
    ) -> None:
        group_id = _setup_group(tracker)

        result = tracker.resolve_experiment_sort_column(group_id, "lr")

        assert result == "static_params"

    def test_raises_for_unknown_sort_key(self, tracker: ExperimentTracker) -> None:
        group_id = _setup_group(tracker)

        with pytest.raises(ValueError, match="Invalid sort_by"):
            tracker.resolve_experiment_sort_column(group_id, "unknown_key")


def _make_group(tracker: ExperimentTracker, name: str = "g") -> str:
    """Create a group via an experiment and return the group_id."""
    tracker.start_experiment(group=name)
    return next(g.id for g in tracker.list_groups() if g.name == name)


class TestUpdateExperiment:
    def test_updates_name(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.update_experiment(exp_id, name="new_name")

        assert result is not None
        assert result.name == "new_name"

    def test_updates_description(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.update_experiment(exp_id, description="my desc")

        assert result is not None
        assert result.description == "my desc"

    def test_updates_tags(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.update_experiment(exp_id, tags=["v2", "prod"])

        assert result is not None
        assert result.tags == ["v2", "prod"]

    def test_updates_all_fields(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.update_experiment(
            exp_id, name="new", description="desc", tags=["x"]
        )

        assert result is not None
        assert result.name == "new"
        assert result.description == "desc"
        assert result.tags == ["x"]

    def test_returns_current_experiment_when_no_fields_provided(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.update_experiment(exp_id)

        assert result is not None
        assert result.id == exp_id
        assert result.name == "scenario_exp"

    def test_returns_none_for_nonexistent_experiment_with_fields(
        self, tracker: ExperimentTracker
    ) -> None:
        result = tracker.update_experiment("nonexistent-id", name="x")

        assert result is None

    def test_returns_none_for_nonexistent_experiment_without_fields(
        self, tracker: ExperimentTracker
    ) -> None:
        result = tracker.update_experiment("nonexistent-id")

        assert result is None

    def test_update_persists_in_listing(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.update_experiment(exp_id, name="persisted", tags=["saved"])

        experiments = tracker.list_experiments()
        exp = next(e for e in experiments if e.id == exp_id)
        assert exp.name == "persisted"
        assert exp.tags == ["saved"]
