import json
import shutil
import subprocess
from pathlib import Path

import pytest

CHART_ROOT = Path(__file__).parents[1] / "chart"


def test_packaged_upgrade_defaults_match_chart_defaults() -> None:
    assert (CHART_ROOT / "defaults.yaml").read_text() == (CHART_ROOT / "values.yaml").read_text()


def test_upgrade_renders_with_previous_release_defaults(tmp_path: Path) -> None:
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is required for the chart upgrade regression")
    plugins = subprocess.run(
        [helm, "plugin", "list"], capture_output=True, text=True, check=True
    ).stdout
    if not any(line.split()[0] == "unittest" for line in plugins.splitlines() if line.split()):
        pytest.skip("helm-unittest is required for the chart upgrade regression")

    chart = tmp_path / "chart"
    shutil.copytree(CHART_ROOT, chart)
    # reuse-values replaces the new chart defaults with the previous release's values.
    (chart / "values.yaml").write_text(
        json.dumps(
            {
                "satellite": {
                    "token": "test-token",
                    "derivationKey": "test-derivation-key",
                },
                "monitoring": {"store": {"persistence": {"enabled": False}}},
            }
        )
    )
    (chart / "tests" / "previous_release_test.yaml").write_text(
        """suite: previous release values
templates:
  - templates/deployment-satellite.yaml
  - templates/statefulset-store.yaml
  - templates/secret-token.yaml
release:
  upgrade: true
tests:
  - it: defaults absent groups while preserving the previous persistence setting
    template: templates/statefulset-store.yaml
    asserts:
      - equal:
          path: spec.template.spec.containers[0].livenessProbe.timeoutSeconds
          value: 5
      - notExists:
          path: spec.volumeClaimTemplates
  - it: defaults nested values
    template: templates/deployment-satellite.yaml
    asserts:
      - equal:
          path: spec.template.spec.containers[0].image
          value: ghcr.io/luml-ai/luml-satellite-kubernetes:dev
      - contains:
          path: spec.template.spec.containers[0].env
          content: {name: MODEL_IMAGE, value: "ghcr.io/luml-ai/luml-model-server:dev"}
  - it: preserves the previous token
    template: templates/secret-token.yaml
    asserts:
      - equal:
          path: stringData.satellite-token
          value: test-token
"""
    )
    result = subprocess.run(
        [helm, "unittest", "--strict", "-f", "tests/previous_release_test.yaml", str(chart)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
