from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from luml.artifacts.dataset._manifest import (
    DatasetArtifactManifest,
    HFDatasetPayload,
    TabularDatasetPayload,
)
from luml.artifacts.dataset._reference import DatasetReference

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    from datasets import Dataset, DatasetDict

_DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "luml" / "datasets"


def materialize(
    reference: DatasetReference,
    cache_dir: str | Path | None = None,
) -> MaterializedDataset:
    tar_path = Path(reference.path).resolve()
    path_hash = hashlib.sha256(str(tar_path).encode()).hexdigest()[:16]

    if cache_dir is None:
        cache_dir = _DEFAULT_CACHE_ROOT / path_hash
    else:
        cache_dir = Path(cache_dir)

    cache_dir.mkdir(parents=True, exist_ok=True)

    manifest_marker = cache_dir / "manifest.json"
    if not manifest_marker.exists():
        with tarfile.open(str(tar_path), "r") as tar:
            tar.extractall(path=str(cache_dir), filter="data")  # noqa: S202

    manifest = reference.get_manifest()
    return MaterializedDataset(manifest, cache_dir)


class MaterializedDataset:
    def __init__(
        self,
        manifest: DatasetArtifactManifest,
        cache_dir: Path,
    ) -> None:
        self._manifest = manifest
        self._cache_dir = cache_dir

    @property
    def variant(self) -> str:
        return self._manifest.variant

    @property
    def subsets(self) -> list[str]:
        return list(self._manifest.payload.subsets.keys())

    def splits(self, subset: str = "default") -> list[str]:
        payload = self._manifest.payload
        if isinstance(payload, TabularDatasetPayload):
            subset_info = payload.subsets.get(subset)
            if subset_info is None:
                available = list(payload.subsets.keys())
                msg = f"Subset '{subset}' not found. Available: {available}"
                raise KeyError(msg)
            return list(subset_info.splits.keys())
        if isinstance(payload, HFDatasetPayload):
            splits = payload.subsets.get(subset)
            if splits is None:
                available = list(payload.subsets.keys())
                msg = f"Subset '{subset}' not found. Available: {available}"
                raise KeyError(msg)
            return splits
        msg = f"Unknown payload type: {type(payload).__name__}"
        raise TypeError(msg)

    def _get_tabular_chunk_paths(
        self,
        subset: str,
        split: str,
    ) -> list[Path]:
        payload = self._manifest.payload
        if not isinstance(payload, TabularDatasetPayload):
            msg = "Not a tabular dataset"
            raise TypeError(msg)

        subset_info = payload.subsets.get(subset)
        if subset_info is None:
            msg = f"Subset '{subset}' not found"
            raise KeyError(msg)

        split_info = subset_info.splits.get(split)
        if split_info is None:
            msg = f"Split '{split}' not found in subset '{subset}'"
            raise KeyError(msg)

        return [self._cache_dir / f for f in split_info.chunk_files]

    def to_pandas(
        self,
        subset: str = "default",
        split: str = "train",
    ) -> pd.DataFrame:
        try:
            import pandas as pd
        except ImportError:
            msg = (
                "pandas is required for this operation. "
                "Install with: pip install luml_sdk[datasets]"
            )
            raise ImportError(msg) from None

        payload = self._manifest.payload

        if isinstance(payload, TabularDatasetPayload):
            chunk_paths = self._get_tabular_chunk_paths(subset, split)
            split_info = payload.subsets[subset].splits[split]
            frames = []
            for path in chunk_paths:
                if split_info.file_format == "csv":
                    frames.append(pd.read_csv(path))
                else:
                    frames.append(pd.read_parquet(path))
            if len(frames) > 1:
                return pd.concat(frames, ignore_index=True)
            return frames[0]

        if isinstance(payload, HFDatasetPayload):
            hf_split = self.to_hf_split(subset, split)
            return hf_split.to_pandas()

        msg = f"Unknown payload type: {type(payload).__name__}"
        raise TypeError(msg)

    def to_polars(
        self,
        subset: str = "default",
        split: str = "train",
    ) -> pl.DataFrame:
        try:
            import polars as pl
        except ImportError:
            msg = (
                "polars is required for this operation. "
                "Install with: pip install luml_sdk[datasets-polars]"
            )
            raise ImportError(msg) from None

        payload = self._manifest.payload

        if isinstance(payload, TabularDatasetPayload):
            chunk_paths = self._get_tabular_chunk_paths(subset, split)
            split_info = payload.subsets[subset].splits[split]
            frames = []
            for path in chunk_paths:
                if split_info.file_format == "csv":
                    frames.append(pl.read_csv(path))
                else:
                    frames.append(pl.read_parquet(path))
            if len(frames) > 1:
                return pl.concat(frames)
            return frames[0]

        if isinstance(payload, HFDatasetPayload):
            hf_split = self.to_hf_split(subset, split)
            return pl.from_pandas(hf_split.to_pandas())

        msg = f"Unknown payload type: {type(payload).__name__}"
        raise TypeError(msg)

    def to_hf(self) -> DatasetDict:
        try:
            from datasets import load_from_disk
        except ImportError:
            msg = (
                "The 'datasets' library is required for this operation. "
                "Install with: pip install luml_sdk[datasets-hf]"
            )
            raise ImportError(msg) from None

        payload = self._manifest.payload

        if isinstance(payload, HFDatasetPayload):
            data_path = self._cache_dir / payload.data_dir
            return load_from_disk(str(data_path))

        msg = (
            "to_hf() is only supported for HuggingFace dataset variants"
        )
        raise NotImplementedError(msg)

    def to_hf_split(
        self,
        subset: str = "default",
        split: str = "train",
    ) -> Dataset:
        dataset_dict = self.to_hf()
        payload = self._manifest.payload

        if isinstance(payload, HFDatasetPayload):
            subset_splits = payload.subsets.get(subset)
            if subset_splits is None:
                msg = f"Subset '{subset}' not found"
                raise KeyError(msg)

            if split not in subset_splits:
                msg = (
                    f"Split '{split}' not found in subset '{subset}'"
                )
                raise KeyError(msg)

            return dataset_dict[split]

        msg = (
            "to_hf_split() is only supported for "
            "HuggingFace dataset variants"
        )
        raise NotImplementedError(msg)

    def info(self) -> dict[str, Any]:
        manifest_path = self._cache_dir / "manifest.json"
        with open(manifest_path) as f:
            return json.loads(f.read())
