import hashlib
import io
import json
import tarfile
from pathlib import Path

from luml_api._types import ArtifactFileDetails
from luml_api.handlers.model_artifacts import ModelFileHandler


def _build_tar(
    path: Path,
    *,
    meta: object | None = None,
    manifest: object | None = None,
    extra_files: dict[str, bytes] | None = None,
) -> str:
    members: dict[str, bytes] = {}
    if meta is not None:
        members["meta.json"] = json.dumps(meta).encode("utf-8")
    if manifest is not None:
        members["manifest.json"] = json.dumps(manifest).encode("utf-8")
    if extra_files:
        members.update(extra_files)

    with tarfile.open(path, "w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return str(path)


def test_file_name_size_and_hash(tmp_path: Path) -> None:
    file_path = _build_tar(tmp_path / "model.fnnx", manifest={})
    expected_hash = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()

    details = ModelFileHandler(file_path).artifact_details()

    assert details.file_name == "model.fnnx"
    assert details.size == Path(file_path).stat().st_size
    assert details.file_hash == expected_hash


def test_manifest_parsed(tmp_path: Path) -> None:
    manifest = {"producer_tags": ["dataforce.studio::tabular_classification:v1"]}
    file_path = _build_tar(tmp_path / "model.fnnx", manifest=manifest)

    details = ModelFileHandler(file_path).artifact_details()

    assert details.manifest == manifest


def test_metadata_missing_returns_empty_extra_values(tmp_path: Path) -> None:
    file_path = _build_tar(tmp_path / "model.fnnx", manifest={"producer_tags": []})

    details = ModelFileHandler(file_path).artifact_details()

    assert details.extra_values == {}


def test_file_index(tmp_path: Path) -> None:
    file_path = _build_tar(
        tmp_path / "model.fnnx",
        manifest={},
        extra_files={"weights.bin": b"abcdef"},
    )

    details = ModelFileHandler(file_path).artifact_details()

    assert "weights.bin" in details.file_index
    offset, size = details.file_index["weights.bin"]
    assert size == 6
    assert isinstance(offset, int)


def test_extra_values_tabular_eval_holdout(tmp_path: Path) -> None:
    manifest = {"producer_tags": ["dataforce.studio::tabular_classification:v1"]}
    meta = [
        {
            "producer_tags": [
                "falcon.beastbyte.ai::tabular_classification_metrics:v1"
            ],
            "payload": {
                "metrics": {
                    "performance": {
                        "eval_holdout": {"accuracy": 0.9, "N_SAMPLES": 100}
                    }
                }
            },
        }
    ]
    file_path = _build_tar(tmp_path / "model.fnnx", meta=meta, manifest=manifest)

    details = ModelFileHandler(file_path).artifact_details()

    # N_SAMPLES is filtered out
    assert details.extra_values == {"accuracy": 0.9}


def test_extra_values_tabular_eval_cv_fallback(tmp_path: Path) -> None:
    manifest = {"producer_tags": ["dataforce.studio::tabular_regression:v1"]}
    meta = [
        {
            "producer_tags": [
                "falcon.beastbyte.ai::tabular_regression_metrics:v1"
            ],
            "payload": {
                "metrics": {"performance": {"eval_cv": {"rmse": 1.5}}}
            },
        }
    ]
    file_path = _build_tar(tmp_path / "model.fnnx", meta=meta, manifest=manifest)

    details = ModelFileHandler(file_path).artifact_details()

    assert details.extra_values == {"rmse": 1.5}


def test_extra_values_custom_registry_metrics(tmp_path: Path) -> None:
    manifest = {"producer_tags": ["some-other-tag"]}
    meta = [
        {
            "producer_tags": ["dataforce.studio::registry_metrics:v1"],
            "payload": {"metrics": {"f1": 0.7}},
        }
    ]
    file_path = _build_tar(tmp_path / "model.fnnx", meta=meta, manifest=manifest)

    details = ModelFileHandler(file_path).artifact_details()

    assert details.extra_values == {"f1": 0.7}


def test_extra_values_empty_when_nothing_matches(tmp_path: Path) -> None:
    file_path = _build_tar(
        tmp_path / "model.fnnx", meta=[], manifest={"producer_tags": []}
    )

    details = ModelFileHandler(file_path).artifact_details()

    assert details.extra_values == {}


def test_artifact_details(tmp_path: Path) -> None:
    manifest: dict = {"producer_tags": []}
    file_path = _build_tar(
        tmp_path / "model.fnnx",
        meta=[],
        manifest=manifest,
        extra_files={"weights.bin": b"abc"},
    )

    details = ModelFileHandler(file_path).artifact_details()

    assert isinstance(details, ArtifactFileDetails)
    assert details.file_name == "model.fnnx"
    assert details.size == Path(file_path).stat().st_size
    assert details.manifest == manifest
    assert details.extra_values == {}
    assert "weights.bin" in details.file_index
