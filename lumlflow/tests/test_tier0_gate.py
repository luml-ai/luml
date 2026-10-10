import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from lumlflow.flow.daemon.workspace import STATE_DIR_ENV

from tests.servers import stop_recorded

HARNESS = Path(__file__).resolve().parents[2] / "dev" / "tier0_gate" / "harness.py"


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tier0_gate_harness", HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_served_guide_loop_completes_on_names_alone(
    harness: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pass
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    workspace = tmp_path / "project"
    workspace.mkdir()

    try:
        report = harness.gate(workspace)
    finally:
        harness.stop_daemon(workspace)
        stop_recorded(state)

    assert report.failures == []
    assert report.passed
    assert report.guide_lines > 0
    assert {"run", "status", "context"} <= report.vocabulary
    assert not (workspace / "AGENTS.md").exists()
