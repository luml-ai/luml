from __future__ import annotations

import io
import zipfile

from luml.artifacts._base import DiskReference, FileMap, MemoryFile
from luml.artifacts.dataset._manifest import DatasetArtifactManifest
from luml.card.builder import CardBuilder


class DatasetReference(DiskReference):
    def get_manifest(self) -> DatasetArtifactManifest:
        raw = super().get_manifest()
        return DatasetArtifactManifest.model_validate(raw)

    def validate(self) -> bool:
        try:
            manifest = self.get_manifest()
            return manifest.artifact_type == "dataset"
        except Exception:
            return False

    def add_dataset_card(self, html_content: str | CardBuilder) -> None:
        if not isinstance(html_content, str):
            if isinstance(html_content, CardBuilder):
                html_content = html_content.build()
            else:
                msg = "html_content must be a string or CardBuilder instance"
                raise TypeError(msg)

        tag = "dataforce.studio::dataset_card:v1"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.writestr("index.html", html_content)

        zip_buffer.seek(0)
        file = MemoryFile(zip_buffer.read())

        self._append_metadata(
            idx=None,
            tags=[tag],
            payload={},
            prefix=tag,
            data=[FileMap(file=file, remote_path="dataset_card.zip")],
        )
