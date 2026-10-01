from pathlib import Path

import pytest

from luml_demo.config import SCENARIOS, DemoConfig, detect_docker_host_ip
from luml_demo.state import DemoState


def test_defaults_and_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LUML_DEMO_API_PORT", "18000")
    monkeypatch.setenv("LUML_DEMO_WEB_PORT", "15173")
    monkeypatch.setenv("LUML_DEMO_HOME", str(tmp_path / "demo"))
    monkeypatch.setenv("LUML_DEMO_SAT_PORT_BASE", "18081")
    config = DemoConfig()
    assert config.api_url == "http://localhost:18000"
    assert config.web_url == "http://localhost:15173"
    assert config.platform_url_for_docker == "http://host.docker.internal:18000"
    assert config.experiments_dir == tmp_path / "demo" / "experiments"
    assert [s.port for s in config.satellites] == [18081, 18082]
    assert config.satellite("staging").greptime_port == config.greptime_port_base + 1


def test_scenarios_cover_both_tracks() -> None:
    names = {s.name for s in SCENARIOS}
    assert names == {"churn", "autorag"}
    churn = next(s for s in SCENARIOS if s.name == "churn")
    assert churn.dataset_file == "data/customers.csv"
    assert churn.deploy_runner_up_to == "staging"


def test_docker_host_ip_falls_back_to_bridge_default() -> None:
    assert detect_docker_host_ip().count(".") == 3


def test_state_round_trip_and_rankings(tmp_path: Path) -> None:
    state = DemoState(api_key="dfs_x")
    state.artifacts["churn"] = [
        {"artifact_id": "a", "name": "base", "metric": 0.83, "winner": False},
        {"artifact_id": "b", "name": "gb", "metric": 0.87, "winner": True},
        {"artifact_id": "c", "name": "fe", "metric": 0.84, "winner": False},
    ]
    path = tmp_path / "state.json"
    state.save(path)
    loaded = DemoState.load(path)
    assert loaded.api_key == "dfs_x"
    assert loaded.winner("churn") == state.artifacts["churn"][1]
    assert loaded.runner_up("churn") == state.artifacts["churn"][2]
    assert loaded.winner("autorag") is None


def test_state_ignores_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"api_key": "k", "legacy_field": 1}')
    assert DemoState.load(path).api_key == "k"


def test_forgetting_platform_state_keeps_prisma_runs() -> None:
    from luml_demo.phases import _forget_platform_state

    state = DemoState(organization_id="old", orbit_id="o", runs={"churn": "run-1"},
                      artifacts={"churn": [{"artifact_id": "a"}]}, satellites={"prod": {"id": "s"}})
    _forget_platform_state(state)
    assert state.runs == {"churn": "run-1"}
    assert state.artifacts == {} and state.satellites == {} and state.orbit_id == ""
