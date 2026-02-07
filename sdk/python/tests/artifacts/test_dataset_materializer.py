from __future__ import annotations

from pathlib import Path

import datasets
import pandas as pd
import polars as pl
import pytest

from luml.artifacts.dataset import (
    DatasetReference,
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

    def test_to_pandas(
        self, hf_ref: DatasetReference, tmp_path: Path
    ) -> None:
        mat = materialize(hf_ref, cache_dir=tmp_path / "cache")
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
