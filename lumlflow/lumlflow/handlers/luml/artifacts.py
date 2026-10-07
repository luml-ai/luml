import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from luml.artifacts.experiment import save_experiment
from luml.artifacts.model import ModelReference
from luml.experiments.backends.data_types import Model as DbModel

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


@dataclass(frozen=True)
class UploadPlan:
    models: bool
    embed: bool
    experiment: bool


def upload_plan(
    upload_type: UploadType, embed_experiment: bool, models: int
) -> UploadPlan:
    """What one upload sends, given how many models the experiment has.

    `auto` embeds the experiment into every model it sends. With more than
    one model the experiment also goes on its own, and with none it is all
    that goes.
    """

    match upload_type:
        case UploadType.EXPERIMENT:
            return UploadPlan(models=False, embed=False, experiment=True)
        case UploadType.MODEL:
            return UploadPlan(models=True, embed=embed_experiment, experiment=False)
        case UploadType.AUTO:
            return UploadPlan(models=True, embed=models > 0, experiment=models != 1)


def _numbered(data: UploadArtifactForm, index: int) -> UploadArtifactForm:
    """The form for the `index`-th of several models, told apart by a suffix.

    Every model of one upload shares the name the user typed and lands in the
    same collection. Without a typed name each keeps its own.
    """

    if not data.artifact.name:
        return data
    name = f"{data.artifact.name}_{index}"
    artifact = data.artifact.model_copy(update={"name": name})
    return data.model_copy(update={"artifact": artifact})


class ArtifactHandler(BaseLumlHandler):
    def __init__(
        self,
        progress_store: ProgressStore | None = None,
    ):
        super().__init__()
        self.progress_store = progress_store or ProgressStore()

    def _upload_model(
        self,
        data: UploadArtifactForm | UploadModelForm,
        model: DbModel,
        embed: bool,
        on_progress,
    ) -> Artifact:
        if not model.path:
            raise ApplicationError(
                f"Model '{model.name}' has no file path", status_code=422
            )
        return self._upload_model_file(
            data,
            self.tracker.backend.base_path / model.path,
            name=model.name,
            embed=embed,
            on_progress=on_progress,
        )

    def _upload_model_file(
        self,
        data: UploadArtifactForm | UploadModelForm,
        model_path: Path,
        name: str,
        embed: bool,
        on_progress,
    ) -> Artifact:
        temp_path = None

        try:
            if embed:
                fd, temp_path = tempfile.mkstemp(suffix=model_path.suffix)
                os.close(fd)
                shutil.copy2(model_path, temp_path)

                self.tracker.link_to_model(
                    ModelReference(temp_path), data.experiment_id
                )
                upload_path = temp_path
            else:
                upload_path = str(model_path)

            luml = self._get_luml_client(data.organization_id, data.orbit_id)

            return luml.artifacts.upload(
                file_path=upload_path,
                name=data.artifact.name or name,
                description=data.artifact.description,
                tags=data.artifact.tags,
                collection_id=data.collection_id,
                on_progress=on_progress,
            )
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def _upload_experiment(
        self,
        data: UploadArtifactForm,
        on_progress,
    ) -> Artifact:
        experiment = self.tracker.get_experiment_record(data.experiment_id)
        if not experiment:
            raise NotFound("Experiment not found")

        fd, output_path = tempfile.mkstemp(suffix=".luml")
        os.close(fd)

        try:
            save_experiment(self.tracker, data.experiment_id, output_path)
            luml = self._get_luml_client(data.organization_id, data.orbit_id)

            return luml.artifacts.upload(
                file_path=output_path,
                name=data.artifact.name or experiment.name,
                description=data.artifact.description,
                tags=data.artifact.tags,
                collection_id=data.collection_id,
                on_progress=on_progress,
            )
        finally:
            Path(output_path).unlink(missing_ok=True)

    def _upload_all(
        self,
        data: UploadArtifactForm,
        job_id: str,
        models: Sequence[DbModel | tuple[Path, str]],
    ) -> list[Artifact]:
        plan = upload_plan(data.upload_type, data.embed_experiment, len(models))
        uploaded = models if plan.models else []
        total = len(uploaded) + int(plan.experiment)
        results = []

        for i, model in enumerate(uploaded):
            on_progress = self.progress_store.make_handler(job_id, i, total)
            form = _numbered(data, i + 1) if len(uploaded) > 1 else data
            if isinstance(model, tuple):
                path, name = model
                artifact = self._upload_model_file(
                    form, path, name=name, embed=plan.embed, on_progress=on_progress
                )
            else:
                artifact = self._upload_model(
                    form, model, embed=plan.embed, on_progress=on_progress
                )
            results.append(artifact)

        if plan.experiment:
            on_progress = self.progress_store.make_handler(job_id, len(uploaded), total)
            results.append(self._upload_experiment(data, on_progress=on_progress))

        return results

    def upload_artifact(self, data: UploadArtifactForm, job_id: str) -> None:
        self._run_upload(
            job_id, lambda: self.tracker.get_models(data.experiment_id), data
        )

    def upload_model_files(
        self, data: UploadArtifactForm, job_id: str, models: list[tuple[Path, str]]
    ) -> None:
        """Upload an experiment with the models of the flow cell that ran it.

        A cell that logs its models links them to the experiment, and those
        go just as in `upload_artifact`. One that returns them as `model`
        outputs links none, so they arrive packaged as `(path, name)` files
        instead. Which models go, and whether the experiment is embedded or
        sent beside them, follows the same `upload_plan` either way.
        """

        self._run_upload(
            job_id,
            lambda: models or self.tracker.get_models(data.experiment_id),
            data,
        )

    def _run_upload(
        self,
        job_id: str,
        models: Callable[[], Sequence[DbModel | tuple[Path, str]]],
        data: UploadArtifactForm,
    ) -> None:
        try:
            results = self._upload_all(data, job_id, models())
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
            models = self.tracker.get_models(data.experiment_id)
            model = next((m for m in models if m.id == data.model_id), None)
            if model is None:
                raise NotFound(f"Model not found: {data.model_id}")
            on_progress = self.progress_store.make_handler(job_id, 0, 1)
            artifact = self._upload_model(
                data, model, embed=data.embed_experiment, on_progress=on_progress
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
