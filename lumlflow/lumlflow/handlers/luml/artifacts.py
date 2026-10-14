import os
import shutil
import tempfile
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

from luml.artifacts.experiment import save_experiment
from luml.artifacts.model import ModelReference
from luml.experiments.backends.data_types import Model as DbModel
from luml_api import LumlClient
from luml_api._exceptions import NotFoundError
from luml_api.utils.progress import BaseProgressHandler

from lumlflow.handlers.luml.base_luml import BaseLumlHandler
from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.infra.progress_store import ProgressStore
from lumlflow.schemas.luml import (
    Artifact,
    UploadArtifactForm,
    UploadFileForm,
    UploadModelForm,
    UploadType,
)


class ArtifactHandler(BaseLumlHandler):
    def __init__(
        self,
        progress_store: ProgressStore | None = None,
        *,
        tracker_lock: AbstractContextManager | None = None,
    ):
        super().__init__()
        self.progress_store = progress_store or ProgressStore()
        self._tracker_lock = tracker_lock if tracker_lock is not None else nullcontext()

    def _upload_model(
        self,
        data: UploadArtifactForm | UploadModelForm,
        model: DbModel,
        embed: bool,
        on_progress: BaseProgressHandler,
        uploaded_experiment_id: str | None,
    ) -> Artifact:
        if not model.path:
            raise ApplicationError(
                f"Model '{model.name}' has no file path", status_code=422
            )

        with self._tracker_lock:
            model_path = str(self.tracker.backend.base_path / model.path)
        temp_path: str | None = None

        try:
            if embed:
                fd, temp_path = tempfile.mkstemp(suffix=Path(model_path).suffix)
                os.close(fd)
                shutil.copy2(model_path, temp_path)

                with self._tracker_lock:
                    self.tracker.link_to_model(
                        ModelReference(temp_path), data.experiment_id
                    )
                upload_path = temp_path
            else:
                upload_path = model_path

            luml = self._get_luml_client(data.organization_id, data.orbit_id)
            experiment_artifact_id = self._resolve_experiment_artifact_id(
                data, uploaded_experiment_id
            )
            remembered_experiment = (
                uploaded_experiment_id is None and experiment_artifact_id is not None
            )

            def upload(lineage_inputs: list[str] | None) -> Artifact:
                return luml.artifacts.upload(
                    file_path=upload_path,
                    name=data.artifact.name or model.name,
                    description=data.artifact.description,
                    tags=data.artifact.tags,
                    lineage_inputs=lineage_inputs,
                    collection_id=data.collection_id,
                    on_progress=on_progress,
                )

            try:
                artifact = upload(
                    [experiment_artifact_id]
                    if experiment_artifact_id is not None
                    else None
                )
            except NotFoundError:
                # A remembered experiment may have been deleted on the platform
                # since it was uploaded; ask the platform instead of guessing
                # from the error text.
                if not remembered_experiment or not self._artifact_is_gone(
                    luml, experiment_artifact_id
                ):
                    raise
                with self._tracker_lock:
                    self.tracker.delete_remote_artifact(
                        "experiment",
                        data.experiment_id,
                        data.orbit_id,
                    )
                artifact = upload(None)

            with self._tracker_lock:
                self.tracker.set_remote_artifact(
                    "model", model.id, data.orbit_id, artifact.id
                )
            return artifact
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    def _artifact_is_gone(luml: LumlClient, artifact_id: str | None) -> bool:
        if artifact_id is None:
            return False
        try:
            luml.artifacts.get_lineage(artifact_id, depth=1)
        except NotFoundError:
            return True
        return False

    def _resolve_experiment_artifact_id(
        self,
        data: UploadArtifactForm | UploadModelForm,
        uploaded: str | None,
    ) -> str | None:
        if uploaded is not None:
            return uploaded
        with self._tracker_lock:
            return self.tracker.get_remote_artifact(
                "experiment", data.experiment_id, data.orbit_id
            )

    def _upload_experiment(
        self,
        data: UploadArtifactForm,
        on_progress: BaseProgressHandler,
    ) -> Artifact:
        fd, output_path = tempfile.mkstemp(suffix=".luml")
        os.close(fd)

        try:
            with self._tracker_lock:
                experiment = self.tracker.get_experiment_record(data.experiment_id)
                if not experiment:
                    raise NotFound("Experiment not found")
                save_experiment(self.tracker, data.experiment_id, output_path)
            luml = self._get_luml_client(data.organization_id, data.orbit_id)

            artifact = luml.artifacts.upload(
                file_path=output_path,
                name=data.artifact.name or experiment.name,
                description=data.artifact.description,
                tags=data.artifact.tags,
                collection_id=data.collection_id,
                on_progress=on_progress,
            )
            with self._tracker_lock:
                self.tracker.set_remote_artifact(
                    "experiment", data.experiment_id, data.orbit_id, artifact.id
                )
            return artifact
        finally:
            Path(output_path).unlink(missing_ok=True)

    def _upload_all(
        self,
        data: UploadArtifactForm,
        job_id: str,
        models: list[DbModel],
        embed: bool,
        with_experiment: bool,
    ) -> list[Artifact]:
        total = len(models) + int(with_experiment)
        results: list[Artifact] = []
        uploaded_experiment_id: str | None = None

        if with_experiment:
            on_progress = self.progress_store.make_handler(job_id, 0, total)
            experiment = self._upload_experiment(data, on_progress=on_progress)
            results.append(experiment)
            uploaded_experiment_id = experiment.id

        for i, model in enumerate(models):
            on_progress = self.progress_store.make_handler(
                job_id, i + int(with_experiment), total
            )
            results.append(
                self._upload_model(
                    data,
                    model,
                    embed=embed,
                    on_progress=on_progress,
                    uploaded_experiment_id=uploaded_experiment_id,
                )
            )

        return results

    def upload_artifact(self, data: UploadArtifactForm, job_id: str) -> None:
        results: list[Artifact] = []

        try:
            match data.upload_type:
                case UploadType.EXPERIMENT:
                    results = self._upload_all(
                        data, job_id, models=[], embed=False, with_experiment=True
                    )
                case UploadType.MODEL:
                    with self._tracker_lock:
                        models = self.tracker.get_models(data.experiment_id)
                    results = self._upload_all(
                        data,
                        job_id,
                        models=models,
                        embed=data.embed_experiment,
                        with_experiment=False,
                    )
                case UploadType.AUTO:
                    with self._tracker_lock:
                        models = self.tracker.get_models(data.experiment_id)
                    results = self._upload_all(
                        data,
                        job_id,
                        models=models,
                        embed=len(models) == 1,
                        with_experiment=len(models) != 1,
                    )

        except Exception as e:
            self.progress_store.set_error(job_id, str(e))
            return

        self.progress_store.set_complete(job_id, [r.model_dump() for r in results])

    def upload_model(self, data: UploadModelForm, job_id: str) -> None:
        """Upload one specific linked model as a cloud artifact.

        Unlike `upload_artifact` with type=model (which pushes every
        linked model), this targets a single model row — the TUI's
        per-model publish. Embedding bundles the experiment into a
        temp copy of the model file, exactly like the bulk path.
        """

        try:
            with self._tracker_lock:
                models = self.tracker.get_models(data.experiment_id)
            model = next((m for m in models if m.id == data.model_id), None)
            if model is None:
                raise NotFound(f"Model not found: {data.model_id}")
            on_progress = self.progress_store.make_handler(job_id, 0, 1)
            artifact = self._upload_model(
                data,
                model,
                embed=data.embed_experiment,
                on_progress=on_progress,
                uploaded_experiment_id=None,
            )
        except Exception as e:
            self.progress_store.set_error(job_id, str(e))
            return

        self.progress_store.set_complete(job_id, [artifact.model_dump()])

    def upload_file(self, data: UploadFileForm, job_id: str) -> None:
        """Upload a user-chosen file from disk as a cloud artifact.

        The manual counterpart of `upload_artifact`: nothing is derived
        from a tracked experiment — the payload is exactly the file at
        `data.file_path`. Progress / completion / errors are reported
        through the shared progress store, same as experiment uploads.
        """

        try:
            path = Path(data.file_path).expanduser()
            if not path.is_file():
                raise NotFound(f"File not found: {path}")
            on_progress = self.progress_store.make_handler(job_id, 0, 1)
            luml = self._get_luml_client(data.organization_id, data.orbit_id)
            artifact = luml.artifacts.upload(
                file_path=str(path),
                name=data.artifact.name or path.stem,
                description=data.artifact.description,
                tags=data.artifact.tags,
                collection_id=data.collection_id,
                on_progress=on_progress,
            )
        except Exception as e:
            self.progress_store.set_error(job_id, str(e))
            return

        self.progress_store.set_complete(job_id, [artifact.model_dump()])
