import io
import json
import sqlite3
import tarfile
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from luml.artifacts.model import ModelReference
from luml.experiments.backends._data_types import (
    Experiment,
    Group,
    Model,
)
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def tracker_with_experiment(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="test_exp")
    return tracker, exp_id


@pytest.fixture
def dummy_model_file(tmp_path: Path) -> Path:
    model_path = tmp_path / "dummy_model.luml"
    with tarfile.open(model_path, "w") as tar:
        data = b"fake model data"
        info = tarfile.TarInfo(name="model.bin")
        info.size = len(data)
        tar.addfile(info, fileobj=io.BytesIO(data))
    return model_path


def _make_fake_instance(module: str) -> object:
    cls = type("FakeModel", (), {"__module__": module})
    return cls()


def _mock_flavor(
    monkeypatch: pytest.MonkeyPatch,
    flavor: str,
    module_path: str,
    func_name: str,
    fake_ref: ModelReference,
) -> MagicMock:
    mock_save = MagicMock(return_value=fake_ref)
    fake_module = ModuleType(module_path)
    setattr(fake_module, func_name, mock_save)
    monkeypatch.setitem(
        __import__("sys").modules,
        module_path,
        fake_module,
    )
    return mock_save


def _exp_db(tmp_path: Path, exp_id: str) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "experiments" / exp_id / "exp.db")


def _meta_db(tmp_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "experiments" / "meta.db")


class TestLogSpan:
    def test_log_span_persists_to_db(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        start = 1_000_000_000
        end = 2_000_000_000

        tracker.log_span(
            trace_id="trace_1",
            span_id="span_1",
            name="preprocess",
            start_time_unix_nano=start,
            end_time_unix_nano=end,
            attributes={"rows": 100},
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT trace_id, span_id, name, start_time_unix_nano, "
            "end_time_unix_nano, attributes FROM spans"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "trace_1"
        assert row[1] == "span_1"
        assert row[2] == "preprocess"
        assert row[3] == start
        assert row[4] == end
        assert json.loads(row[5]) == {"rows": 100}

    def test_log_span_with_parent_persists_hierarchy(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000

        tracker.log_span(
            trace_id="t1",
            span_id="root",
            name="pipeline",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 2_000_000,
        )
        tracker.log_span(
            trace_id="t1",
            span_id="child",
            name="step_1",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1_000_000,
            parent_span_id="root",
        )

        conn = _exp_db(tmp_path, exp_id)
        rows = conn.execute(
            "SELECT span_id, parent_span_id FROM spans ORDER BY span_id"
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        by_id = {r[0]: r[1] for r in rows}
        assert by_id["child"] == "root"
        assert by_id["root"] is None

    def test_log_span_all_optional_fields_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        events = [{"name": "start", "timestamp": now}]
        links = [{"trace_id": "other_trace", "span_id": "other_span"}]

        tracker.log_span(
            trace_id="t2",
            span_id="s2",
            name="inference",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 500_000,
            parent_span_id="parent_span",
            kind=2,
            status_code=1,
            status_message="OK",
            attributes={"model": "rf_v1"},
            events=events,
            links=links,
            trace_flags=1,
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT parent_span_id, kind, status_code, status_message, "
            "attributes, events, links, trace_flags FROM spans"
        ).fetchone()
        conn.close()

        assert row[0] == "parent_span"
        assert row[1] == 2
        assert row[2] == 1
        assert row[3] == "OK"
        assert json.loads(row[4]) == {"model": "rf_v1"}
        assert json.loads(row[5]) == events
        assert json.loads(row[6]) == links
        assert row[7] == 1

    def test_log_span_requires_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_span(
                trace_id="t",
                span_id="s",
                name="op",
                start_time_unix_nano=0,
                end_time_unix_nano=1,
            )


class TestLogEvalSample:
    def test_log_eval_sample_all_fields_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_eval_sample(
            eval_id="eval_001",
            dataset_id="ds_1",
            inputs={"prompt": "hello"},
            outputs={"response": "hi"},
            references={"expected": "hi there"},
            scores={"bleu": 0.8},
            metadata={"latency_ms": 42},
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT id, dataset_id, inputs, outputs, refs, scores, metadata FROM evals"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "eval_001"
        assert row[1] == "ds_1"
        assert json.loads(row[2]) == {"prompt": "hello"}
        assert json.loads(row[3]) == {"response": "hi"}
        assert json.loads(row[4]) == {"expected": "hi there"}
        assert json.loads(row[5]) == {"bleu": 0.8}
        assert json.loads(row[6]) == {"latency_ms": 42}

    def test_log_eval_sample_minimal_leaves_optional_null(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_eval_sample(
            eval_id="eval_002",
            dataset_id="ds_1",
            inputs={"x": 1},
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT outputs, refs, scores, metadata FROM evals WHERE id = 'eval_002'"
        ).fetchone()
        conn.close()

        assert row is not None
        assert all(col is None for col in row)

    def test_log_eval_sample_requires_experiment(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_eval_sample(eval_id="e", dataset_id="d", inputs={"x": 1})


class TestLinkEvalSampleToTrace:
    def test_link_persists_bridge_row(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = time.time_ns()

        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_1", inputs={"x": 1})
        tracker.log_span(
            trace_id="trace_link",
            span_id="span_link",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 100,
        )
        tracker.link_eval_sample_to_trace(
            eval_dataset_id="ds_1",
            eval_id="e1",
            trace_id="trace_link",
        )

        conn = _exp_db(tmp_path, exp_id)
        row = conn.execute(
            "SELECT eval_dataset_id, eval_id, trace_id FROM eval_traces_bridge"
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "ds_1"
        assert row[1] == "e1"
        assert row[2] == "trace_link"

    def test_link_requires_existing_eval(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        now = time.time_ns()
        tracker.log_span(
            trace_id="t",
            span_id="s",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1,
        )

        with pytest.raises(ValueError, match="not found"):
            tracker.link_eval_sample_to_trace(
                eval_dataset_id="ds", eval_id="missing", trace_id="t"
            )

    def test_link_requires_existing_trace(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, _ = tracker_with_experiment
        tracker.log_eval_sample(eval_id="e1", dataset_id="ds_1", inputs={"x": 1})

        with pytest.raises(ValueError, match="not found"):
            tracker.link_eval_sample_to_trace(
                eval_dataset_id="ds_1", eval_id="e1", trace_id="missing"
            )

    def test_link_requires_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.link_eval_sample_to_trace(
                eval_dataset_id="ds", eval_id="e", trace_id="t"
            )


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
        assert data.metadata.name == "test_exp"
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


class TestGroups:
    def test_create_group_persists_to_meta_db(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        group = tracker.create_group("my_group", description="test group")

        assert isinstance(group, Group)
        assert group.name == "my_group"
        assert group.description == "test group"

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT id, name, description FROM experiment_groups WHERE name = ?",
            ("my_group",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == group.id
        assert row[1] == "my_group"
        assert row[2] == "test group"

    def test_create_group_without_description(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        group = tracker.create_group("bare_group")

        assert group.description is None

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT description FROM experiment_groups WHERE name = ?",
            ("bare_group",),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] is None

    def test_create_group_idempotent(self, tracker: ExperimentTracker) -> None:
        g1 = tracker.create_group("same_name", description="first")
        g2 = tracker.create_group("same_name", description="second")

        assert g1.id == g2.id

    def test_list_groups_returns_all(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        tracker.create_group("group_a", description="A")
        tracker.create_group("group_b", description="B")

        groups = tracker.list_groups()
        names = {g.name for g in groups}
        assert "group_a" in names
        assert "group_b" in names

        conn = _meta_db(tmp_path)
        count = conn.execute("SELECT COUNT(*) FROM experiment_groups").fetchone()[0]
        conn.close()

        assert count == len(groups)

    def test_list_groups_empty(self, tracker: ExperimentTracker) -> None:
        groups = tracker.list_groups()
        assert isinstance(groups, list)
        assert len(groups) == 0


class TestGetModels:
    def test_get_models_requires_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.get_models()

    def test_get_models_empty(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, _ = tracker_with_experiment
        models = tracker.get_models()
        assert models == []


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


# ── log_model (per-flavor e2e) ───────────────────────────────────────

# (flavor, module_path, func_name, model_module_prefix)
_FLAVOR_PARAMS = [
    (
        "sklearn",
        "luml.integrations.sklearn.packaging",
        "save_sklearn",
        "sklearn.ensemble._forest",
    ),
    (
        "xgboost",
        "luml.integrations.xgboost.packaging",
        "save_xgboost",
        "xgboost.sklearn",
    ),
    (
        "lightgbm",
        "luml.integrations.lightgbm.packaging",
        "save_lightgbm",
        "lightgbm.sklearn",
    ),
    (
        "catboost",
        "luml.integrations.catboost.packaging",
        "save_catboost",
        "catboost.core",
    ),
    (
        "langgraph",
        "luml.integrations.langgraph.packaging",
        "save_langgraph",
        "langgraph.graph.state",
    ),
]

_FLAVORS_WITH_INPUTS = {"sklearn", "xgboost", "lightgbm"}
_FLAVORS_WITHOUT_INPUTS = {"catboost", "langgraph"}


class TestLogModel:
    @pytest.mark.parametrize(
        "flavor, module_path, func_name, model_module",
        _FLAVOR_PARAMS,
        ids=[p[0] for p in _FLAVOR_PARAMS],
    )
    def test_log_model_auto_detect_persists_to_db_and_disk(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        flavor: str,
        module_path: str,
        func_name: str,
        model_module: str,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_save = _mock_flavor(monkeypatch, flavor, module_path, func_name, fake_ref)
        mock_model = _make_fake_instance(model_module)

        result = tracker.log_model(
            mock_model,
            name=f"{flavor}_model",
            tags=[flavor, "test"],
            experiment_id=exp_id,
        )

        mock_save.assert_called_once()
        assert isinstance(result, ModelReference)
        assert Path(result.path).exists()

        models_dir = tmp_path / "experiments" / exp_id / "models"
        assert models_dir.exists()
        assert Path(result.path).parent == models_dir

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT name, tags, experiment_id FROM models WHERE experiment_id = ?",
            (exp_id,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == f"{flavor}_model"
        assert json.loads(row[1]) == [flavor, "test"]
        assert row[2] == exp_id

    @pytest.mark.parametrize(
        "flavor, module_path, func_name, model_module",
        [p for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITH_INPUTS],
        ids=[p[0] for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITH_INPUTS],
    )
    def test_inputs_forwarded_when_provided(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        flavor: str,
        module_path: str,
        func_name: str,
        model_module: str,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_save = _mock_flavor(monkeypatch, flavor, module_path, func_name, fake_ref)
        mock_model = _make_fake_instance(model_module)
        sample_inputs = [[1, 2], [3, 4]]

        tracker.log_model(mock_model, inputs=sample_inputs, experiment_id=exp_id)

        args, _ = mock_save.call_args
        assert args[0] is mock_model
        assert args[1] is sample_inputs

    @pytest.mark.parametrize(
        "flavor, module_path, func_name, model_module",
        [p for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITHOUT_INPUTS],
        ids=[p[0] for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITHOUT_INPUTS],
    )
    def test_inputs_not_forwarded_when_none(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        flavor: str,
        module_path: str,
        func_name: str,
        model_module: str,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_save = _mock_flavor(monkeypatch, flavor, module_path, func_name, fake_ref)
        mock_model = _make_fake_instance(model_module)

        tracker.log_model(mock_model, experiment_id=exp_id)

        args, _ = mock_save.call_args
        assert len(args) == 1
        assert args[0] is mock_model

    def test_log_model_with_reference_skips_save(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        model_ref = ModelReference(str(dummy_model_file))

        result = tracker.log_model(
            model_ref, name="ref_model", tags=["v1"], experiment_id=exp_id
        )

        assert isinstance(result, ModelReference)
        assert Path(result.path).exists()
        assert Path(result.path).parent == tmp_path / "experiments" / exp_id / "models"

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT name, tags FROM models WHERE experiment_id = ?", (exp_id,)
        ).fetchone()
        conn.close()

        assert row[0] == "ref_model"
        assert json.loads(row[1]) == ["v1"]

    def test_log_model_cleans_up_temp_file(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        _mock_flavor(
            monkeypatch,
            "sklearn",
            "luml.integrations.sklearn.packaging",
            "save_sklearn",
            fake_ref,
        )
        mock_model = _make_fake_instance("sklearn.ensemble._forest")

        result = tracker.log_model(mock_model, inputs=[[1]], experiment_id=exp_id)

        assert not dummy_model_file.exists(), "Temp model file should be cleaned up"
        assert Path(result.path).exists(), "Stored copy should still exist"

    def test_get_models_returns_all_logged(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ref = ModelReference(str(dummy_model_file))

        tracker.log_model(ref, name="model_a")
        tracker.log_model(ref, name="model_b", tags=["prod"])

        models = tracker.get_models()
        assert len(models) == 2
        names = {m.name for m in models}
        assert names == {"model_a", "model_b"}
        for m in models:
            assert isinstance(m, Model)
            assert m.experiment_id == exp_id

    def test_get_model_by_id_returns_correct_record(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ref = ModelReference(str(dummy_model_file))

        tracker.log_model(ref, name="target", tags=["v2"])

        models = tracker.get_models()
        model_id = models[0].id

        model = tracker.get_model(model_id)
        assert model.name == "target"
        assert model.tags == ["v2"]
        assert model.experiment_id == exp_id
        assert model.path is not None

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT id, name FROM models WHERE id = ?", (model_id,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "target"

    def test_log_model_explicit_flavor_overrides_auto_detect(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_xgb = _mock_flavor(
            monkeypatch,
            "xgboost",
            "luml.integrations.xgboost.packaging",
            "save_xgboost",
            fake_ref,
        )
        mock_model = _make_fake_instance("sklearn.ensemble._forest")

        tracker.log_model(
            mock_model, flavor="xgboost", inputs=[[1]], experiment_id=exp_id
        )

        mock_xgb.assert_called_once()
        args, _ = mock_xgb.call_args
        assert args[0] is mock_model
