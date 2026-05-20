from __future__ import annotations

import io
import json
import tarfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class PathSeparators(str, Enum):
    COLON = "~c~"
    SLASH = "~s~"
    ENDTAG = "~~et~~"


class _BaseFile(ABC):
    @abstractmethod
    def get_content(self) -> bytes:
        pass


class DiskFile(_BaseFile):
    def __init__(self, path: str | Path) -> None:
        self.path = path

    def get_content(self) -> bytes:
        with open(self.path, "rb") as f:
            return f.read()


class MemoryFile(_BaseFile):
    def __init__(self, data: bytes) -> None:
        self.data = data

    def get_content(self) -> bytes:
        return self.data


@dataclass
class FileMap:
    file: _BaseFile
    remote_path: str


class ArtifactManifest(BaseModel):
    artifact_type: str
    variant: str
    name: str | None = None
    description: str | None = None
    version: str | None = None
    producer_name: str
    producer_version: str
    producer_tags: list[str]
    payload: dict[str, Any] | BaseModel


class DiskReference:
    def __init__(self, path: str) -> None:
        self.path = path

    def get_manifest(self) -> dict[str, Any]:
        with tarfile.open(self.path, "r") as tar:
            manifest_file = tar.extractfile(tar.getmember("manifest.json"))
            if manifest_file is None:
                return {}
            return json.loads(manifest_file.read().decode("utf-8"))

    def validate(self) -> bool:
        try:
            self.get_manifest()
            return True
        except Exception:
            return False

    def list_files(self) -> list[str]:
        with tarfile.open(self.path, "r") as tar:
            return [m.name for m in tar.getmembers() if m.isfile()]

    def _append_metadata(
        self,
        idx: str | None,
        tags: list[str],
        payload: dict[str, Any],
        data: list[FileMap],
        prefix: str | None = None,
    ) -> None:
        idx = idx or uuid.uuid4().hex
        if prefix is not None:
            prefix = prefix.replace(":", PathSeparators.COLON.value).replace(
                "/", PathSeparators.SLASH.value
            )
        idx = idx if prefix is None else f"{prefix}{PathSeparators.ENDTAG.value}{idx}"

        body = {
            "id": idx,
            "tags": tags,
            "payload": payload,
        }
        body_str = json.dumps([body]).encode("utf-8")
        uid = uuid.uuid4().hex
        artifact_path_prefix = f"meta_artifacts/{idx}/"
        with tarfile.open(self.path, "a") as tar:
            info = tarfile.TarInfo(name=f"meta-{uid}.json")
            info.size = len(body_str)
            tar.addfile(info, fileobj=io.BytesIO(body_str))
            for _, item in enumerate(data):
                file_content = item.file.get_content()
                file_info = tarfile.TarInfo(
                    name=f"{artifact_path_prefix}{item.remote_path}"
                )
                file_info.size = len(file_content)
                tar.addfile(file_info, fileobj=io.BytesIO(file_content))

    def extract_file(self, name: str) -> bytes:
        with tarfile.open(self.path, "r") as tar:
            member = tar.getmember(name)
            extracted = tar.extractfile(member)
            if extracted is None:
                raise FileNotFoundError(f"Cannot read file '{name}' from archive")
            return extracted.read()
