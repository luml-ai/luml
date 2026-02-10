from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from luml.artifacts._base import ArtifactManifest


class TabularSplitInfo(BaseModel):
    file_format: Literal["csv", "parquet"]
    num_rows: int
    num_chunks: int
    chunk_files: list[str]


class TabularSubsetInfo(BaseModel):
    splits: dict[str, TabularSplitInfo]


class TabularDatasetPayload(BaseModel):
    subsets: dict[str, TabularSubsetInfo]
    total_rows: int
    file_format: Literal["csv", "parquet"]


class HFDatasetPayload(BaseModel):
    subsets: dict[str, list[str]]
    data_dir: str
    library_version: str


class DatasetArtifactManifest(ArtifactManifest):
    variant: Literal["tabular", "hf"]
    payload: TabularDatasetPayload | HFDatasetPayload
