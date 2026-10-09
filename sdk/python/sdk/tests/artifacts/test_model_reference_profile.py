import io
import json
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray
from sklearn.linear_model import LinearRegression  # type: ignore[import-untyped]

from luml.artifacts.model import ModelReference
from luml.integrations.sklearn import save_sklearn
from luml.utils.packaging import REFERENCE_PROFILE_FILENAME, TABULAR_MONITORING_TAG

LLM_KIND_TAG = "luml.ai::kind_llm:v1"
TABULAR_KIND_TAG = "luml.ai::kind_tabular:v1"


def _save_model(
    tmp_path: Path,
    *,
    extra_tags: list[str] | None = None,
) -> tuple[ModelReference, NDArray[np.float64]]:
    rng = np.random.default_rng(12)
    features = rng.normal(size=(80, 3))
    target = features[:, 0] * 2.0 - features[:, 1]
    estimator = LinearRegression().fit(features, target)
    reference = save_sklearn(
        estimator,
        features,
        path=str(tmp_path / "model.luml"),
        manifest_extra_producer_tags=extra_tags,
    )
    return reference, features


def _replace_producer_tags(path: Path, tags: list[str]) -> None:
    source = io.BytesIO(path.read_bytes())
    output = io.BytesIO()

    with (
        tarfile.open(fileobj=source, mode="r") as src,
        tarfile.open(fileobj=output, mode="w") as dst,
    ):
        for member in src.getmembers():
            content = None
            if member.isreg():
                extracted = src.extractfile(member)
                assert extracted is not None
                content = extracted.read()
            if member.name == "manifest.json":
                assert content is not None
                manifest = json.loads(content)
                manifest["producer_tags"] = tags
                content = json.dumps(manifest).encode("utf-8")
                member.size = len(content)
            dst.addfile(member, io.BytesIO(content) if content is not None else None)

    path.write_bytes(output.getvalue())


def _archive_state(
    path: Path,
) -> tuple[list[str], list[str], dict[str, Any]]:
    with tarfile.open(path, "r") as archive:
        names = archive.getnames()
        manifest_file = archive.extractfile("manifest.json")
        profile_file = archive.extractfile(REFERENCE_PROFILE_FILENAME)
        assert manifest_file is not None
        assert profile_file is not None
        manifest = json.load(manifest_file)
        profile = json.load(profile_file)
    return names, manifest["producer_tags"], profile


def test_add_reference_profile_embeds_and_replaces_profile(tmp_path: Path) -> None:
    reference, features = _save_model(tmp_path)
    path = Path(reference.path)
    manifest = reference.get_manifest()
    tags_without_kind = [
        tag for tag in manifest["producer_tags"] if tag != TABULAR_KIND_TAG
    ]
    _replace_producer_tags(path, tags_without_kind)

    first_profile = reference.add_reference_profile(features)
    first_names, first_tags, embedded_first = _archive_state(path)

    assert embedded_first == first_profile
    assert first_names.count(REFERENCE_PROFILE_FILENAME) == 1
    assert first_tags.count(TABULAR_KIND_TAG) == 1
    assert first_tags.count(TABULAR_MONITORING_TAG) == 1
    assert reference.validate()

    second_profile = reference.add_reference_profile(features + 5.0)
    second_names, second_tags, embedded_second = _archive_state(path)

    assert embedded_second == second_profile
    assert embedded_second != embedded_first
    assert second_names.count(REFERENCE_PROFILE_FILENAME) == 1
    assert second_tags.count(TABULAR_KIND_TAG) == 1
    assert second_tags.count(TABULAR_MONITORING_TAG) == 1
    assert reference.validate()


def test_add_reference_profile_refuses_llm_without_changing_bundle(
    tmp_path: Path,
) -> None:
    reference, features = _save_model(tmp_path, extra_tags=[LLM_KIND_TAG])
    path = Path(reference.path)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="LLM"):
        reference.add_reference_profile(features)

    assert path.read_bytes() == before
