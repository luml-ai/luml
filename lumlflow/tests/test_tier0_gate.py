"""The Tier-0 contract, enforced as a gate rather than argued about.

The harness lives in `dev/tier0_gate/` because it is also a thing to run by hand
against a real workspace; this is the CI wiring for it. It spawns the actual CLI
in subprocesses — the point is the surface an agent meets, and an in-process
runner would not prove that surface exists.
"""

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
    """Edit → run → inspect → fix → rerun, using only verbs the guide names,
    with no uid, content hash or memo key printed anywhere along the way."""
    state = tmp_path / "state"
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    workspace = tmp_path / "project"
    workspace.mkdir()

    try:
        report = harness.gate(workspace)
    finally:
        harness.stop_daemon(workspace)
        # The harness drives the CLI, which starts servers behind it; a gate
        # that fails halfway must not leave one holding the workspace.
        stop_recorded(state)

    assert report.failures == []
    assert report.passed
    assert report.guide_lines > 0
    # The whole loop, on the three gestures the guide teaches.
    assert {"run", "status", "context"} <= report.vocabulary
    assert not (workspace / "AGENTS.md").exists()
