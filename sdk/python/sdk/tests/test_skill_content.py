"""Keep the luml-sdk skill true to the installed SDK.

Every name the skill's code blocks import or call on a tracker, model, dataset or
builder must exist, keyword arguments must be accepted, and the main examples
must run on small data.
"""

import ast
import importlib
import importlib.util
import inspect
import json
import re
import sys
import tarfile
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]

from luml.artifacts.dataset import DatasetReference, MaterializedDataset
from luml.artifacts.model import ModelReference
from luml.experiments.tracker import ExperimentTracker
from luml.flow import RelayedFlow

SKILL_DIR = Path(__file__).resolve().parents[1] / "luml/skills/luml-sdk"
PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
OBJECT_TYPES: dict[str, type] = {
    "tracker": ExperimentTracker,
    "model_ref": ModelReference,
    "dataset_ref": DatasetReference,
    "dataset": MaterializedDataset,
    "builder": PyfuncBuilder,
    "flow": RelayedFlow,
}


def _markdown_files() -> list[Path]:
    return sorted(SKILL_DIR.rglob("*.md"))


def _blocks(path: Path) -> list[str]:
    return PYTHON_BLOCK.findall(path.read_text())


def _all_blocks() -> Iterator[tuple[str, str]]:
    for path in _markdown_files():
        for index, block in enumerate(_blocks(path)):
            yield f"{path.relative_to(SKILL_DIR)}#{index}", block


def _block(path: str, marker: str) -> str:
    (block,) = [b for b in _blocks(SKILL_DIR / path) if marker in b]
    return block


BLOCKS = list(_all_blocks())


@pytest.mark.parametrize(("where", "block"), BLOCKS, ids=[b[0] for b in BLOCKS])
def test_block_parses(where: str, block: str) -> None:
    ast.parse(block)


@pytest.mark.parametrize(("where", "block"), BLOCKS, ids=[b[0] for b in BLOCKS])
def test_luml_imports_exist(where: str, block: str) -> None:
    for node in ast.walk(ast.parse(block)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            ("luml", "fnnx")
        ):
            module = importlib.import_module(node.module or "")
            for alias in node.names:
                assert hasattr(module, alias.name), f"{node.module}.{alias.name}"


def _calls_on_known_objects(block: str) -> Iterator[tuple[type, str, ast.Call]]:
    for node in ast.walk(ast.parse(block)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in OBJECT_TYPES
        ):
            continue
        yield OBJECT_TYPES[node.func.value.id], node.func.attr, node


@pytest.mark.parametrize(("where", "block"), BLOCKS, ids=[b[0] for b in BLOCKS])
def test_methods_and_keywords_exist(where: str, block: str) -> None:
    for owner, method_name, call in _calls_on_known_objects(block):
        method = getattr(owner, method_name, None)
        assert method is not None, f"{owner.__name__}.{method_name}"
        _assert_keywords_accepted(method, call, f"{owner.__name__}.{method_name}")


def _assert_keywords_accepted(method: Callable, call: ast.Call, name: str) -> None:
    parameters = inspect.signature(method).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return
    for keyword in call.keywords:
        if keyword.arg is not None:
            assert keyword.arg in parameters, f"{name}(... {keyword.arg}=)"


def test_imported_functions_accept_keywords() -> None:
    for where, block in BLOCKS:
        tree = ast.parse(block)
        imported: dict[str, Any] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "luml"
            ):
                module = importlib.import_module(node.module or "")
                for alias in node.names:
                    imported[alias.asname or alias.name] = getattr(module, alias.name)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and callable(imported.get(node.func.id))
            ):
                _assert_keywords_accepted(
                    imported[node.func.id], node, f"{where}: {node.func.id}"
                )


@pytest.fixture
def iris_frame() -> tuple[pd.DataFrame, pd.Series]:
    from sklearn.datasets import load_iris  # type: ignore[import-untyped]

    features, target = load_iris(return_X_y=True, as_frame=True)
    return features, target


def _manifest(path: str) -> dict[str, Any]:
    with tarfile.open(path) as archive:
        member = archive.extractfile("manifest.json")
        assert member is not None
        return json.load(member)


def test_minimal_example_logs_a_monitored_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    block = _block("SKILL.md", "ExperimentTracker(")

    exec(compile(block, "SKILL.md", "exec"), {})  # noqa: S102

    tracker = ExperimentTracker("sqlite://./experiments")
    (experiment,) = tracker.list_experiments()
    (model,) = tracker.get_models(experiment.id)
    assert model.path is not None
    tags = _manifest(str(Path("experiments") / model.path))["producer_tags"]
    assert "luml.ai::tabular_monitoring:v1" in tags


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_custom_tabular_pyfunc_runs_and_takes_a_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    iris_frame: tuple[pd.DataFrame, pd.Series],
) -> None:
    from fnnx.runtime import Runtime  # type: ignore[import-untyped]
    from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    features, target = iris_frame
    training_features = features.rename(
        columns=lambda c: c.replace(" (cm)", "").replace(" ", "_")
    )
    model = LogisticRegression(max_iter=500).fit(
        training_features.to_numpy(), target == 0
    )
    pyfunc_file = tmp_path / "tabular_pyfunc.py"
    pyfunc_file.write_text(_block("references/packaging.md", "TabularModel(PyFunc)"))
    _load_module("tabular_pyfunc", pyfunc_file)
    namespace: dict[str, Any] = {"X_train": training_features, "model": model}

    build = _block("references/packaging.md", 'builder.save("churn-ranker.luml")')
    exec(compile(build, "packaging.md", "exec"), namespace)  # noqa: S102
    model_ref: ModelReference = namespace["model_ref"]

    rows = training_features.head(3)
    outputs = Runtime(model_ref.path).compute(
        {name: rows[name].to_numpy() for name in rows.columns}, dynamic_attributes={}
    )
    np.testing.assert_allclose(outputs["y"], model.predict(rows.to_numpy()), rtol=1e-5)

    profile_call = _block("references/monitoring.md", "add_reference_profile(\n")
    exec(  # noqa: S102
        compile(profile_call, "monitoring.md", "exec"),
        {
            "model_ref": model_ref,
            "X_train": training_features,
            "predict": lambda frame: model.predict(np.asarray(frame)).astype(float),
            "predict_proba": lambda frame: model.predict_proba(np.asarray(frame)),
        },
    )
    check = _block("references/monitoring.md", "profile_status")
    exec(compile(check, "monitoring.md", "exec"), {"model_ref": model_ref})  # noqa: S102


def _verify_script() -> ModuleType:
    return _load_module("verify_artifact", SKILL_DIR / "scripts/verify_artifact.py")


def test_verify_script_builds_an_isolated_uv_command() -> None:
    script = _verify_script()
    spec = {
        "python_version": "3.12.4",
        "dependencies": [{"package": "fnnx==0.0.13"}, {"package": "numpy==2.3.0"}],
    }

    assert script.uv_command(spec) == [
        "uv", "run", "--no-project", "--isolated", "--python", "3.12",
        "--with", "fnnx==0.0.13", "--with", "numpy==2.3.0",
    ]  # fmt: skip


def test_verify_script_reads_the_artifact_environment(
    tmp_path: Path, iris_frame: tuple[pd.DataFrame, pd.Series]
) -> None:
    from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

    from luml.integrations.sklearn import save_sklearn

    features, target = iris_frame
    model = LogisticRegression(max_iter=500).fit(features, target)
    ref = save_sklearn(model, inputs=features, path=str(tmp_path / "m.luml"))

    spec = _verify_script().environment_spec(Path(ref.path))

    packages = [dependency["package"] for dependency in spec["dependencies"]]
    assert any(package.startswith("scikit-learn==") for package in packages)


def test_verify_script_usage_without_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _verify_script().main([]) == 2
    assert "verify_artifact.py model.luml inputs.json" in capsys.readouterr().out
