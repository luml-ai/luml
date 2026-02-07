from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from luml.artifacts.dataset import (
    DatasetReference,
    TabularDatasetPayload,
    save_tabular_dataset,
)


@pytest.fixture
def sample_pandas_df() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


@pytest.fixture
def sample_polars_df() -> pl.DataFrame:
    return pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


class TestSaveTabularDatasetPandas:
    def test_single_dataframe_parquet(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_pandas_df,
            name="test-ds",
            output_path=str(tmp_path / "ds.tar"),
        )
        assert isinstance(ref, DatasetReference)
        assert Path(ref.path).exists()

        manifest = ref.get_manifest()
        assert manifest.artifact_type == "dataset"
        assert manifest.variant == "tabular"
        assert manifest.name == "test-ds"
        assert isinstance(manifest.payload, TabularDatasetPayload)
        assert manifest.payload.file_format == "parquet"
        assert manifest.payload.total_rows == 3
        assert "default" in manifest.payload.subsets
        assert "train" in manifest.payload.subsets["default"].splits

    def test_single_dataframe_csv(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_pandas_df,
            file_format="csv",
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        assert manifest.payload.file_format == "csv"

    def test_split_dict(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            {"train": sample_pandas_df, "test": sample_pandas_df},
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        splits = manifest.payload.subsets["default"].splits
        assert "train" in splits
        assert "test" in splits

    def test_full_subset_dict(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            {
                "subset_a": {"train": sample_pandas_df},
                "subset_b": {"train": sample_pandas_df, "val": sample_pandas_df},
            },
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        assert "subset_a" in manifest.payload.subsets
        assert "subset_b" in manifest.payload.subsets
        assert "val" in manifest.payload.subsets["subset_b"].splits

    def test_chunking(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_pandas_df,
            chunk_size=2,
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        split_info = manifest.payload.subsets["default"].splits["train"]
        assert split_info.num_chunks == 2
        assert len(split_info.chunk_files) == 2

    def test_auto_output_path(self, sample_pandas_df: pd.DataFrame) -> None:
        ref = save_tabular_dataset(sample_pandas_df)
        assert Path(ref.path).exists()
        Path(ref.path).unlink()

    def test_validate(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_pandas_df,
            output_path=str(tmp_path / "ds.tar"),
        )
        assert ref.validate() is True

    def test_tar_contains_data_files(
        self, sample_pandas_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_pandas_df,
            output_path=str(tmp_path / "ds.tar"),
        )
        files = ref.list_files()
        assert "manifest.json" in files
        data_files = [f for f in files if f.startswith("data/")]
        assert len(data_files) == 1
        assert data_files[0].endswith(".parquet")


class TestSaveTabularDatasetPolars:
    def test_single_dataframe_parquet(
        self, sample_polars_df: pl.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_polars_df,
            name="polars-ds",
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        assert manifest.payload.total_rows == 3

    def test_single_dataframe_csv(
        self, sample_polars_df: pl.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_polars_df,
            file_format="csv",
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        assert manifest.payload.file_format == "csv"

    def test_chunking(
        self, sample_polars_df: pl.DataFrame, tmp_path: Path
    ) -> None:
        ref = save_tabular_dataset(
            sample_polars_df,
            chunk_size=2,
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        split_info = manifest.payload.subsets["default"].splits["train"]
        assert split_info.num_chunks == 2


class TestSaveTabularDatasetFromFile:
    def test_from_csv_path(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "input.csv"
        csv_file.write_text("a,b\n1,x\n2,y\n")
        ref = save_tabular_dataset(
            str(csv_file),
            file_format="csv",
            output_path=str(tmp_path / "ds.tar"),
        )
        manifest = ref.get_manifest()
        assert isinstance(manifest.payload, TabularDatasetPayload)
        assert manifest.payload.subsets["default"].splits["train"].num_rows == -1

    def test_from_path_object(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "input.csv"
        csv_file.write_text("a,b\n1,x\n")
        ref = save_tabular_dataset(
            csv_file,
            file_format="csv",
            output_path=str(tmp_path / "ds.tar"),
        )
        assert ref.validate() is True

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            save_tabular_dataset(
                str(tmp_path / "nonexistent.csv"),
                output_path=str(tmp_path / "ds.tar"),
            )


class TestSaveTabularDatasetErrors:
    def test_invalid_input_type(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="Unsupported input type"):
            save_tabular_dataset(42, output_path=str(tmp_path / "ds.tar"))
