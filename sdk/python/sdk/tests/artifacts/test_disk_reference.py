import io
import json
import tarfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from luml.artifacts._base import (
    ArtifactManifest,
    DiskFile,
    DiskReference,
    MemoryFile,
)


def _create_tar(
    tmp_path: Path,
    manifest_data: dict,
    extra_files: dict[str, bytes] | None = None,
) -> str:
    tar_path = str(tmp_path / "test.tar")
    manifest_bytes = json.dumps(manifest_data).encode("utf-8")
    with tarfile.open(tar_path, "w") as tar:
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        tar.addfile(info, fileobj=io.BytesIO(manifest_bytes))
        for name, content in (extra_files or {}).items():
            fi = tarfile.TarInfo(name=name)
            fi.size = len(content)
            tar.addfile(fi, fileobj=io.BytesIO(content))
    return tar_path


def _dataset_manifest() -> dict:
    return {
        "artifact_type": "dataset",
        "variant": "tabular",
        "name": "test-dataset",
        "producer_name": "luml.ai",
        "producer_version": "1.0.0",
        "producer_tags": ["dataforce.studio::dataset:v1"],
        "payload": {"rows": 100},
    }


def _experiment_manifest() -> dict:
    return {
        "artifact_type": "experiment",
        "variant": "experiment_snapshot",
        "name": "test-exp",
        "producer_name": "luml.ai",
        "producer_version": "1.0.0",
        "producer_tags": ["dataforce.studio::experiment_snapshot:v1"],
        "payload": {},
    }


# --- ArtifactManifest ---


class TestArtifactManifest:
    def test_valid_manifest(self) -> None:
        manifest = ArtifactManifest.model_validate(_dataset_manifest())
        assert manifest.artifact_type == "dataset"
        assert manifest.payload == {"rows": 100}

    def test_optional_fields_default_to_none(self) -> None:
        data = {
            "artifact_type": "experiment",
            "variant": "snapshot",
            "producer_name": "luml.ai",
            "producer_version": "1.0.0",
            "producer_tags": [],
            "payload": {},
        }
        manifest = ArtifactManifest.model_validate(data)
        assert manifest.name is None
        assert manifest.description is None
        assert manifest.version is None

    def test_missing_required_field_raises(self) -> None:
        data = _dataset_manifest()
        del data["artifact_type"]
        with pytest.raises(ValidationError):
            ArtifactManifest.model_validate(data)

    def test_serialization_roundtrip(self) -> None:
        manifest = ArtifactManifest.model_validate(_dataset_manifest())
        restored = ArtifactManifest.model_validate_json(manifest.model_dump_json())
        assert restored == manifest


# --- DiskReference ---


class TestDiskReference:
    def test_get_manifest(self, tmp_path: Path) -> None:
        tar_path = _create_tar(tmp_path, {"key": "value"})
        ref = DiskReference(tar_path)
        assert ref.get_manifest() == {"key": "value"}

    def test_validate_success(self, tmp_path: Path) -> None:
        tar_path = _create_tar(tmp_path, {"key": "value"})
        assert DiskReference(tar_path).validate() is True

    def test_validate_failure(self, tmp_path: Path) -> None:
        assert DiskReference(str(tmp_path / "nope.tar")).validate() is False

    def test_list_files(self, tmp_path: Path) -> None:
        tar_path = _create_tar(tmp_path, {}, extra_files={"data/file.txt": b"hello"})
        files = DiskReference(tar_path).list_files()
        assert "manifest.json" in files
        assert "data/file.txt" in files

    def test_extract_file(self, tmp_path: Path) -> None:
        tar_path = _create_tar(tmp_path, {}, extra_files={"data.bin": b"binary"})
        assert DiskReference(tar_path).extract_file("data.bin") == b"binary"

    def test_extract_file_not_found(self, tmp_path: Path) -> None:
        tar_path = _create_tar(tmp_path, {})
        with pytest.raises(KeyError):
            DiskReference(tar_path).extract_file("nope.txt")

    def test_tar_without_manifest(self, tmp_path: Path) -> None:
        tar_path = str(tmp_path / "no_manifest.tar")
        with tarfile.open(tar_path, "w") as tar:
            data = b"x"
            info = tarfile.TarInfo(name="data.bin")
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))
        assert DiskReference(tar_path).validate() is False


def test_disk_artifact(tmp_path: Path) -> None:
    p = tmp_path / "test.bin"
    p.write_bytes(b"binary data")
    assert DiskFile(p).get_content() == b"binary data"


def test_memory_artifact() -> None:
    assert MemoryFile(b"in-memory").get_content() == b"in-memory"
