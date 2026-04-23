import io
import json
import sys
from pathlib import Path

import pytest

from luml_prisma.mock_agent import (
    RESULT_FILE,
    STATE_DIR,
    STATE_FILE,
    _interactive_loop,
    detect_step_type,
    run,
)


def _read_state(cwd: Path) -> dict[str, int]:
    return json.loads(
        (cwd / STATE_DIR / STATE_FILE).read_text(),
    )


def _read_result(cwd: Path) -> dict[str, object]:
    return json.loads(
        (cwd / STATE_DIR / RESULT_FILE).read_text(),
    )


class TestDetectStepType:
    def test_no_args_defaults_to_implement(self) -> None:
        assert detect_step_type([]) == "implement"

    def test_plain_prompt_is_implement(self) -> None:
        assert detect_step_type(["add a login page"]) == "implement"

    def test_run_subcommand(self) -> None:
        assert detect_step_type(["run"]) == "run"
        assert detect_step_type(["run", "--timeout=30"]) == "run"

    def test_fork_prompt_detected(self) -> None:
        prompt = (
            "Decompose the following objective"
            " into at most 3 atomic changes"
        )
        assert detect_step_type([prompt]) == "fork"

    def test_debug_prompt_detected(self) -> None:
        prompt = (
            "The previous run command failed"
            " with exit code 1.\nPlease fix."
        )
        assert detect_step_type([prompt]) == "debug"


class TestInteractiveLoop:
    def test_echoes_input(
        self, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("hello\n/exit\n"),
        )
        _interactive_loop()
        out = capsys.readouterr().out
        assert "hello" in out

    def test_exits_on_slash_exit(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        _interactive_loop()

    def test_exits_on_eof(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        _interactive_loop()

    def test_multiple_lines_before_exit(
        self, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("one\ntwo\n/exit\n"),
        )
        _interactive_loop()
        out = capsys.readouterr().out
        assert "one" in out
        assert "two" in out


class TestImplementHandler:
    def test_writes_step_py(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        assert run(["build feature"]) == 0
        assert (
            (tmp_path / "step.py").read_text()
            == "# implement step 1\n"
        )

    def test_writes_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["build feature"])
        assert _read_result(tmp_path)["success"] is True

    def test_increments_step_number(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["first"])
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["second"])
        assert (
            (tmp_path / "step.py").read_text()
            == "# implement step 2\n"
        )
        assert _read_state(tmp_path)["implement"] == 2


class TestDebugHandler:
    def test_writes_step_py(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        prompt = (
            "The previous run command failed"
            " with exit code 1.\nFix it."
        )
        assert run([prompt]) == 0
        assert (
            (tmp_path / "step.py").read_text()
            == "# debug step 1\n"
        )

    def test_overwrites_implement_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["implement something"])
        assert "implement" in (tmp_path / "step.py").read_text()

        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        prompt = (
            "The previous run command failed"
            " with exit code 1.\nFix."
        )
        run([prompt])
        assert "debug" in (tmp_path / "step.py").read_text()


class TestRunHandler:
    def test_succeeds_with_metrics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        assert run(["run"]) == 0
        result = _read_result(tmp_path)
        assert result["success"] is True
        assert result["metrics"]["passed"] == 1

    def test_does_not_write_step_py(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["run"])
        assert not (tmp_path / "step.py").exists()


class TestForkHandler:
    def test_writes_luml_fork_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        prompt = (
            "Decompose the following objective"
            " into at most 3 atomic changes"
        )
        assert run([prompt]) == 0

        fork_path = tmp_path / ".luml-fork.json"
        fork_data = json.loads(fork_path.read_text())
        assert isinstance(fork_data, list)
        assert len(fork_data) == 4
        assert all(
            isinstance(s, str) and len(s) == 8
            for s in fork_data
        )

    def test_result_has_proposals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        prompt = (
            "Decompose the following objective"
            " into at most 3 atomic changes"
        )
        run([prompt])

        result = _read_result(tmp_path)
        assert result["success"] is True
        assert len(result["proposals"]) == 4
        assert all(
            "title" in p and "prompt" in p
            for p in result["proposals"]
        )


class TestStateTracking:
    def test_types_have_independent_counters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["build feature"])
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["run"])
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        run(["build another"])

        state = _read_state(tmp_path)
        assert state["implement"] == 2
        assert state["run"] == 1

    def test_no_args_uses_implement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("/exit\n"),
        )
        assert run() == 0
        assert (
            (tmp_path / "step.py").read_text()
            == "# implement step 1\n"
        )
