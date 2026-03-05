import os
import shutil
import tempfile
from pathlib import Path

from luml.artifacts.experiment import save_experiment
from luml.artifacts.model import ModelReference
from luml.experiments.backends.data_types import Model as DbModel
from luml.experiments.tracker import ExperimentTracker

from lumlflow.handlers.luml.base_luml import BaseLumlHandler
from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.infra.progress_store import progress_store
from lumlflow.schemas.luml import (
    Artifact,
    UploadArtifactForm,
    UploadType,
)
from lumlflow.settings import config


class ArtifactHandler(BaseLumlHandler):
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        super().__init__(db_path)
        self.tracker = ExperimentTracker(f"sqlite://{config.BACKEND_STORE_URI}")

    def _upload_model(
        self,
        data: UploadArtifactForm,
        model: DbModel,
        embed: bool,
        on_progress,
    ) -> Artifact:
        if not model.path:
            raise ApplicationError(
                f"Model '{model.name}' has no file path", status_code=422
            )

        model_path = str(self.db.base_path / model.path)
        temp_path = None

        try:
            if embed:
                fd, temp_path = tempfile.mkstemp(suffix=Path(model_path).suffix)
                os.close(fd)
                shutil.copy2(model_path, temp_path)

                self.tracker.link_to_model(
                    ModelReference(temp_path), data.experiment_id
                )
                upload_path = temp_path
            else:
                upload_path = model_path

            luml = self._get_luml_client(data.organization_id, data.orbit_id)

            return luml.artifacts.upload(
                file_path=upload_path,
                name=data.artifact.name or model.name,
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
        experiment = self.db.get_experiment(data.experiment_id)
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
        models: list[DbModel],
        embed: bool,
        with_experiment: bool,
    ) -> list[Artifact]:
        total = len(models) + int(with_experiment)
        results = []

        for i, model in enumerate(models):
            on_progress = progress_store.make_callback(job_id, i, total)
            results.append(
                self._upload_model(data, model, embed=embed, on_progress=on_progress)
            )

        if with_experiment:
            on_progress = progress_store.make_callback(job_id, len(models), total)
            results.append(self._upload_experiment(data, on_progress=on_progress))

        return results

    # на аплоадинг в люмл у нас з'являється форма з трьома вкладками
    #
    # За замовчуванням на uploading зі сторінки експерименту
    # має стояти автоматичний режим (перша вкладка):
    # 1. якщо у юзера експеримент БЕЗ моделі → в luml передається експеримент
    # 2. якщо у юзера експеримент з ОДНІЄЮ моделлю → в luml передаємо модель,
    # а експеримент ембедиться в неї
    # 3. якщо у юзера експеримент з багатьма моделями
    #   → окремо передаємо всі моделі, і окремо сам експеримент
    #
    # Друга вкладка - завантажити лише модель. форма на заповнення та сама,
    # лише у юзера питаємо окремо, чи треба ембедити експеримент до неї (чекбокс просто)
    #
    # Третя вкладка - завантажити лише експеримент
    #
    # когда ембедим експеримент у модель, надо сначала сделать копию,
    # так как оно ембедится inplace и сработает только 1 раз
    #
    # У нас в трекере есть метод, который експеримент добавляет внутрь модели.
    # Чтобы он на платформе отображался во вкладке experiment snapshots.
    # Если у нас в эксперименте ровно 1 модель,
    # то мы загружаем только 1 артефакт (модель,
    #   внутри которой есть снепшот эксперимента)
    def upload_artifact(self, data: UploadArtifactForm, job_id: str) -> list[Artifact]:
        results = []

        try:
            match data.upload_type:
                case UploadType.EXPERIMENT:
                    results = self._upload_all(
                        data, job_id, models=[], embed=False, with_experiment=True
                    )
                case UploadType.MODEL:
                    models = self.db.get_models(data.experiment_id)
                    results = self._upload_all(
                        data,
                        job_id,
                        models=models,
                        embed=data.embed_experiment,
                        with_experiment=False,
                    )
                case UploadType.AUTO:
                    models = self.db.get_models(data.experiment_id)
                    results = self._upload_all(
                        data,
                        job_id,
                        models=models,
                        embed=len(models) == 1,
                        with_experiment=len(models) != 1,
                    )

        except Exception as e:
            progress_store.set_error(job_id, str(e))
            return

        progress_store.set_complete(job_id, [r.model_dump() for r in results])
        return results
