from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from luml.artifacts._base import ArtifactManifest, DiskFile, DiskReference, _BaseFile
from luml.artifacts._helpers import add_bytes_to_tar

if TYPE_CHECKING:
    from luml.experiments.backends._snapshot import ExperimentSnapshot
    from luml.experiments.backends.data_types import Experiment
    from luml.experiments.tracker import ExperimentTracker

# Generation 2 publishes the database uncompressed, for readers that fetch its pages
# by HTTP range; generation 1 zipped it.
SNAPSHOT_MEMBERS = {2: "exp.db", 1: "exp.db.zip"}
_GENERATION_2_PAYLOAD = {"schema_revision", "min_reader_revision"}


class ExperimentManifestPayload(BaseModel):
    local_experiment_id: str
    status: str | None = None
    group: str | None = None
    tags: list[str] = []
    schema_revision: int | None = None
    min_reader_revision: int | None = None


class ExperimentArtifactManifest(ArtifactManifest):
    payload: ExperimentManifestPayload  # ty: ignore[incompatible-mutable-override]


class ExperimentReference(DiskReference):
    def get_manifest(
        self,
    ) -> ExperimentArtifactManifest:  # ty: ignore[incompatible-method-override]
        raw = super().get_manifest()
        return ExperimentArtifactManifest.model_validate(raw)

    def snapshot_member(self) -> str | None:
        """The member holding the experiment database, of either generation."""
        files = set(self.list_files())
        return next((m for m in SNAPSHOT_MEMBERS.values() if m in files), None)

    def validate(self) -> bool:
        try:
            manifest = self.get_manifest()
            return (
                manifest.artifact_type == "experiment"
                and self.snapshot_member() is not None
            )
        except Exception:
            return False


def snapshot_tag(producer: str, snapshot: ExperimentSnapshot) -> str:
    return f"{producer}::experiment_snapshot:v{snapshot.artifact_generation}"


def snapshot_database_file(snapshot: ExperimentSnapshot) -> tuple[str, DiskFile]:
    """The database member name for the snapshot's generation and the file to store
    as it, both streamed from disk."""
    member = SNAPSHOT_MEMBERS[snapshot.artifact_generation]
    if snapshot.artifact_generation == 2:
        return member, DiskFile(snapshot.path)
    zip_path = snapshot.work_dir / member
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
        zipf.write(snapshot.path, "exp.db")
    return member, DiskFile(zip_path)


def _manifest_json(
    experiment_id: str, metadata: Experiment, snapshot: ExperimentSnapshot
) -> bytes:
    from luml import __version__ as luml_sdk_version
    from luml._constants import PRODUCER_NAME

    manifest = ExperimentArtifactManifest(
        artifact_type="experiment",
        variant="default",
        name=metadata.name,
        version="1",
        producer_name=PRODUCER_NAME,
        producer_version=luml_sdk_version,
        producer_tags=[snapshot_tag(PRODUCER_NAME, snapshot)],
        payload=ExperimentManifestPayload(
            local_experiment_id=experiment_id,
            status=metadata.status,
            group=metadata.group_id,
            tags=metadata.tags,
            schema_revision=snapshot.schema_revision,
            min_reader_revision=snapshot.min_reader_revision,
        ),
    )
    # Generation 1 keeps the manifest that released readers know.
    exclude = (
        {"payload": _GENERATION_2_PAYLOAD}
        if snapshot.artifact_generation == 1
        else None
    )
    return manifest.model_dump_json(indent=2, exclude=exclude).encode("utf-8")


def _write_artifact(
    output_path: str,
    manifest_json: bytes,
    database: tuple[str, _BaseFile],
    attachments: tuple[_BaseFile, _BaseFile] | None,
) -> None:
    try:
        with tarfile.open(output_path, "w") as tar:
            add_bytes_to_tar(tar, "manifest.json", manifest_json)
            database[1].add_to_tar(tar, database[0])
            if attachments is not None:
                attachments_tar, index_file = attachments
                attachments_tar.add_to_tar(tar, "attachments.tar")
                index_file.add_to_tar(tar, "attachments.index.json")
    except BaseException:
        Path(output_path).unlink(missing_ok=True)
        raise


def save_experiment(
    tracker: ExperimentTracker,
    experiment_id: str,
    output_path: str | None = None,
) -> ExperimentReference:
    # The record only: the full experiment data can be large.
    experiment = tracker.get_experiment_record(experiment_id)
    if experiment is None:
        msg = f"Experiment {experiment_id} not found"
        raise ValueError(msg)

    if output_path is None:
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            output_path = tmp.name

    with tracker.backend.snapshot_experiment(experiment_id) as snapshot:
        manifest_json = _manifest_json(experiment_id, experiment, snapshot)
        database = snapshot_database_file(snapshot)
        attachments = tracker.backend.export_attachments(experiment_id)
        _write_artifact(output_path, manifest_json, database, attachments)

    return ExperimentReference(output_path)
