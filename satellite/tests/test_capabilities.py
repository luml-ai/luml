from agent.agent_manager import SatelliteManager


def test_capabilities_include_monitoring() -> None:
    caps = SatelliteManager.get_capabilities()
    assert "monitoring" in caps
    assert caps["monitoring"]["version"] == 1


def test_capabilities_include_deploy() -> None:
    caps = SatelliteManager.get_capabilities()
    assert "deploy" in caps
    assert caps["deploy"]["version"] == 1
