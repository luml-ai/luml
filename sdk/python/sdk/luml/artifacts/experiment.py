from __future__ import annotations

import contextlib
import errno
import os
import secrets
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

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
# A file that cannot be replaced by a rename: a bind mount of the file itself (EBUSY,
# EXDEV), or one owned by another user in a sticky directory (EPERM, EACCES).
_IN_PLACE_ERRNOS = {errno.EBUSY, errno.EXDEV, errno.EPERM, errno.EACCES}
# A directory where no file may be created next to the target. Other failures, such
# as a full disk, are raised so the earlier export is not truncated.
_NO_SIBLING_ERRNOS = {errno.EACCES, errno.EPERM, errno.EROFS}


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


def _write_tar(
    file: BinaryIO,
    manifest_json: bytes,
    database: tuple[str, _BaseFile],
    attachments: tuple[_BaseFile, _BaseFile] | None,
) -> None:
    with tarfile.open(fileobj=file, mode="w") as tar:
        add_bytes_to_tar(tar, "manifest.json", manifest_json)
        database[1].add_to_tar(tar, database[0])
        if attachments is not None:
            attachments_tar, index_file = attachments
            attachments_tar.add_to_tar(tar, "attachments.tar")
            index_file.add_to_tar(tar, "attachments.index.json")


def _write_artifact(
    output_path: str,
    manifest_json: bytes,
    database: tuple[str, _BaseFile],
    attachments: tuple[_BaseFile, _BaseFile] | None,
) -> None:
    """Writes next to the target and moves the archive onto it only once complete, so
    a failed export leaves an earlier file at `output_path` as it was.

    Where no file may be created next to the target or moved onto it (a read-only
    directory, a bind-mounted file), the target is written in place instead. A
    replaced export keeps its permission bits.
    """
    target = Path(os.path.realpath(output_path))
    target_stat: os.stat_result | None = None
    # Refused as writing in place would be, so a read-only earlier export stays.
    with contextlib.suppress(FileNotFoundError):
        os.close(os.open(target, os.O_WRONLY))
        target_stat = os.stat(target)
    # A device node must stay one: a rename would put a regular file in its place.
    if target_stat is not None and not stat.S_ISREG(target_stat.st_mode):
        with open(target, "wb") as file:
            _write_tar(file, manifest_json, database, attachments)
        return
    # Named apart from the target so a long but valid target name cannot overflow it.
    partial = target.with_name(f".luml-{secrets.token_hex(8)}.partial")
    try:
        # Created like `open` would, so a new archive gets the mode the umask allows.
        # Without O_BINARY, Windows opens it in text mode and rewrites every LF.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        fd = os.open(partial, flags, 0o666)
    except OSError as error:
        if error.errno not in _NO_SIBLING_ERRNOS:
            raise
        with open(target, "wb") as file:
            _write_tar(file, manifest_json, database, attachments)
        return
    try:
        with os.fdopen(fd, "wb") as file:
            _write_tar(file, manifest_json, database, attachments)
        if target_stat is not None:
            os.chmod(partial, stat.S_IMODE(target_stat.st_mode))
        try:
            os.replace(partial, target)
        except OSError as error:
            if error.errno not in _IN_PLACE_ERRNOS:
                raise
            shutil.copyfile(partial, target)
    finally:
        partial.unlink(missing_ok=True)


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
