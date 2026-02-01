from __future__ import annotations

import io
import tarfile
import tempfile
import zipfile
from typing import TYPE_CHECKING

from pydantic import BaseModel

from luml.artifacts._base import ArtifactManifest, DiskReference
from luml.artifacts._helpers import add_bytes_to_tar

if TYPE_CHECKING:
    from luml.experiments.tracker import ExperimentTracker


class ExperimentManifestPayload(BaseModel):
    local_experiment_id: str
    status: str | None = None
    group: str | None = None
    tags: list[str] = []


class ExperimentArtifactManifest(ArtifactManifest):
    payload: ExperimentManifestPayload


class ExperimentReference(DiskReference):
    def get_manifest(self) -> ExperimentArtifactManifest:
        raw = super().get_manifest()
        return ExperimentArtifactManifest.model_validate(raw)

    def validate(self) -> bool:
        try:
            manifest = self.get_manifest()
            return manifest.artifact_type == "experiment"
        except Exception:
            return False


def save_experiment(
    tracker: ExperimentTracker,
    experiment_id: str,
    output_path: str | None = None,
) -> ExperimentReference:
    from luml import __version__ as luml_sdk_version
    from luml._constants import PRODUCER_NAME

    exp_data = tracker.get_experiment(experiment_id)
    metadata = exp_data.get("metadata", {})

    manifest = ExperimentArtifactManifest(
        artifact_type="experiment",
        variant="default",
        name=metadata.get("name"),
        version="1",
        producer_name=PRODUCER_NAME,
        producer_version=luml_sdk_version,
        producer_tags=[f"{PRODUCER_NAME}::experiment_snapshot:v1"],
        payload=ExperimentManifestPayload(
            local_experiment_id=experiment_id,
            status=metadata.get("status"),
            group=metadata.get("group"),
            tags=metadata.get("tags", []),
        ),
    )

    exp_db_artifact = tracker.backend.export_experiment_db(experiment_id)
    attachments_result = tracker.backend.export_attachments(experiment_id)

    if output_path is None:
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            output_path = tmp.name

    manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")

    exp_db_bytes = exp_db_artifact.get_content()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(
        zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=1
    ) as zipf:
        zipf.writestr("exp.db", exp_db_bytes)
    zipped_db_bytes = zip_buffer.getvalue()

    with tarfile.open(output_path, "w") as tar:
        add_bytes_to_tar(tar, "manifest.json", manifest_bytes)
        add_bytes_to_tar(tar, "exp.db.zip", zipped_db_bytes)

        if attachments_result is not None:
            attachments_tar, index_file = attachments_result
            add_bytes_to_tar(tar, "attachments.tar", attachments_tar.get_content())
            add_bytes_to_tar(
                tar,
                "attachments.index.json",
                index_file.get_content(),
            )

    return ExperimentReference(output_path)
