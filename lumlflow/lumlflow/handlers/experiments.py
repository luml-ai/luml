from math import ceil

from luml.experiments.backends.data_types import TraceState as SdkTraceState
from luml.experiments.tracker import ExperimentTracker

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.annotations import AnnotationSummary
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    Eval,
    EvalColumns,
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    ExperimentStatus,
    MetricPoint,
    PaginatedEvals,
    PaginatedTraces,
    Span,
    Trace,
    TraceDetails,
    TracesSortBy,
    TraceState,
    UpdateExperiment,
)
from lumlflow.schemas.models import Model
from lumlflow.settings import get_tracker


class ExperimentsHandler:
    def __init__(self, tracker: ExperimentTracker | None = None) -> None:
        self.tracker = tracker or get_tracker()

    def get_experiment(self, experiment_id: str) -> ExperimentDetails:
        experiment = self.tracker.get_experiment_record(experiment_id)
        if not experiment:
            raise NotFound("Experiment not found")
        try:
            models = self.tracker.get_models(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return ExperimentDetails(
            id=experiment.id,
            name=experiment.name,
            status=ExperimentStatus(experiment.status),
            group_id=experiment.group_id or "",
            created_at=experiment.created_at,
            duration=experiment.duration,
            description=experiment.description,
            tags=experiment.tags,
            static_params=experiment.static_params,
            dynamic_params=experiment.dynamic_params,
            models=[Model.model_validate(m) for m in models],
        )

    def delete_experiment(self, experiment_id: str) -> None:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")
        models = self.tracker.get_models(experiment_id)
        if models and len(models) > 0:
            raise ApplicationError(
                "Cannot delete an experiment that has linked models", status_code=409
            )
        try:
            self.tracker.delete_experiment(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

    def get_experiment_metric_history(
        self, experiment_id: str, key: str, max_points: int = 1000
    ) -> ExperimentMetricHistory:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")
        try:
            raw = self.tracker.get_experiment_metric_history(experiment_id, key)
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
        self,
        experiment_id: str,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        states: list[TraceState] | None = None,
    ) -> PaginatedTraces:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")
        try:
            sdk_states = (
                [SdkTraceState(s.value) for s in states] if states else None
            )
            result = self.tracker.get_experiment_traces(
                experiment_id,
                limit=limit,
                cursor_str=cursor,
                sort_by=sort_by,
                order=order,
                search=search,
                states=sdk_states,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        traces = []
        for t in result.items:
            trace = Trace.model_validate(t)
            summary = self.tracker.get_trace_annotation_summary(
                experiment_id, t.trace_id
            )
            trace.annotation_summary = AnnotationSummary.model_validate(
                summary, from_attributes=True
            )
            traces.append(trace)
        return PaginatedTraces(
            items=traces,
            cursor=result.cursor,
        )

    def get_trace(self, experiment_id: str, trace_id: str) -> TraceDetails:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")
        try:
            result = self.tracker.get_trace(experiment_id, trace_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        if result is None:
            raise NotFound("Trace not found")
        summary = self.tracker.get_trace_annotation_summary(
            experiment_id, trace_id
        )
        return TraceDetails(
            trace_id=result.trace_id,
            spans=[Span.model_validate(s) for s in result.spans],
            annotation_summary=AnnotationSummary.model_validate(
                summary, from_attributes=True
            ),
        )

    def get_experiment_evals(
        self,
        experiment_id: str,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        dataset_id: str | None = None,
        search: str | None = None,
    ) -> PaginatedEvals:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")
        try:
            json_sort_column = self.tracker.resolve_evals_sort_column(
                experiment_id, sort_by
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        try:
            result = self.tracker.get_experiment_evals(
                experiment_id,
                limit=limit,
                cursor_str=cursor,
                sort_by=sort_by,
                order=order,
                dataset_id=dataset_id,
                json_sort_column=json_sort_column,
                search=search,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        return PaginatedEvals(
            items=[Eval.model_validate(e) for e in result.items],
            cursor=result.cursor,
        )

    def get_experiment_eval_columns(self, experiment_id: str) -> EvalColumns:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")
        try:
            result = self.tracker.get_experiment_eval_columns(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        return EvalColumns.model_validate(result)

    def update_experiment(
        self, experiment_id: str, body: UpdateExperiment
    ) -> Experiment:
        try:
            experiment = self.tracker.update_experiment(
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
