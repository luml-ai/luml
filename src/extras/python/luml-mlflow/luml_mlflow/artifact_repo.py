"""MLflow ``ArtifactRepository`` implementation for the ``luml://`` scheme.

The repository serves the ``luml`` scheme, parses the target + run id from the
artifact URI, and writes into the same ``ExperimentTracker`` the tracking store
uses. An MLflow *artifact* that looks like a serialized **MLflow model**
(i.e. its directory contains an ``MLmodel`` descriptor) is routed through the
fnnx converter and stored as a luml **model**; any other artifact is
stored as a luml **attachment**.

Terminology note (see SPEC.md): this repository fills MLflow's
``mlflow.artifact_repository`` slot, so its inputs are MLflow "artifacts".
It produces luml **attachments** and **models** — never luml **artifacts**
(those are only ever created by the sync step uploading to an orbit).
"""

import hashlib
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from mlflow.entities.file_info import FileInfo
from mlflow.store.artifact.artifact_repo import ArtifactRepository

from luml_mlflow._tracker import ThreadSafeTracker, get_tracker
from luml_mlflow.fnnx import convert_mlflow_model_to_fnnx
from luml_mlflow.uri import LumlArtifactLocation, parse_artifact_uri

logger = logging.getLogger(__name__)

MLMODEL_FILE_NAME = "MLmodel"
FNNX_SUFFIX = ".fnnx"


class LumlArtifactRepository(ArtifactRepository):
    """Artifact repository that backs MLflow ``log_artifact(s)`` with luml.

    The owning **run** is extracted from ``self.artifact_uri`` — the tracking
    store hands each run a URI of the form
    ``luml://<org>/<orbit>/runs/<run_id>/artifacts`` (or the ``luml://local``
    equivalent), and this repository writes into the luml experiment whose id
    equals that ``run_id``.
    """

    def __init__(
        self,
        artifact_uri: str,
        tracking_uri: str | None = None,
        registry_uri: str | None = None,
    ) -> None:
        super().__init__(artifact_uri, tracking_uri, registry_uri)
        self._location: LumlArtifactLocation = parse_artifact_uri(artifact_uri)
        self._tracker: ThreadSafeTracker = get_tracker()

    @property
    def run_id(self) -> str:
        return self._location.run_id

    # --------------------------------------------------------------- writes

    def log_artifact(self, local_file: str, artifact_path: str | None = None) -> None:
        """Log a single file as a luml attachment.

        A single file is by definition not an MLflow model directory, so it is
        always stored as a luml attachment under its target name.
        """
        src = Path(local_file)
        name = _join_artifact_path(artifact_path, src.name)
        self._log_attachment_file(src, name)

    def log_artifacts(self, local_dir: str, artifact_path: str | None = None) -> None:
        """Log a directory of files.

        If ``local_dir`` (or one of its subdirectories under ``artifact_path``)
        contains an ``MLmodel`` descriptor, that directory is treated as a
        **serialized MLflow model**: it is copied to a temp location, fed
        through the fnnx converter, the resulting ``.fnnx`` is logged as a
        luml model, and the temp dir is cleaned up. All other files are stored
        as luml attachments under the run.
        """
        src_dir = Path(local_dir)
        if _is_mlflow_model_dir(src_dir):
            self._log_model_directory(src_dir, artifact_path)
            return

        for file_path in _iter_files(src_dir):
            rel = file_path.relative_to(src_dir).as_posix()
            name = _join_artifact_path(artifact_path, rel)
            self._log_attachment_file(file_path, name)

    def _log_attachment_file(self, src: Path, name: str) -> None:
        data = src.read_bytes()
        self._tracker.log_attachment(name, data, binary=True, experiment_id=self.run_id)

    def _log_model_directory(self, model_dir: Path, artifact_path: str | None) -> None:
        """Run an MLflow model dir through the fnnx converter, log as a luml model.

        Calls ``backend.log_model`` directly (rather than ``tracker.log_model``)
        because the latter is designed for raw model objects + flavor detection,
        whereas we already have a converted ``.fnnx`` file on disk.

        The luml model name is, in order of preference: the MLflow-given model
        name carried on the artifact URI (``log_model(name=...)``), an explicit
        ``artifact_path``, or — when neither names the model, as on the MLflow
        3.x ``log_model`` path that logs into a generic ``model`` directory —
        ``<experiment>-<fnnx hash>`` so it stays identifiable and unique.
        """
        with tempfile.TemporaryDirectory(prefix="luml-mlflow-fnnx-") as tmp:
            tmp_dir = Path(tmp)
            staged = tmp_dir / "model"
            shutil.copytree(model_dir, staged)
            converted = tmp_dir / f"converted{FNNX_SUFFIX}"
            convert_mlflow_model_to_fnnx(staged, converted, name=artifact_path)
            model_name = self._model_name(artifact_path, converted)
            output = tmp_dir / f"{_slugify(model_name)}{FNNX_SUFFIX}"
            converted.rename(output)
            self._tracker.backend.log_model(
                self.run_id,
                str(output),
                name=model_name,
            )

    def _model_name(self, artifact_path: str | None, fnnx_path: Path) -> str:
        """Name an MLflow model dir's resulting luml model.

        The MLflow-given name on the artifact URI wins, then an explicit
        ``artifact_path`` (e.g. ``log_model("my-model")``), else the
        ``<experiment>-<fnnx hash>`` fallback.
        """
        if self._location.model_name:
            return self._location.model_name
        if artifact_path:
            return Path(artifact_path).name
        digest = _file_sha256(fnnx_path)[:12]
        experiment = self._experiment_name()
        base = _slugify(experiment) if experiment else "model"
        return f"{base}-{digest}"

    def _experiment_name(self) -> str | None:
        record = self._tracker.get_experiment_record(self.run_id)
        return record.group_name if record is not None else None

    # ---------------------------------------------------------------- reads

    def list_artifacts(self, path: str | None = None) -> list[FileInfo]:
        """List the run's logged artifacts (attachments + models)."""
        attachments = self._tracker.list_attachments(experiment_id=self.run_id)
        models = self._tracker.get_models(experiment_id=self.run_id)

        prefix = _normalize_prefix(path)
        out: list[FileInfo] = []
        seen_dirs: set[str] = set()

        for record in attachments:
            rel = record.name
            entry = _path_relative_to(rel, prefix)
            if entry is None:
                continue
            _emit_entry(rel, entry, record.size, seen_dirs, out, prefix)

        for model in models:
            rel = _model_artifact_path(model.name, model.path)
            entry = _path_relative_to(rel, prefix)
            if entry is None:
                continue
            _emit_entry(rel, entry, model.size, seen_dirs, out, prefix)

        out.sort(key=lambda fi: fi.path)
        return out

    def _download_file(self, remote_file_path: str, local_path: str) -> None:
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        model = _find_model_for_path(
            self._tracker.get_models(experiment_id=self.run_id),
            remote_file_path,
        )
        if model is not None and model.path:
            src = self._tracker.backend.base_path / model.path
            shutil.copyfile(src, dest)
            return
        data = self._tracker.get_attachment(remote_file_path, experiment_id=self.run_id)
        dest.write_bytes(data)


# ----------------------------------------------------------- helpers


def _iter_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _is_mlflow_model_dir(path: Path) -> bool:
    return path.is_dir() and (path / MLMODEL_FILE_NAME).is_file()


def _join_artifact_path(artifact_path: str | None, name: str) -> str:
    if not artifact_path:
        return name
    return f"{artifact_path.strip('/')}/{name}"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^\w.-]+", "-", value.strip()).strip("-")
    return slug or "model"


def _model_artifact_path(model_name: str, stored_path: str | None) -> str:
    if stored_path:
        return Path(stored_path).name
    return f"{model_name}{FNNX_SUFFIX}"


def _normalize_prefix(path: str | None) -> str:
    if not path:
        return ""
    return path.strip("/")


def _path_relative_to(full: str, prefix: str) -> str | None:
    """Return the part of ``full`` that lives under ``prefix`` (POSIX).

    Returns ``None`` if ``full`` does not live under ``prefix``.
    """
    if not prefix:
        return full
    if full == prefix:
        return ""
    pref = prefix + "/"
    if full.startswith(pref):
        return full[len(pref) :]
    return None


def _emit_entry(
    full_path: str,
    relative: str,
    size: int | None,
    seen_dirs: set[str],
    out: list[FileInfo],
    prefix: str,
) -> None:
    """Append a ``FileInfo`` for the *immediate* child of the listing prefix.

    ``relative`` is the portion of ``full_path`` below the listing prefix. If
    it contains a ``/``, only the first directory component is exposed (one
    entry per top-level subfolder); otherwise the file itself is exposed.
    """
    if "/" in relative:
        first = relative.split("/", 1)[0]
        dir_path = f"{prefix}/{first}" if prefix else first
        if dir_path not in seen_dirs:
            seen_dirs.add(dir_path)
            out.append(FileInfo(path=dir_path, is_dir=True, file_size=None))
        return
    out.append(FileInfo(path=full_path, is_dir=False, file_size=size))


def _find_model_for_path(models: list[Any], remote_path: str) -> Any | None:
    target = Path(remote_path).name
    for model in models:
        if model.path and Path(model.path).name == target:
            return model
    return None


__all__ = [
    "MLMODEL_FILE_NAME",
    "LumlArtifactRepository",
]
