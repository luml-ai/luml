import json
from pathlib import Path

from luml_agent.orchestrator.nodes.result_file import (
    RESULT_DIR,
    RESULT_FILENAME,
    parse_stdout_metric,
    read_result_file,
)


class TestReadResultFile:
    def test_returns_none_when_missing(
        self, tmp_path: Path,
    ) -> None:
        assert read_result_file(str(tmp_path)) is None

    def test_reads_minimal_result(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        (result_dir / RESULT_FILENAME).write_text(
            json.dumps({"success": True}),
        )

        result = read_result_file(str(tmp_path))
        assert result == {"success": True}

    def test_reads_full_result(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        data = {
            "success": False,
            "error_message": "tests failed",
            "metrics": {"passed": 3, "failed": 1},
            "artifacts": {"summary": "partial fix"},
            "proposals": [{"title": "A", "prompt": "do A"}],
        }
        (result_dir / RESULT_FILENAME).write_text(
            json.dumps(data),
        )

        result = read_result_file(str(tmp_path))
        assert result is not None
        assert result["success"] is False
        assert result["metrics"]["failed"] == 1
        assert len(result["proposals"]) == 1

    def test_returns_none_on_invalid_json(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        (result_dir / RESULT_FILENAME).write_text("not json")

        assert read_result_file(str(tmp_path)) is None

    def test_returns_none_when_success_key_missing(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        (result_dir / RESULT_FILENAME).write_text(
            json.dumps({"metrics": {}}),
        )

        assert read_result_file(str(tmp_path)) is None

    def test_returns_none_when_not_a_dict(
        self, tmp_path: Path,
    ) -> None:
        result_dir = tmp_path / RESULT_DIR
        result_dir.mkdir()
        (result_dir / RESULT_FILENAME).write_text(
            json.dumps([1, 2, 3]),
        )

        assert read_result_file(str(tmp_path)) is None


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
