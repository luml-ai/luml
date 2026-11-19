"""Describe workspace LUML packages without unpacking their payloads."""

import json
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from luml.artifacts.dataset import HFDatasetPayload, TabularDatasetPayload
from luml.artifacts.model import ModelReference
from pydantic import ValidationError

from lumlflow.flow.daemon.files import os_errors, regular_file
from lumlflow.flow.errors import FlowError


def luml_file(path: str) -> Path:
    file = regular_file(path)
    if file.suffix.lower() != ".luml":
        raise FlowError("Choose a .luml file")
    return file


def _json_object(
    tar: tarfile.TarFile, members: dict[str, tarfile.TarInfo], name: str
) -> dict[str, Any] | None:
    member = members.get(name)
    if member is None:
        return None
    stream = tar.extractfile(member)
    assert stream is not None  # members contains regular files only
    with stream:
        try:
            value = json.load(stream)
        except (ValueError, RecursionError):
            return None
    return value if isinstance(value, dict) else None


def _rows(count: object) -> int | None:
    return count if type(count) is int and count >= 0 else None


def _tabular_splits(payload: TabularDatasetPayload) -> list[dict[str, Any]]:
    return [
        {
            "subset": subset,
            "name": name,
            "format": info.file_format,
            "files": info.chunk_files,
            "num_rows": _rows(info.num_rows),
        }
        for subset, config in payload.subsets.items()
        for name, info in config.splits.items()
    ]


def _hf_splits(
    tar: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    payload: HFDatasetPayload,
) -> list[dict[str, Any]]:
    chunks: dict[str, list[str]] = defaultdict(list)
    for path in sorted(members):
        if path.endswith(".arrow"):
            chunks[path.rpartition("/")[0]].append(path)

    splits = []
    for subset, names in payload.subsets.items():
        for name in names:
            folder = f"data/{subset}/{name}"
            info = _json_object(tar, members, f"{folder}/dataset_info.json") or {}
            counts = info.get("splits")
            split_info = counts.get(name) if isinstance(counts, dict) else None
            count = (
                split_info.get("num_examples") if isinstance(split_info, dict) else None
            )
            splits.append(
                {
                    "subset": subset,
                    "name": name,
                    "format": "arrow",
                    "files": chunks[folder],
                    "num_rows": _rows(count),
                }
            )
    return splits


@os_errors()
def inspect_archive(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": "unknown", "manifest": None, "files": []}
    try:
        with tarfile.open(path, "r:") as tar:
            members = {entry.name: entry for entry in tar if entry.isfile()}
            result["files"] = [
                {"name": name, "size": entry.size} for name, entry in members.items()
            ]
            manifest = _json_object(tar, members, "manifest.json")
            result["manifest"] = manifest
            kind = (manifest or {}).get("artifact_type")
            if kind == "experiment":
                result["kind"] = kind
                return result
            if manifest is not None and kind == "dataset":
                variant = manifest.get("variant")
                payload = manifest.get("payload")
                result.update(kind=kind, variant=None, splits=[])
                try:
                    if variant == "hf":
                        result["variant"] = variant
                        hf = HFDatasetPayload.model_validate(payload, strict=True)
                        result["splits"] = _hf_splits(tar, members, hf)
                    elif variant == "tabular":
                        result["variant"] = variant
                        tabular = TabularDatasetPayload.model_validate(
                            payload, strict=True
                        )
                        result["splits"] = _tabular_splits(tabular)
                except ValidationError:
                    # The manifest can still be displayed when its preview fields
                    # are incomplete or from another dataset format version.
                    pass
                return result
    except (tarfile.TarError, EOFError):
        return result

    # The SDK's model check parses fnnx metadata without loading model weights.
    try:
        ModelReference(str(path)).read()
    except OSError:
        raise
    except Exception:
        return result
    result["kind"] = "model"
    return result
