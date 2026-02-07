from __future__ import annotations

import tarfile
from collections.abc import Iterable
from pathlib import Path

import datasets
import pandas as pd
import polars as pl
import pytest

from luml import __version__ as luml_sdk_version
from luml._constants import PRODUCER_NAME
from luml.artifacts._helpers import add_bytes_to_tar
from luml.artifacts.dataset import (
    DatasetArtifactManifest,
    DatasetReference,
    HFDatasetPayload,
    MaterializedDataset,
    materialize,
    save_hf_dataset,
    save_tabular_dataset,
)


@pytest.fixture
def pandas_ref(tmp_path: Path) -> DatasetReference:
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [10, 20, 30, 40, 50]})
    return save_tabular_dataset(
        df,
        name="pandas-test",
        output_path=str(tmp_path / "pandas.tar"),
    )


@pytest.fixture
def pandas_csv_ref(tmp_path: Path) -> DatasetReference:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [10, 20, 30]})
    return save_tabular_dataset(
        df,
        file_format="csv",
        name="csv-test",
        output_path=str(tmp_path / "csv.tar"),
    )


@pytest.fixture
def chunked_ref(tmp_path: Path) -> DatasetReference:
    df = pd.DataFrame({"a": list(range(10)), "b": list(range(10, 20))})
    return save_tabular_dataset(
        df,
        chunk_size=3,
        name="chunked-test",
        output_path=str(tmp_path / "chunked.tar"),
    )


@pytest.fixture
def hf_ref(tmp_path: Path) -> DatasetReference:
    ds = datasets.DatasetDict(
        {
            "train": datasets.Dataset.from_dict({"a": [1, 2], "b": [10, 20]}),
            "test": datasets.Dataset.from_dict({"a": [3], "b": [30]}),
        }
    )
    return save_hf_dataset(
        ds,
        name="hf-test",
        output_path=str(tmp_path / "hf.tar"),
    )


class TestMaterializeTabular:
    def test_materialize_creates_cache(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        cache = tmp_path / "cache"
        mat = materialize(pandas_ref, cache_dir=cache)
        assert isinstance(mat, MaterializedDataset)
        assert (cache / "manifest.json").exists()

    def test_variant(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        assert mat.variant == "tabular"

    def test_subsets_and_splits(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        assert mat.subsets == ["default"]
        assert "train" in mat.splits("default")

    def test_to_pandas_parquet(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        df = mat.to_pandas()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert list(df.columns) == ["a", "b"]

    def test_to_pandas_csv(
        self, pandas_csv_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_csv_ref, cache_dir=tmp_path / "cache")
        df = mat.to_pandas()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_to_polars_parquet(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        df = mat.to_polars()
        assert isinstance(df, pl.DataFrame)
        assert df.height == 5

    def test_to_pandas_chunked(
        self, chunked_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(chunked_ref, cache_dir=tmp_path / "cache")
        df = mat.to_pandas()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10

    def test_to_polars_chunked(
        self, chunked_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(chunked_ref, cache_dir=tmp_path / "cache")
        df = mat.to_polars()
        assert isinstance(df, pl.DataFrame)
        assert df.height == 10

    def test_cached_extraction(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        cache = tmp_path / "cache"
        mat1 = materialize(pandas_ref, cache_dir=cache)
        mat2 = materialize(pandas_ref, cache_dir=cache)
        assert mat1.to_pandas().equals(mat2.to_pandas())

    def test_to_hf_raises_not_implemented(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        with pytest.raises(NotImplementedError):
            mat.to_hf()

    def test_missing_subset_raises(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        with pytest.raises(KeyError, match="Subset 'nonexistent' not found"):
            mat.splits("nonexistent")


class TestMaterializeHF:
    def test_materialize_creates_cache(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        cache = tmp_path / "cache"
        mat = materialize(hf_ref, cache_dir=cache)
        assert isinstance(mat, MaterializedDataset)
        assert mat.variant == "hf"

    def test_subsets_and_splits(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
        assert mat.subsets == ["default"]
        assert "train" in mat.splits("default")
        assert "test" in mat.splits("default")

    def test_to_hf(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
        ds_dict = mat.to_hf()
        assert isinstance(ds_dict, datasets.DatasetDict)
        assert "train" in ds_dict
        assert "test" in ds_dict
        assert len(ds_dict["train"]) == 2
        assert len(ds_dict["test"]) == 1

    def test_to_hf_split(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
        ds = mat.to_hf_split(split="train")
        assert isinstance(ds, datasets.Dataset)
        assert len(ds) == 2

    def test_to_hf_single_dataset_from_disk(
        self, tmp_path: Path
    ) -> None:
        ds = datasets.Dataset.from_dict({"a": [1, 2]})
        work_dir = tmp_path / "work"
        data_dir = work_dir / "data" / "default"
        data_dir.mkdir(parents=True, exist_ok=True)
        ds.save_to_disk(str(data_dir))

        payload = HFDatasetPayload(
            subsets={"default": ["train"]},
            data_dir="data/",
            library_version=datasets.__version__,
        )
        manifest = DatasetArtifactManifest(
            artifact_type="dataset",
            variant="hf",
            name="hf-single-from-disk",
            description=None,
            version=None,
            producer_name=PRODUCER_NAME,
            producer_version=luml_sdk_version,
            producer_tags=[f"{PRODUCER_NAME}::dataset:v1"],
            payload=payload,
        )

        tar_path = tmp_path / "hf-single.tar"
        with tarfile.open(tar_path, "w") as tar:
            manifest_bytes = manifest.model_dump_json(
                indent=2
            ).encode("utf-8")
            add_bytes_to_tar(tar, "manifest.json", manifest_bytes)
            tar.add(str(work_dir / "data"), arcname="data")

        ref = DatasetReference(str(tar_path))
        mat = materialize(ref, cache_dir=tmp_path / "cache")
        result = mat.to_hf()
        assert isinstance(result, datasets.DatasetDict)
        assert "train" in result
        assert len(result["train"]) == 2

        train = mat.to_hf_split(split="train")
        assert len(train) == 2

    def test_to_pandas(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
        df = mat.to_pandas(split="train")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_to_pandas_handles_iterator(
        self,
        hf_ref: DatasetReference,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")

        def fake_to_pandas(
            self: datasets.Dataset,
        ) -> Iterable[pd.DataFrame]:
            return iter(
                [
                    pd.DataFrame({"a": [1], "b": [10]}),
                    pd.DataFrame({"a": [2], "b": [20]}),
                ]
            )

        monkeypatch.setattr(datasets.Dataset, "to_pandas", fake_to_pandas)
        df = mat.to_pandas(split="train")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_to_polars(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
        df = mat.to_polars(split="train")
        assert isinstance(df, pl.DataFrame)
        assert df.height == 2

    def test_missing_split_raises(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
        with pytest.raises(KeyError, match="Split 'nonexistent' not found"):
            mat.to_hf_split(split="nonexistent")


class TestMaterializeInfo:
    def test_info_returns_manifest(
        self, pandas_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(pandas_ref, cache_dir=tmp_path / "cache")
        info = mat.info()
        assert info["artifact_type"] == "dataset"
        assert info["variant"] == "tabular"


class TestMaterializeHFMultiConfig:
    def test_multiple_configs(self, tmp_path: Path) -> None:
        cola = datasets.DatasetDict(
            {
                "train": datasets.Dataset.from_dict(
                    {"sentence": ["test1"], "label": [0]}
                ),
            }
        )
        sst2 = datasets.DatasetDict(
            {
                "train": datasets.Dataset.from_dict(
                    {"sentence": ["test2"], "label": [1]}
                ),
            }
        )

        ref = save_hf_dataset(
            {"cola": cola, "sst2": sst2},
            output_path=str(tmp_path / "ds.tar"),
        )

        mat = materialize(ref, cache_dir=tmp_path / "cache")

        assert "cola" in mat.subsets
        assert "sst2" in mat.subsets
        assert mat.splits("cola") == ["train"]
        assert mat.splits("sst2") == ["train"]

    def test_to_hf_returns_dict(self, tmp_path: Path) -> None:
        cola = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [1]})}
        )
        sst2 = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [2]})}
        )

        ref = save_hf_dataset(
            {"cola": cola, "sst2": sst2},
            output_path=str(tmp_path / "ds.tar"),
        )

        mat = materialize(ref, cache_dir=tmp_path / "cache")
        result = mat.to_hf()

        assert isinstance(result, dict)
        assert "cola" in result
        assert "sst2" in result
        assert isinstance(result["cola"], datasets.DatasetDict)
        assert isinstance(result["sst2"], datasets.DatasetDict)

    def test_to_hf_config(self, tmp_path: Path) -> None:
        cola = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [1, 2]})}
        )
        sst2 = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [3, 4]})}
        )

        ref = save_hf_dataset(
            {"cola": cola, "sst2": sst2},
            output_path=str(tmp_path / "ds.tar"),
        )

        mat = materialize(ref, cache_dir=tmp_path / "cache")

        cola_loaded = mat.to_hf_config("cola")
        assert isinstance(cola_loaded, datasets.DatasetDict)
        assert len(cola_loaded["train"]) == 2

        sst2_loaded = mat.to_hf_config("sst2")
        assert isinstance(sst2_loaded, datasets.DatasetDict)
        assert len(sst2_loaded["train"]) == 2

    def test_to_hf_split_with_config(self, tmp_path: Path) -> None:
        cola = datasets.DatasetDict(
            {
                "train": datasets.Dataset.from_dict({"a": [1]}),
                "test": datasets.Dataset.from_dict({"a": [2]}),
            }
        )
        sst2 = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [3]})}
        )

        ref = save_hf_dataset(
            {"cola": cola, "sst2": sst2},
            output_path=str(tmp_path / "ds.tar"),
        )

        mat = materialize(ref, cache_dir=tmp_path / "cache")

        cola_train = mat.to_hf_split(subset="cola", split="train")
        assert len(cola_train) == 1
        assert cola_train[0]["a"] == 1

        sst2_train = mat.to_hf_split(subset="sst2", split="train")
        assert len(sst2_train) == 1
        assert sst2_train[0]["a"] == 3

    def test_single_default_config_backward_compat(
        self, tmp_path: Path
    ) -> None:
        ds = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [1, 2, 3]})}
        )

        ref = save_hf_dataset(ds, output_path=str(tmp_path / "ds.tar"))
        mat = materialize(ref, cache_dir=tmp_path / "cache")

        result = mat.to_hf()
        assert isinstance(result, datasets.DatasetDict)
        assert len(result["train"]) == 3

    def test_missing_config_raises(self, tmp_path: Path) -> None:
        cola = datasets.DatasetDict(
            {"train": datasets.Dataset.from_dict({"a": [1]})}
        )

        ref = save_hf_dataset(
            {"cola": cola}, output_path=str(tmp_path / "ds.tar")
        )
        mat = materialize(ref, cache_dir=tmp_path / "cache")

        with pytest.raises(KeyError, match="Config 'sst2' not found"):
            mat.to_hf_config("sst2")
