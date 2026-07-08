"""End-to-end check of the real ``tabular_train`` wiring.

Falcon (and its onnx toolchain) only ship in the Pyodide worker, so this is skipped
wherever falcon is absent. Where it runs, it proves the actual packaging path embeds a
full ``reference_profile.json`` and stamps the presence tag alongside the studio tag.
"""

import io
import json
import tarfile
from typing import Any

import numpy as np
import pytest

pytest.importorskip("falcon")

from dfs_webworker.constants import (  # noqa: E402
    PRODUCER,
    REFERENCE_PROFILE_FILENAME,
    REFERENCE_PROFILE_TAG,
    TABULAR_CLASSIFICATION,
    TABULAR_REGRESSION,
)
from dfs_webworker.tabular import tabular_train  # noqa: E402


def _dataset(classification: bool) -> tuple[dict[str, list[Any]], str]:
    rng = np.random.default_rng(0)
    n = 80
    age = rng.integers(18, 65, size=n)
    bmi = rng.normal(30.0, 6.0, size=n)
    sex = rng.choice(["female", "male"], size=n)
    target = (age > 40).astype(int) if classification else age * 120.0 + bmi * 40.0
    return {
        "age": age.tolist(),
        "bmi": bmi.tolist(),
        "sex": sex.tolist(),
        "target": target.tolist(),
    }, "target"


def _artifact_members(model: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(model), mode="r") as tar:
        for member in tar.getmembers():
            if member.isreg():
                extracted = tar.extractfile(member)
                assert extracted is not None
                out[member.name] = extracted.read()
    return out


@pytest.mark.parametrize(
    ("task", "classification"),
    [(TABULAR_REGRESSION, False), (TABULAR_CLASSIFICATION, True)],
)
def test_tabular_train_embeds_profile_and_tag(task: str, classification: bool) -> None:
    data, target = _dataset(classification)
    result = tabular_train(task, data, target)

    members = _artifact_members(result["model"])
    manifest = json.loads(members["manifest.json"])
    tags = manifest["producer_tags"]
    assert REFERENCE_PROFILE_TAG in tags
    assert f"{PRODUCER}::{task}:v1" in tags

    profile = json.loads(members[REFERENCE_PROFILE_FILENAME])  # plain JSON
    assert set(profile) == {"feature_summaries", "output_summaries", "pca_profile"}
    outputs = profile["output_summaries"]
    if classification:
        assert "categorical_outputs" in outputs
    else:
        assert "numerical_outputs" in outputs
    assert profile["pca_profile"]["pca"]["feature_names"] == ["age", "bmi"]
