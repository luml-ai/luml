from __future__ import annotations

from luml.artifacts._base import ArtifactManifest, DiskReference


class DatasetReference(DiskReference):
    def get_manifest(self) -> ArtifactManifest:
        raw = super().get_manifest()
        return ArtifactManifest.model_validate(raw)
