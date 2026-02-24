from math import ceil

from luml.experiments.backends.sqlite import SQLiteBackend

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.experiments import (
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    MetricPoint,
    PaginatedTraces,
    Span,
    Trace,
    UpdateExperiment,
)
from lumlflow.schemas.models import Model
from lumlflow.settings import config


class ExperimentsHandler:
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        self._db_path = db_path
        self.db = SQLiteBackend(self._db_path)

    def get_experiment(self, experiment_id: str) -> ExperimentDetails:
        experiment = self.db.get_experiment(experiment_id)
        if not experiment:
            raise NotFound("Experiment not found")
        try:
            models = self.db.list_experiment_models(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return ExperimentDetails(
            id=experiment.id,
            name=experiment.name,
            status=experiment.status,
            group_id=experiment.group_id,
            created_at=experiment.created_at,
            duration=experiment.duration,
            description=experiment.description,
            tags=experiment.tags,
            static_params=experiment.static_params,
            dynamic_params=experiment.dynamic_params,
            models=[Model.model_validate(m) for m in models],
        )

    def delete_experiment(self, experiment_id: str) -> None:
        if not self.db.get_experiment(experiment_id):
            raise NotFound("Experiment not found")
        models = self.db.list_experiment_models(experiment_id)
        if models and len(models) > 0:
            raise ApplicationError(
                "Cannot delete an experiment that has linked models", status_code=409
            )
        try:
            self.db.delete_experiment(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

    def get_experiment_metric_history(
        self, experiment_id: str, key: str, max_points: int = 1000
    ) -> ExperimentMetricHistory:
        if not self.db.get_experiment(experiment_id):
            raise NotFound("Experiment not found")
        try:
            raw = self.db.get_experiment_metric_history(experiment_id, key)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        subsampled = False

        if len(raw) > max_points:
            step = ceil(len(raw) / max_points)
            raw = raw[::step]
            subsampled = True

        return ExperimentMetricHistory(
            experiment_id=experiment_id,
            key=key,
            subsampled=subsampled,
            history=[MetricPoint(**p) for p in raw],
        )

    def get_experiment_traces(
        self, experiment_id: str, limit: int = 20, cursor: str | None = None
    ) -> PaginatedTraces:
        if not self.db.get_experiment(experiment_id):
            raise NotFound("Experiment not found")
        try:
            result = self.db.get_experiment_traces(
                experiment_id, limit=limit, cursor_str=cursor
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        traces = []
        for tr in result.items:
            pydantic_spans = [Span.model_validate(s) for s in tr.spans]
            root = next((s for s in pydantic_spans if s.parent_span_id is None), None)
            traces.append(
                Trace(trace_id=tr.trace_id, root_span=root, spans=pydantic_spans)
            )
        return PaginatedTraces(items=traces, cursor=result.cursor)

    def update_experiment(
        self, experiment_id: str, body: UpdateExperiment
    ) -> Experiment:
        try:
            experiment = self.db.update_experiment(
                experiment_id,
                name=body.name,
                description=body.description,
                tags=body.tags,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if not experiment:
            raise NotFound("Experiment not found")

        return Experiment.model_validate(experiment)
