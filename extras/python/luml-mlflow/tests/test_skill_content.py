"""Keep the luml-mlflow skill true to the installed plugin.

The monitoring reference is run as written: a model logged through MLflow gets a
reference profile that passes the SDK skill's check. The settings the skill
names must exist.
"""

import json
import re
import tarfile
import textwrap
from pathlib import Path
from typing import Any

import pytest
from luml_mlflow.config import Settings

SKILL_DIR = Path(__file__).resolve().parents[1] / "luml_mlflow/skills/luml-mlflow"
PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _blocks(name: str) -> list[str]:
    text = (SKILL_DIR / name).read_text()
    return [textwrap.dedent(block) for block in PYTHON_BLOCK.findall(text)]


def test_named_settings_exist() -> None:
    text = "\n".join(path.read_text() for path in SKILL_DIR.rglob("*.md"))
    named = set(re.findall(r"\b(LUML_MLFLOW_[A-Z_]+|LUML_BACKEND_STORE_URI)\b", text))
    assert named
    assert named <= set(Settings.model_fields)


def test_monitoring_steps_give_a_ready_profile(
    temp_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sklearn.datasets import load_iris
    from sklearn.linear_model import LogisticRegression

    # MLflow 3.x reads requirements from a uv.lock in the working directory.
    monkeypatch.chdir(temp_store.parent)
    monkeypatch.setenv("LUML_MLFLOW_AUTOSYNC", "0")
    monkeypatch.setattr(Path, "home", lambda: temp_store.parent / "home")
    (temp_store.parent / "home/.luml").mkdir(parents=True)
    (temp_store.parent / "home/.luml/experiments").symlink_to(temp_store)

    features, target = load_iris(return_X_y=True, as_frame=True)
    features.columns = [
        c.replace(" (cm)", "").replace(" ", "_") for c in features.columns
    ]
    log_block, profile_block = _blocks("references/monitoring.md")
    namespace: dict[str, Any] = {
        "model": LogisticRegression(max_iter=500),
        "X_train": features,
        "y_train": target == 0,
    }

    exec(  # noqa: S102
        compile(
            log_block.replace("luml://My org/Research", "luml://local"), "log", "exec"
        ),
        namespace,
    )
    exec(compile(profile_block, "profile", "exec"), namespace)  # noqa: S102

    path = temp_store / namespace["logged"].path
    with tarfile.open(path) as archive:
        manifest = json.load(archive.extractfile("manifest.json"))  # type: ignore[arg-type]
        profile = json.load(archive.extractfile("reference_profile.json"))  # type: ignore[arg-type]
    summaries = profile["feature_summaries"]
    profiled = set(summaries.get("numerical_features", {})) | set(
        summaries.get("categorical_features", {})
    )
    assert profiled == {spec["name"] for spec in manifest["inputs"]}
    assert {"luml.ai::tabular_monitoring:v1", "luml.ai::kind_tabular:v1"} <= set(
        manifest["producer_tags"]
    )
    assert [spec["name"] for spec in manifest["outputs"]] == ["predictions"]
    assert profile["profile_status"] == "ready"
