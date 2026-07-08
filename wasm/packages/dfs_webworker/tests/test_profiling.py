"""Reference-profile generation + tar embedding for the tabular web-worker path.

These exercise the exact code ``tabular_train`` runs (build the profile, then embed it);
only falcon's ``save_model`` output is faked, since falcon runs solely in the Pyodide
worker. The fake artifact reproduces falcon's tar layout and producer-tag rule
(``[falcon.beastbyte.ai::{task}:v1] + extra_tags``) so the assertions mirror the real
Express Tasks scenarios.
"""

import io
import json
import tarfile
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import pytest

from dfs_webworker.constants import (
    PRODUCER,
    REFERENCE_PROFILE_FILENAME,
    REFERENCE_PROFILE_TAG,
    TABULAR_CLASSIFICATION,
    TABULAR_REGRESSION,
)
from dfs_webworker.profiling import (
    build_tabular_reference_profile,
    embed_reference_profile,
)

TARGET = "charges"
FEATURE_NAMES = ["age", "bmi", "sex"]


def _training_payload() -> dict[str, list[Any]]:
    rng = np.random.default_rng(0)
    n = 120
    age = rng.integers(18, 65, size=n)
    bmi = rng.normal(30.0, 6.0, size=n)
    return {
        "age": age.tolist(),
        "bmi": bmi.tolist(),
        "sex": rng.choice(["female", "male"], size=n).tolist(),
        TARGET: (age * 120.0 + bmi * 40.0).tolist(),
    }


def _regression_predict(features: pd.DataFrame) -> np.ndarray:
    return features["age"].to_numpy(dtype=float) * 100.0


def _classification_predict(features: pd.DataFrame) -> np.ndarray:
    return np.where(features["age"].to_numpy() > 40, "senior", "adult")


def _falcon_like_artifact(task: str, extra_tags: list[str]) -> bytes:
    """Uncompressed tar shaped like falcon's ``save_model`` output.

    Producer tags follow falcon's rule exactly: the built-in task tag first, then the
    verbatim ``extra_tags``. Includes a directory and a binary member so the repack is
    tested against non-JSON, non-file entries too.
    """
    manifest = {
        "variant": "pipeline",
        "producer_name": "falcon.beastbyte.ai",
        "producer_tags": [f"falcon.beastbyte.ai::{task}:v1", *extra_tags],
        "inputs": [],
        "outputs": [],
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        _add_bytes(tar, "manifest.json", json.dumps(manifest, indent=4).encode())
        _add_bytes(tar, "dtypes.json", b"{}")
        _add_dir(tar, "ops_artifacts/onnx_main")
        _add_bytes(tar, "ops_artifacts/onnx_main/model.onnx", b"\x08\x07onnx-bytes\x00")
    return buffer.getvalue()


def _add_bytes(tar: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(content))


def _add_dir(tar: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name=name + "/")
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    tar.addfile(info)


def _members(artifact: bytes) -> dict[str, bytes | None]:
    out: dict[str, bytes | None] = {}
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r") as tar:
        for member in tar.getmembers():
            extracted = tar.extractfile(member) if member.isreg() else None
            out[member.name] = extracted.read() if extracted is not None else None
    return out


def _producer_tags(artifact: bytes) -> list[str]:
    raw = _members(artifact)["manifest.json"]
    assert raw is not None
    return json.loads(raw)["producer_tags"]


def _read_profile(artifact: bytes) -> dict[str, Any] | None:
    raw = _members(artifact).get(REFERENCE_PROFILE_FILENAME)
    return None if raw is None else json.loads(raw)


def _make_artifact(task: str, predict: Callable[[pd.DataFrame], np.ndarray]) -> bytes:
    data = _training_payload()
    profile = build_tabular_reference_profile(data, FEATURE_NAMES, task, predict)
    tar = _falcon_like_artifact(
        task, extra_tags=[f"{PRODUCER}::{task}:v1", REFERENCE_PROFILE_TAG]
    )
    return embed_reference_profile(tar, profile)


def test_regression_artifact_has_full_profile_and_tags() -> None:
    artifact = _make_artifact(TABULAR_REGRESSION, _regression_predict)

    tags = _producer_tags(artifact)
    assert REFERENCE_PROFILE_TAG in tags
    assert f"{PRODUCER}::{TABULAR_REGRESSION}:v1" in tags

    profile = _read_profile(artifact)
    assert profile is not None
    features = profile["feature_summaries"]
    assert set(features["numerical_features"]) == {"age", "bmi"}
    assert set(features["categorical_features"]) == {"sex"}
    assert "numerical_outputs" in profile["output_summaries"]
    assert "categorical_outputs" not in profile["output_summaries"]
    assert profile["pca_profile"]["pca"]["feature_names"] == ["age", "bmi"]


def test_classification_output_is_categorical() -> None:
    artifact = _make_artifact(TABULAR_CLASSIFICATION, _classification_predict)

    tags = _producer_tags(artifact)
    assert REFERENCE_PROFILE_TAG in tags
    assert f"{PRODUCER}::{TABULAR_CLASSIFICATION}:v1" in tags

    profile = _read_profile(artifact)
    assert profile is not None
    outputs = profile["output_summaries"]
    assert "categorical_outputs" in outputs
    assert "numerical_outputs" not in outputs
    predicted = next(iter(outputs["categorical_outputs"].values()))
    assert set(predicted["categories"]) == {"adult", "senior"}
    assert abs(sum(predicted["probabilities"].values()) - 1.0) < 1e-6
    # PCA covers numerical features only; the categorical column is excluded.
    assert profile["pca_profile"]["pca"]["feature_names"] == ["age", "bmi"]


def test_profile_is_internally_consistent() -> None:
    profile = build_tabular_reference_profile(
        _training_payload(), FEATURE_NAMES, TABULAR_REGRESSION, _regression_predict
    )
    for summary in profile["feature_summaries"]["numerical_features"].values():
        lengths = {
            len(summary["bin_edges"]) - 1,
            len(summary["bin_centres"]),
            len(summary["frequencies"]),
            len(summary["probabilities"]),
        }
        assert len(lengths) == 1
        assert abs(sum(summary["probabilities"]) - 1.0) < 1e-6

    reference = profile["pca_profile"]["reference_distribution"]
    n_components = reference["n_components"]
    assert len(reference["mean"]) == n_components
    assert len(reference["covariance"]) == n_components
    assert all(len(row) == n_components for row in reference["covariance"])


def test_embed_preserves_existing_members_and_is_json_only() -> None:
    task = TABULAR_REGRESSION
    original = _falcon_like_artifact(
        task, extra_tags=[f"{PRODUCER}::{task}:v1", REFERENCE_PROFILE_TAG]
    )
    profile = build_tabular_reference_profile(
        _training_payload(), FEATURE_NAMES, task, _regression_predict
    )
    embedded = embed_reference_profile(original, profile)

    before = _members(original)
    after = _members(embedded)
    for name, content in before.items():
        assert after[name] == content
    assert after["ops_artifacts/onnx_main/model.onnx"] == b"\x08\x07onnx-bytes\x00"

    raw = after[REFERENCE_PROFILE_FILENAME]
    assert raw is not None
    reparsed = json.loads(raw)  # no custom decoder
    assert set(reparsed) == {"feature_summaries", "output_summaries", "pca_profile"}
    _assert_json_scalars(reparsed)


def test_embed_is_idempotent() -> None:
    task = TABULAR_REGRESSION
    original = _falcon_like_artifact(task, extra_tags=[REFERENCE_PROFILE_TAG])
    profile = build_tabular_reference_profile(
        _training_payload(), FEATURE_NAMES, task, _regression_predict
    )

    once = embed_reference_profile(original, profile)
    twice = embed_reference_profile(once, profile)

    names = [n for n in _members(twice) if n == REFERENCE_PROFILE_FILENAME]
    assert names == [REFERENCE_PROFILE_FILENAME]


def test_unknown_task_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported tabular task"):
        build_tabular_reference_profile(
            _training_payload(),
            FEATURE_NAMES,
            "tabular_clustering",
            _regression_predict,
        )


def _assert_json_scalars(obj: object) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert isinstance(key, str)
            _assert_json_scalars(value)
    elif isinstance(obj, list):
        for value in obj:
            _assert_json_scalars(value)
    else:
        assert obj is None or isinstance(obj, (bool, int, float, str))
