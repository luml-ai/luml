"""Reference-profile generation and embedding for the tabular web-worker path.

The heavy lifting lives in the vendored, dependency-light ``reference_profile``
module (numpy / scikit-learn / pandas only). This module adds the worker-specific
glue: turning the training payload into a feature frame, mapping the Express Tasks
task name onto the canonical task type, and embedding the resulting JSON profile as a
``reference_profile.json`` member inside falcon's uncompressed tar artifact. It never
imports falcon or fnnx, so it can be exercised without the Pyodide toolchain.
"""

import io
import json
import tarfile
from collections.abc import Callable
from typing import Any

import pandas as pd

from dfs_webworker.constants import (
    REFERENCE_PROFILE_FILENAME,
    TABULAR_CLASSIFICATION,
    TABULAR_REGRESSION,
)
from dfs_webworker.reference_profile import TaskType, build_reference_profile

_TASK_TYPES: dict[str, TaskType] = {
    TABULAR_CLASSIFICATION: "classification",
    TABULAR_REGRESSION: "regression",
}


def build_tabular_reference_profile(
    data: dict[str, list[Any]],
    feature_names: list[str],
    task: str,
    predict: Callable[[Any], Any],
) -> dict[str, Any]:
    """Compute the full reference profile from the training payload.

    ``feature_names`` selects and orders the feature columns (excluding the target)
    so the profile matches the order the model consumes. Column dtypes come from the
    training payload, so numerical and categorical columns land in the correct group.
    """
    try:
        task_type = _TASK_TYPES[task]
    except KeyError as exc:
        raise ValueError(f"Unsupported tabular task: {task!r}") from exc

    features = pd.DataFrame(data)[list(feature_names)]
    return build_reference_profile(features, task_type, predict)


def embed_reference_profile(model_bytes: bytes, profile: dict[str, Any]) -> bytes:
    """Add ``reference_profile.json`` to falcon's uncompressed tar artifact.

    The profile is serialized as plain JSON and written as a single new tar member
    next to ``manifest.json``; every existing member (manifest, onnx, dtypes, …) is
    copied through unchanged. The producer tag is expected to already be present in the
    manifest via ``save_model(extra_tags=...)`` — this only carries the file.
    """
    payload = json.dumps(profile).encode("utf-8")

    source = io.BytesIO(model_bytes)
    output = io.BytesIO()
    with (
        tarfile.open(fileobj=source, mode="r") as src,
        tarfile.open(fileobj=output, mode="w") as dst,
    ):
        for member in src.getmembers():
            if member.name == REFERENCE_PROFILE_FILENAME:
                continue
            content = src.extractfile(member) if member.isreg() else None
            dst.addfile(member, content)

        info = tarfile.TarInfo(name=REFERENCE_PROFILE_FILENAME)
        info.size = len(payload)
        info.mode = 0o644
        dst.addfile(info, io.BytesIO(payload))

    return output.getvalue()
