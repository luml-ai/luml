from __future__ import annotations

import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Literal

from luml.artifacts._helpers import add_bytes_to_tar
from luml.artifacts.dataset._manifest import (
    DatasetArtifactManifest,
    TabularDatasetPayload,
    TabularSplitInfo,
    TabularSubsetInfo,
)
from luml.artifacts.dataset._reference import DatasetReference

SplitInput = Any
SubsetDict = dict[str, SplitInput]
FullInput = dict[str, SubsetDict]


def _is_pandas_dataframe(obj: object) -> bool:
    mod = type(obj).__module__
    return mod.startswith("pandas") and type(obj).__name__ == "DataFrame"


def _is_polars_dataframe(obj: object) -> bool:
    mod = type(obj).__module__
    return mod.startswith("polars") and type(obj).__name__ == "DataFrame"


def _is_dataframe(obj: object) -> bool:
    return _is_pandas_dataframe(obj) or _is_polars_dataframe(obj)


def _normalize_input(
    data: SplitInput | SubsetDict | FullInput,  # noqa: ANN401
) -> dict[str, dict[str, Any]]:
    if _is_dataframe(data) or isinstance(data, str | Path):
        return {"default": {"train": data}}

    if isinstance(data, dict):
        first_value = next(iter(data.values()), None)
        if isinstance(first_value, dict):
            return data  # type: ignore[return-value]
        return {"default": data}

    msg = (
        f"Unsupported input type: {type(data).__name__}. "
        "Expected a DataFrame, file path, or dict of splits/subsets."
    )
    raise TypeError(msg)


def _get_row_count(obj: object) -> int:
    if _is_pandas_dataframe(obj):
        return len(obj)  # type: ignore[arg-type]
    if _is_polars_dataframe(obj):
        return obj.height  # type: ignore[union-attr]
    msg = f"Cannot get row count from {type(obj).__name__}"
    raise TypeError(msg)


def _write_chunk(
    obj: object,
    path: Path,
    file_format: Literal["csv", "parquet"],
) -> None:
    if _is_pandas_dataframe(obj):
        if file_format == "csv":
            obj.to_csv(path, index=False)  # type: ignore[union-attr]
        else:
            obj.to_parquet(path, index=False)  # type: ignore[union-attr]
    elif _is_polars_dataframe(obj):
        if file_format == "csv":
            obj.write_csv(path)  # type: ignore[union-attr]
        else:
            obj.write_parquet(path)  # type: ignore[union-attr]
    else:
        msg = f"Cannot write {type(obj).__name__} as {file_format}"
        raise TypeError(msg)


def _chunk_dataframe(
    obj: object,
    chunk_size: int,
) -> list[object]:
    if _is_pandas_dataframe(obj):
        return [
            obj.iloc[i : i + chunk_size]  # type: ignore[union-attr]
            for i in range(0, len(obj), chunk_size)  # type: ignore[arg-type]
        ]
    if _is_polars_dataframe(obj):
        return [
            obj.slice(i, chunk_size)  # type: ignore[union-attr]
            for i in range(0, obj.height, chunk_size)  # type: ignore[union-attr]
        ]
    msg = f"Cannot chunk {type(obj).__name__}"
    raise TypeError(msg)


def _process_split(
    data: object,
    subset_name: str,
    split_name: str,
    file_format: Literal["csv", "parquet"],
    chunk_size: int | None,
    work_dir: Path,
) -> tuple[TabularSplitInfo, list[tuple[str, Path]]]:
    split_dir = work_dir / "data" / subset_name / split_name
    split_dir.mkdir(parents=True, exist_ok=True)

    files: list[tuple[str, Path]] = []

    if isinstance(data, str | Path):
        src_path = Path(data)
        if not src_path.exists():
            msg = f"File not found: {src_path}"
            raise FileNotFoundError(msg)
        arc_name = (
            f"data/{subset_name}/{split_name}/chunk_000.{file_format}"
        )
        dest = split_dir / f"chunk_000.{file_format}"
        shutil.copy2(src_path, dest)
        files.append((arc_name, dest))
        return (
            TabularSplitInfo(
                file_format=file_format,
                num_rows=-1,
                num_chunks=1,
                chunk_files=[arc_name],
            ),
            files,
        )

    if not _is_dataframe(data):
        msg = (
            f"Unsupported split data type: {type(data).__name__}. "
            "Expected a DataFrame or file path."
        )
        raise TypeError(msg)

    num_rows = _get_row_count(data)

    if chunk_size is not None and chunk_size > 0:
        chunks = _chunk_dataframe(data, chunk_size)
    else:
        chunks = [data]

    chunk_files: list[str] = []
    for i, chunk in enumerate(chunks):
        chunk_filename = f"chunk_{i:03d}.{file_format}"
        arc_name = f"data/{subset_name}/{split_name}/{chunk_filename}"
        dest = split_dir / chunk_filename
        _write_chunk(chunk, dest, file_format)
        files.append((arc_name, dest))
        chunk_files.append(arc_name)

    split_info = TabularSplitInfo(
        file_format=file_format,
        num_rows=num_rows,
        num_chunks=len(chunks),
        chunk_files=chunk_files,
    )
    return split_info, files


def save_tabular_dataset(
    data: SplitInput | SubsetDict | FullInput,  # noqa: ANN401
    file_format: Literal["csv", "parquet"] = "parquet",
    chunk_size: int | None = None,
    name: str | None = None,
    description: str | None = None,
    version: str | None = None,
    output_path: str | None = None,
) -> DatasetReference:
    from luml import __version__ as luml_sdk_version
    from luml._constants import PRODUCER_NAME

    normalized = _normalize_input(data)

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        subsets: dict[str, TabularSubsetInfo] = {}
        all_files: list[tuple[str, Path]] = []
        total_rows = 0

        for subset_name, splits in normalized.items():
            split_infos: dict[str, TabularSplitInfo] = {}
            for split_name, split_data in splits.items():
                split_info, files = _process_split(
                    split_data,
                    subset_name,
                    split_name,
                    file_format,
                    chunk_size,
                    work_dir,
                )
                split_infos[split_name] = split_info
                all_files.extend(files)
                if split_info.num_rows >= 0:
                    total_rows += split_info.num_rows

            subsets[subset_name] = TabularSubsetInfo(splits=split_infos)

        payload = TabularDatasetPayload(
            subsets=subsets,
            total_rows=total_rows,
            file_format=file_format,
        )

        manifest = DatasetArtifactManifest(
            artifact_type="dataset",
            variant="tabular",
            name=name,
            description=description,
            version=version,
            producer_name=PRODUCER_NAME,
            producer_version=luml_sdk_version,
            producer_tags=[f"{PRODUCER_NAME}::dataset:v1"],
            payload=payload,
        )

        if output_path is None:
            with tempfile.NamedTemporaryFile(
                suffix=".tar", delete=False
            ) as tmp:
                output_path = tmp.name

        manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")

        with tarfile.open(output_path, "w") as tar:
            add_bytes_to_tar(tar, "manifest.json", manifest_bytes)
            for arc_name, local_path in all_files:
                tar.add(str(local_path), arcname=arc_name)

    return DatasetReference(output_path)
