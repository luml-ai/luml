import io
import json
import tarfile
import uuid
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pyfnx_utils.reader import Reader


class PathSeparators(str, Enum):
    COLON = "~c~"
    SLASH = "~s~"
    ENDTAG = "~~et~~"


class _BaseArtifact(ABC):
    @abstractmethod
    def get_artifact(self) -> bytes:
        pass


class DiskArtifact(_BaseArtifact):
    def __init__(self, path: str | Path) -> None:
        self.path = path

    def get_artifact(self) -> bytes:
        with open(self.path, "rb") as f:
            return f.read()


class MemoryArtifact(_BaseArtifact):
    def __init__(self, data: bytes) -> None:
        self.data = data

    def get_artifact(self) -> bytes:
        return self.data


@dataclass
class ArtifactMap:
    artifact: _BaseArtifact
    remote_path: str


class ModelReference:
    def __init__(self, path: str) -> None:
        self.path = path

    def validate(self) -> bool:
        try:
            self.read()
            return True
        except Exception as e:
            print(f"Validation failed: {e}")  # noqa: T201
            return False

    def _append_metadata(
        self,
        idx: str | None,
        tags: list[str],
        payload: dict[str, Any],  # noqa: ANN401
        data: list[ArtifactMap],
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
                file_content = item.artifact.get_artifact()
                file_info = tarfile.TarInfo(
                    name=f"{artifact_path_prefix}{item.remote_path}"
                )
                file_info.size = len(file_content)
                tar.addfile(file_info, fileobj=io.BytesIO(file_content))

    def add_model_card(self, html_content: str) -> None:
        tag = "dataforce.studio::model_card:v1"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.writestr("index.html", html_content)

        zip_buffer.seek(0)
        artifact = MemoryArtifact(zip_buffer.read())

        self._append_metadata(
            idx=None,
            tags=[tag],
            payload={},
            prefix=tag,
            data=[ArtifactMap(artifact=artifact, remote_path="model_card.zip")],
        )

    def read(self) -> Reader:
        return Reader(self.path)
