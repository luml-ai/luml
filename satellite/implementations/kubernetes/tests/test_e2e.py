import base64
import io
import tarfile
from pathlib import Path

from e2e.create_state import (
    GPU_DEPLOYMENT_ID,
    MAIN_DEPLOYMENT_ID,
    REPLICA_DEPLOYMENT_ID,
    build_state,
)

REPOSITORY_ROOT = Path(__file__).parents[4]


def test_fake_platform_state_seeds_each_kind_scenario(tmp_path: Path) -> None:
    fixture = tmp_path / "stub.json"
    fixture.write_text('{"prediction": 42}', encoding="utf-8")

    state = build_state(fixture)

    deployments = {item["id"]: item for item in state["deployments"]}
    assert deployments[MAIN_DEPLOYMENT_ID]["monitoring_mode"] == "full"
    assert deployments[REPLICA_DEPLOYMENT_ID]["satellite_parameters"]["replicas"] == 3
    assert deployments[GPU_DEPLOYMENT_ID]["satellite_parameters"]["use_gpu"] is True
    assert state["allowed_api_keys"] == ["ci-valid-api-key"]
    assert state["monitoring_tokens"]["ci-monitoring-launch-token"]["active"] is True

    content = base64.b64decode(state["artifacts"][0]["content_base64"])
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        extracted = archive.extractfile("stub.json")
        assert extracted is not None
        assert extracted.read() == b'{"prediction": 42}'


def test_kind_harness_uses_an_enforcing_cni_and_enables_the_policy() -> None:
    package_root = Path(__file__).parents[1]
    run_script = (package_root / "e2e/run.sh").read_text(encoding="utf-8")
    kind_configuration = (package_root / "e2e/kind-config.yaml").read_text(encoding="utf-8")
    chart_values = (package_root / "chart/values.yaml").read_text(encoding="utf-8")

    assert "disableDefaultCNI: true" in kind_configuration
    assert "projectcalico/calico" in run_script
    assert "networkPolicy:\n  enabled: true" in chart_values
    assert "_assert_model_port_is_blocked" in (package_root / "e2e/test_kind.py").read_text(
        encoding="utf-8"
    )


def test_openshift_leg_supplies_a_random_user_without_a_group() -> None:
    run_script = (REPOSITORY_ROOT / "satellite/implementations/kubernetes/e2e/run.sh").read_text(
        encoding="utf-8"
    )

    assert "RANDOM_USER=1000710000" in run_script
    assert "pod-security.kubernetes.io/enforce=restricted" in run_script
    assert "runAsUser" in run_script
    assert "fsGroup" in run_script
    assert "runAsGroup" not in run_script
