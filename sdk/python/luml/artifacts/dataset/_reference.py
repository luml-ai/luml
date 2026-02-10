from __future__ import annotations

from luml.artifacts._base import DiskReference
from luml.artifacts.dataset._manifest import DatasetArtifactManifest


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
