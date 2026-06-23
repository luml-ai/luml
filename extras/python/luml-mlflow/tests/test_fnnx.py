"""Integration test for the real fnnx conversion seam.

Exercises ``convert_mlflow_model_to_fnnx`` end-to-end against the FNNX
converter using a tiny, deterministic sklearn model. Skipped when scikit-learn
is not installed in the environment.
"""

import tarfile
from pathlib import Path

import pytest
from luml_mlflow.fnnx import convert_mlflow_model_to_fnnx

pytest.importorskip("sklearn")


def _save_sklearn_model(model_dir: Path) -> None:
    import mlflow.sklearn
    import pandas as pd
    from mlflow.models.signature import infer_signature
    from sklearn.ensemble import RandomForestClassifier

    x = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0, 0.0]})
    y = [0, 1, 0, 1]
    model = RandomForestClassifier(n_estimators=5, random_state=0).fit(x, y)
    sig = infer_signature(x, model.predict(x))
    mlflow.sklearn.save_model(model, str(model_dir), signature=sig)


def test_converts_sklearn_model_to_valid_fnnx_package(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    _save_sklearn_model(model_dir)
    output = tmp_path / "model.fnnx"

    result = convert_mlflow_model_to_fnnx(model_dir, output, name="sklearn-rf")

    assert result == output
    assert output.exists() and output.stat().st_size > 0
    with tarfile.open(output) as tar:
        names = set(tar.getnames())
    assert {"manifest.json", "env.json", "meta.json"} <= names


def test_conversion_is_independent_of_output_name(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    _save_sklearn_model(model_dir)

    out_a = tmp_path / "a.fnnx"
    out_b = tmp_path / "b.fnnx"
    convert_mlflow_model_to_fnnx(model_dir, out_a, name="m")
    convert_mlflow_model_to_fnnx(model_dir, out_b, name="m")

    with tarfile.open(out_a) as ta, tarfile.open(out_b) as tb:
        assert set(ta.getnames()) == set(tb.getnames())
