from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path
from typing import Any

from luml.artifacts._helpers import add_bytes_to_tar
from luml.artifacts.dataset._manifest import (
    DatasetArtifactManifest,
    HFDatasetPayload,
)
from luml.artifacts.dataset._reference import DatasetReference


def save_hf_dataset(
    dataset: Any,  # noqa: ANN401
    name: str | None = None,
    description: str | None = None,
    version: str | None = None,
    output_path: str | None = None,
) -> DatasetReference:
    try:
        import datasets
    except ImportError:
        msg = (
            "The 'datasets' library is required for HuggingFace dataset packaging. "
            "Install with: pip install luml_sdk[datasets-hf]"
        )
        raise ImportError(msg) from None

    from luml import __version__ as luml_sdk_version
    from luml._constants import PRODUCER_NAME

    if isinstance(dataset, datasets.Dataset):
        dataset_dict = datasets.DatasetDict({"default": dataset})
    elif isinstance(dataset, datasets.DatasetDict):
        dataset_dict = dataset
    else:
        msg = (
            f"Unsupported dataset type: {type(dataset).__name__}. "
            "Expected datasets.Dataset or datasets.DatasetDict."
        )
        raise TypeError(msg)

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        data_dir = work_dir / "data"
        dataset_dict.save_to_disk(str(data_dir))

        subset_splits: dict[str, list[str]] = {}
        for split_name in dataset_dict:
            subset_splits.setdefault("default", []).append(split_name)

        payload = HFDatasetPayload(
            subsets=subset_splits,
            data_dir="data/",
            library_version=datasets.__version__,
        )

        manifest = DatasetArtifactManifest(
            artifact_type="dataset",
            variant="hf",
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
            tar.add(str(data_dir), arcname="data")

    return DatasetReference(output_path)
