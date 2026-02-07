from __future__ import annotations

from pathlib import Path

import datasets
import pytest

from luml.artifacts.dataset import (
    DatasetReference,
    HFDatasetPayload,
    save_hf_dataset,
)


@pytest.fixture
def sample_hf_dataset() -> datasets.Dataset:
    return datasets.Dataset.from_dict({"a": [1, 2, 3], "b": ["x", "y", "z"]})


@pytest.fixture
def sample_hf_dataset_dict() -> datasets.DatasetDict:
    return datasets.DatasetDict(
        {
            "train": datasets.Dataset.from_dict({"a": [1, 2], "b": ["x", "y"]}),
            "test": datasets.Dataset.from_dict({"a": [3], "b": ["z"]}),
        }
    )


class TestSaveHFDataset:
    def test_single_dataset(
        self, sample_hf_dataset: datasets.Dataset, tmp_path: Path
    ) -> None:
        ref = save_hf_dataset(
            sample_hf_dataset,
            name="hf-ds",
            output_path=str(tmp_path / "ds.tar"),
        )
        assert isinstance(ref, DatasetReference)
        assert Path(ref.path).exists()

        manifest = ref.get_manifest()
        assert manifest.artifact_type == "dataset"
        assert manifest.variant == "hf"
        assert manifest.name == "hf-ds"
        assert isinstance(manifest.payload, HFDatasetPayload)
        assert manifest.payload.data_dir == "data/"
        assert "default" in manifest.payload.subsets
        assert "default" in manifest.payload.subsets["default"]

    def test_dataset_dict(
        self, sample_hf_dataset_dict: datasets.DatasetDict, tmp_path: Path
    ) -> None:
        ref = save_hf_dataset(
            sample_hf_dataset_dict,
            name="hf-dict-ds",
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, HFDatasetPayload)
        assert "train" in manifest.payload.subsets["default"]
        assert "test" in manifest.payload.subsets["default"]

    def test_auto_output_path(
        self, sample_hf_dataset: datasets.Dataset
    ) -> None:
        ref = save_hf_dataset(sample_hf_dataset)
        assert Path(ref.path).exists()
        Path(ref.path).unlink()

    def test_validate(
        self, sample_hf_dataset: datasets.Dataset, tmp_path: Path
    ) -> None:
        ref = save_hf_dataset(
            sample_hf_dataset,
            output_path=str(tmp_path / "ds.tar"),
        )
        assert ref.validate() is True

    def test_tar_contains_data(
        self, sample_hf_dataset: datasets.Dataset, tmp_path: Path
    ) -> None:
        ref = save_hf_dataset(
            sample_hf_dataset,
            output_path=str(tmp_path / "ds.tar"),
        )
        files = ref.list_files()
        assert "manifest.json" in files
        data_files = [f for f in files if f.startswith("data/")]
        assert len(data_files) > 0

    def test_library_version_recorded(
        self, sample_hf_dataset: datasets.Dataset, tmp_path: Path
    ) -> None:
        ref = save_hf_dataset(
            sample_hf_dataset,
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, HFDatasetPayload)
        assert manifest.payload.library_version == datasets.__version__


class TestSaveHFDatasetErrors:
    def test_invalid_type(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="Unsupported dataset type"):
            save_hf_dataset({"a": [1, 2]}, output_path=str(tmp_path / "ds.tar"))
