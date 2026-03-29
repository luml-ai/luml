import json
from pathlib import Path

from luml_agent.services.orchestrator.nodes.result_file import (
    RESULT_DIR,
    RESULT_FILENAME,
    ResultData,
    parse_stdout_metric,
    read_result_file,
)


def _write_result(tmp_path: Path, data: dict) -> None:
    result_dir = tmp_path / RESULT_DIR
    result_dir.mkdir(exist_ok=True)
    (result_dir / RESULT_FILENAME).write_text(json.dumps(data))


class TestReadResultFile:
    def test_returns_none_when_missing(
        self, tmp_path: Path,
    ) -> None:
        assert read_result_file(str(tmp_path)) is None

    def test_reads_minimal_success(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {"success": True})
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.success is True
        assert result.experiment_ids == []
        assert result.metrics == {}
        assert result.model_path is None
        assert result.error_message is None

    def test_single_experiment_id(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "experiment_id": "abc-123",
            "metrics": {"accuracy": 0.92},
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.experiment_ids == ["abc-123"]
        assert result.experiment_id == "abc-123"
        assert result.metrics == {"accuracy": 0.92}

    def test_multiple_experiment_ids(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "experiment_ids": ["exp-1", "exp-2", "exp-3"],
            "metrics": {"accuracy": 0.95},
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.experiment_ids == ["exp-1", "exp-2", "exp-3"]
        assert result.metrics == {"accuracy": 0.95}

    def test_experiment_ids_takes_precedence_over_singular(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "experiment_id": "single",
            "experiment_ids": ["list-1", "list-2"],
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.experiment_ids == ["list-1", "list-2"]

    def test_legacy_metric_float_normalized(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "metric": 0.87,
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.metrics == {"metric": 0.87}

    def test_metrics_dict_takes_precedence_over_legacy(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "metrics": {"f1": 0.9},
            "metric": 0.5,
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.metrics == {"f1": 0.9}

    def test_model_path_from_artifacts(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "artifacts": {"model_path": "model.luml"},
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.model_path == "model.luml"

    def test_model_path_top_level(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "model_path": "output/best.pt",
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.model_path == "output/best.pt"

    def test_error_message(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": False,
            "error_message": "training crashed",
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.success is False
        assert result.error_message == "training crashed"

    def test_returns_none_on_invalid_json(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        (result_dir / RESULT_FILENAME).write_text("not json {{{")
        assert read_result_file(str(tmp_path)) is None

    def test_returns_none_when_not_a_dict(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, [1, 2, 3])
        assert read_result_file(str(tmp_path)) is None

    def test_missing_success_defaults_false(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        (result_dir / RESULT_FILENAME).write_text(
            json.dumps({"metrics": {"acc": 0.5}}),
        )
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.success is False

    def test_non_numeric_metric_values_skipped(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "metrics": {"acc": 0.9, "bad": "not_a_number", "ok": 1},
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.metrics == {"acc": 0.9, "ok": 1.0}

    def test_empty_experiment_ids_list(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "experiment_ids": [],
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.experiment_ids == []

    def test_full_result(
        self, tmp_path: Path,
    ) -> None:
        _write_result(tmp_path, {
            "success": True,
            "experiment_id": "exp-42",
            "experiment_ids": ["exp-42", "exp-43"],
            "metrics": {"accuracy": 0.92, "f1_score": 0.88},
            "artifacts": {"model_path": "model.luml"},
            "error_message": "",
        })
        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result.success is True
        assert result.experiment_ids == ["exp-42", "exp-43"]
        assert result.metrics == {"accuracy": 0.92, "f1_score": 0.88}
        assert result.model_path == "model.luml"
        assert result.error_message == ""


class TestResultDataDefaults:
    def test_dataclass_defaults(self) -> None:
        rd = ResultData(success=True)
        assert rd.success is True
        assert rd.experiment_id is None
        assert rd.experiment_ids == []
        assert rd.metrics == {}
        assert rd.model_path is None
        assert rd.error_message is None


class TestParseStdoutMetric:
    def test_extracts_metric_from_jsonline(self) -> None:
        logs = (
            "sleeping for 1 second...\n"
            '{"type": "luml-agent-message",'
            ' "metric": 0.95}\n'
        )
        assert parse_stdout_metric(logs) == 0.95

    def test_returns_last_metric_when_multiple(self) -> None:
        logs = (
            '{"type": "luml-agent-message",'
            ' "metric": 0.5}\n'
            "some output\n"
            '{"type": "luml-agent-message",'
            ' "metric": 0.9}\n'
        )
        assert parse_stdout_metric(logs) == 0.9

    def test_returns_none_when_no_metric(self) -> None:
        logs = "just regular output\nno json here\n"
        assert parse_stdout_metric(logs) is None

    def test_ignores_non_metric_jsonlines(self) -> None:
        logs = (
            '{"type": "luml-agent-message",'
            ' "status": "running"}\n'
        )
        assert parse_stdout_metric(logs) is None

    def test_ignores_invalid_json(self) -> None:
        logs = (
            "{not valid json}\n"
            '{"type": "luml-agent-message",'
            ' "metric": 42}\n'
        )
        assert parse_stdout_metric(logs) == 42

    def test_handles_dict_metric(self) -> None:
        logs = (
            '{"type": "luml-agent-message",'
            ' "metric": {"accuracy": 0.95, "loss": 0.05}}\n'
        )
        assert parse_stdout_metric(logs) == {
            "accuracy": 0.95, "loss": 0.05,
        }

    def test_handles_empty_logs(self) -> None:
        assert parse_stdout_metric("") is None

    def test_ignores_wrong_type(self) -> None:
        logs = '{"type": "other-message", "metric": 0.5}\n'
        assert parse_stdout_metric(logs) is None

    def test_skips_lines_not_starting_with_brace(
        self,
    ) -> None:
        logs = (
            'prefix {"type": "luml-agent-message",'
            ' "metric": 0.5}\n'
        )
        assert parse_stdout_metric(logs) is None

    def test_strips_ansi_escape_sequences(self) -> None:
        logs = (
            '\x1b[2K{"type": "luml-agent-message",'
            ' "metric": 0.99}\n'
        )
        assert parse_stdout_metric(logs) == 0.99

    def test_strips_multiple_ansi_escapes(self) -> None:
        logs = (
            '\x1b[0m\x1b[2K{"type": "luml-agent-message",'
            ' "metric": 0.42}\r\n'
        )
        assert parse_stdout_metric(logs) == 0.42
