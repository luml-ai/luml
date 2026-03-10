from fastapi import APIRouter, Query, status
from luml.experiments.backends.data_types import TraceState

from lumlflow.handlers.annotations import AnnotationsHandler
from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.handlers.models import ModelsHandler
from lumlflow.schemas.annotations import (
    Annotation,
    AnnotationSummary,
    CreateAnnotation,
    UpdateAnnotation,
)
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    EvalColumns,
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    PaginatedEvals,
    PaginatedTraces,
    TraceDetails,
    TracesSortBy,
    UpdateExperiment,
)
from lumlflow.schemas.models import Model

experiments_router = APIRouter(
    prefix="/api/experiments",
    tags=["experiments"],
)

experiments_handler = ExperimentsHandler()
models_handler = ModelsHandler()
annotations_handler = AnnotationsHandler()


@experiments_router.get("/{experiment_id}", response_model=ExperimentDetails)
def get_experiment(experiment_id: str) -> ExperimentDetails:
    return experiments_handler.get_experiment(experiment_id)


@experiments_router.patch("/{experiment_id}", response_model=Experiment)
def update_experiment(experiment_id: str, body: UpdateExperiment) -> Experiment:
    return experiments_handler.update_experiment(experiment_id, body)


@experiments_router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: str) -> None:
    experiments_handler.delete_experiment(experiment_id)


@experiments_router.get(
    "/{experiment_id}/metrics/{key}", response_model=ExperimentMetricHistory
)
def get_experiment_metric_history(
    experiment_id: str, key: str, max_points: int = 1000
) -> ExperimentMetricHistory:
    return experiments_handler.get_experiment_metric_history(
        experiment_id, key, max_points
    )


@experiments_router.get("/{experiment_id}/models", response_model=list[Model])
def list_experiment_models(experiment_id: str) -> list[Model]:
    return models_handler.list_experiment_models(experiment_id)


@experiments_router.get(
    "/{experiment_id}/traces/{trace_id}", response_model=TraceDetails
)
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails:
    return experiments_handler.get_trace(experiment_id, trace_id)


@experiments_router.get("/{experiment_id}/evals/columns", response_model=EvalColumns)
def get_experiment_eval_columns(
    experiment_id: str,
    dataset_id: str | None = None,
) -> EvalColumns:
    return experiments_handler.get_experiment_eval_columns(experiment_id, dataset_id)


@experiments_router.get(
    "/{experiment_id}/evals/average-scores", response_model=dict[str, float]
)
def get_experiment_eval_average_scores(
    experiment_id: str,
    dataset_id: str | None = None,
) -> dict[str, float]:
    return experiments_handler.get_experiment_eval_average_scores(
        experiment_id, dataset_id
    )


@experiments_router.get("/{experiment_id}/evals/dataset-ids", response_model=list[str])
def get_experiment_eval_dataset_ids(experiment_id: str) -> list[str]:
    return experiments_handler.get_experiment_eval_dataset_ids(experiment_id)


@experiments_router.get("/{experiment_id}/evals", response_model=PaginatedEvals)
def get_experiment_evals(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    dataset_id: str | None = None,
    search: str | None = None,
) -> PaginatedEvals:
    """
    search: optional substring filter on eval id

    sort_by: standard column (created_at, updated_at, dataset_id) or
    a score / inputs / outputs / refs key
    """
    return experiments_handler.get_experiment_evals(
        experiment_id,
        limit=limit,
        cursor=cursor,
        sort_by=sort_by,
        order=order,
        dataset_id=dataset_id,
        search=search,
    )


@experiments_router.get("/{experiment_id}/traces", response_model=PaginatedTraces)
def get_experiment_traces(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
    states: list[TraceState] | None = None,
) -> PaginatedTraces:
    """
    search: An optional search by trace_id

    states: An optional list of TraceState objects to filter traces by their state.
    """
    return experiments_handler.get_experiment_traces(
        experiment_id,
        limit=limit,
        cursor=cursor,
        sort_by=sort_by,
        order=order,
        search=search,
        states=states,
    )


@experiments_router.post(
    "/{experiment_id}/evals/{dataset_id}/{eval_id}/annotations",
    response_model=Annotation,
    status_code=status.HTTP_201_CREATED,
)
def create_eval_annotation(
    experiment_id: str, dataset_id: str, eval_id: str, body: CreateAnnotation
) -> Annotation:
    return annotations_handler.create_eval_annotation(
        experiment_id, dataset_id, eval_id, body
    )


@experiments_router.get(
    "/{experiment_id}/evals/{dataset_id}/{eval_id}/annotations",
    response_model=list[Annotation],
)
def get_eval_annotations(
    experiment_id: str, dataset_id: str, eval_id: str
) -> list[Annotation]:
    return annotations_handler.get_eval_annotations(
        experiment_id, dataset_id, eval_id
    )


@experiments_router.post(
    "/{experiment_id}/traces/{trace_id}/spans/{span_id}/annotations",
    response_model=Annotation,
    status_code=status.HTTP_201_CREATED,
)
def create_span_annotation(
    experiment_id: str, trace_id: str, span_id: str, body: CreateAnnotation
) -> Annotation:
    return annotations_handler.create_span_annotation(
        experiment_id, trace_id, span_id, body
    )


@experiments_router.get(
    "/{experiment_id}/traces/{trace_id}/spans/{span_id}/annotations",
    response_model=list[Annotation],
)
def get_span_annotations(
    experiment_id: str, trace_id: str, span_id: str
) -> list[Annotation]:
    return annotations_handler.get_span_annotations(
        experiment_id, trace_id, span_id
    )


@experiments_router.patch(
    "/{experiment_id}/eval-annotations/{annotation_id}",
    response_model=Annotation,
)
def update_eval_annotation(
    experiment_id: str, annotation_id: str, body: UpdateAnnotation
) -> Annotation:
    return annotations_handler.update_eval_annotation(
        experiment_id, annotation_id, body
    )


@experiments_router.patch(
    "/{experiment_id}/span-annotations/{annotation_id}",
    response_model=Annotation,
)
def update_span_annotation(
    experiment_id: str, annotation_id: str, body: UpdateAnnotation
) -> Annotation:
    return annotations_handler.update_span_annotation(
        experiment_id, annotation_id, body
    )


@experiments_router.delete(
    "/{experiment_id}/eval-annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_eval_annotation(experiment_id: str, annotation_id: str) -> None:
    annotations_handler.delete_eval_annotation(experiment_id, annotation_id)


@experiments_router.delete(
    "/{experiment_id}/span-annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_span_annotation(experiment_id: str, annotation_id: str) -> None:
    annotations_handler.delete_span_annotation(experiment_id, annotation_id)


@experiments_router.get(
    "/{experiment_id}/evals/annotations/summary",
    response_model=AnnotationSummary,
)
def get_eval_annotation_summary(
    experiment_id: str, dataset_id: str = Query(...)
) -> AnnotationSummary:
    return annotations_handler.get_eval_annotation_summary(experiment_id, dataset_id)


@experiments_router.get(
    "/{experiment_id}/traces/annotations/summary",
    response_model=AnnotationSummary,
)
def get_all_traces_annotation_summary(
    experiment_id: str,
) -> AnnotationSummary:
    return annotations_handler.get_all_traces_annotation_summary(experiment_id)


@experiments_router.get(
    "/{experiment_id}/traces/{trace_id}/annotations/summary",
    response_model=AnnotationSummary,
)
def get_trace_annotation_summary(
    experiment_id: str, trace_id: str
) -> AnnotationSummary:
    return annotations_handler.get_trace_annotation_summary(experiment_id, trace_id)
