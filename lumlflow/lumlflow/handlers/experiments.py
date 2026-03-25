from math import ceil

from luml.experiments.backends.data_types import TraceState as SdkTraceState
from luml.experiments.tracker import ExperimentTracker

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.annotations import AnnotationSummary
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    Eval,
    EvalColumns,
    EvalTypedColumns,
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    ExperimentStatus,
    MetricPoint,
    PaginatedEvals,
    PaginatedTraces,
    SearchValidationResult,
    Span,
    Trace,
    TraceColumns,
    TraceDetails,
    TracesSortBy,
    TraceState,
    TraceTypedColumns,
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
            group_name=experiment.group_name,
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
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> PaginatedTraces:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            sdk_states = [SdkTraceState(s.value) for s in states] if states else None
            result = self.tracker.get_experiment_traces(
                experiment_id,
                limit=limit,
                cursor_str=cursor,
                sort_by=sort_by,
                order=order,
                search=search,
                filters=filters,
                states=sdk_states,
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        trace_ids = [t.trace_id for t in result.items]
        summaries = self.tracker.get_traces_annotation_summaries(
            experiment_id, trace_ids
        )

        traces = []
        for t in result.items:
            trace = Trace.model_validate(t)
            summary = summaries.get(t.trace_id)
            if summary is not None:
                trace.annotations = AnnotationSummary.model_validate(summary)
            traces.append(trace)

        return PaginatedTraces(
            items=traces,
            cursor=result.cursor,
        )

    def get_experiment_traces_all(
        self,
        experiment_id: str,
        sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> list[Trace]:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            sdk_states = [SdkTraceState(s.value) for s in states] if states else None
            result = self.tracker.get_experiment_traces_all(
                experiment_id,
                sort_by=sort_by,
                order=order,
                search=search,
                filters=filters,
                states=sdk_states,
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        traces = []
        for t in result:
            trace = Trace.model_validate(t)
            if t.annotations is not None:
                trace.annotations = AnnotationSummary.model_validate(t.annotations)
            traces.append(trace)

        return traces

    def get_trace(self, experiment_id: str, trace_id: str) -> TraceDetails:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            result = self.tracker.get_trace(experiment_id, trace_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if result is None:
            raise NotFound("Trace not found")

        summary = self.tracker.get_trace_annotation_summary(experiment_id, trace_id)

        return TraceDetails(
            trace_id=result.trace_id,
            spans=[Span.model_validate(s) for s in result.spans],
            annotations=AnnotationSummary.model_validate(summary),
        )

    def get_eval(self, experiment_id: str, eval_id: str) -> Eval:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            result = self.tracker.get_eval(experiment_id, eval_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if result is None:
            raise NotFound("Eval not found")

        eval_summaries = self.tracker.get_evals_annotation_summaries(
            experiment_id, [eval_id]
        )
        annotations_summary = None
        if eval_summaries:
            annotations_summary = eval_summaries.get(eval_id) or next(
                iter(eval_summaries.values()), None
            )

        eval_rec = Eval.model_validate(result)

        if annotations_summary is not None:
            eval_rec.annotations = AnnotationSummary.model_validate(annotations_summary)

        return eval_rec

    def get_experiment_evals(
        self,
        experiment_id: str,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        dataset_id: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
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
                filters=filters,
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return PaginatedEvals(
            items=[Eval.model_validate(e) for e in result.items],
            cursor=result.cursor,
        )

    def get_experiment_evals_all(
        self,
        experiment_id: str,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        dataset_id: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> list[Eval]:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            json_sort_column = self.tracker.resolve_evals_sort_column(
                experiment_id, sort_by
            )

        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e

        try:
            result = self.tracker.get_experiment_evals_all(
                experiment_id,
                sort_by=sort_by,
                order=order,
                dataset_id=dataset_id,
                json_sort_column=json_sort_column,
                search=search,
                filters=filters,
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return [Eval.model_validate(e) for e in result]

    def get_experiment_eval_dataset_ids(self, experiment_id: str) -> list[str]:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            return self.tracker.get_experiment_eval_dataset_ids(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

    def get_experiment_trace_columns(self, experiment_id: str) -> TraceColumns:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            result = self.tracker.get_experiment_trace_columns(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return TraceColumns.model_validate(result)

    def get_experiment_trace_typed_columns(
        self, experiment_id: str
    ) -> TraceTypedColumns:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            result = self.tracker.get_experiment_trace_typed_columns(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return TraceTypedColumns.model_validate(result)

    def get_experiment_eval_typed_columns(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> EvalTypedColumns:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            result = self.tracker.get_experiment_eval_typed_columns(
                experiment_id, dataset_id
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return EvalTypedColumns.model_validate(result)

    def get_experiment_eval_columns(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> EvalColumns:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            result = self.tracker.get_experiment_eval_columns(experiment_id, dataset_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return EvalColumns.model_validate(result)

    def get_experiment_eval_average_scores(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> dict[str, float]:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

        try:
            return self.tracker.get_experiment_evals_average_scores(
                experiment_id, dataset_id
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

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

    def validate_evals_filter(self, filter_str: str) -> SearchValidationResult:
        try:
            self.tracker.validate_evals_filter(filter_str)
        except Exception as e:
            return SearchValidationResult(valid=False, error=str(e))
        return SearchValidationResult()

    def validate_traces_filter(self, filter_str: str) -> SearchValidationResult:
        try:
            self.tracker.validate_traces_filter(filter_str)
        except Exception as e:
            return SearchValidationResult(valid=False, error=str(e))
        return SearchValidationResult()
