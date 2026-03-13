from fastapi import APIRouter, Query, status

from lumlflow.handlers.annotations import AnnotationsHandler
from lumlflow.schemas.annotations import (
    Annotation,
    AnnotationSummary,
    CreateAnnotation,
    UpdateAnnotation,
)

annotations_router = APIRouter(
    prefix="/api/experiments",
    tags=["annotations"],
)

annotations_handler = AnnotationsHandler()


@annotations_router.post(
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


@annotations_router.get(
    "/{experiment_id}/evals/{dataset_id}/{eval_id}/annotations",
    response_model=list[Annotation],
)
def get_eval_annotations(
    experiment_id: str, dataset_id: str, eval_id: str
) -> list[Annotation]:
    return annotations_handler.get_eval_annotations(experiment_id, dataset_id, eval_id)


@annotations_router.patch(
    "/{experiment_id}/eval-annotations/{annotation_id}",
    response_model=Annotation,
)
def update_eval_annotation(
    experiment_id: str, annotation_id: str, body: UpdateAnnotation
) -> Annotation:
    return annotations_handler.update_eval_annotation(
        experiment_id, annotation_id, body
    )


@annotations_router.delete(
    "/{experiment_id}/eval-annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_eval_annotation(experiment_id: str, annotation_id: str) -> None:
    annotations_handler.delete_eval_annotation(experiment_id, annotation_id)


@annotations_router.get(
    "/{experiment_id}/evals/annotations/summary",
    response_model=AnnotationSummary,
)
def get_eval_annotation_summary(
    experiment_id: str, dataset_id: str = Query(...)
) -> AnnotationSummary:
    return annotations_handler.get_eval_annotation_summary(experiment_id, dataset_id)


@annotations_router.get(
    "/{experiment_id}/traces/annotations/summary",
    response_model=AnnotationSummary,
)
def get_all_traces_annotation_summary(
    experiment_id: str,
) -> AnnotationSummary:
    return annotations_handler.get_all_traces_annotation_summary(experiment_id)


@annotations_router.get(
    "/{experiment_id}/traces/{trace_id}/annotations/summary",
    response_model=AnnotationSummary,
)
def get_trace_annotation_summary(
    experiment_id: str, trace_id: str
) -> AnnotationSummary:
    return annotations_handler.get_trace_annotation_summary(experiment_id, trace_id)


@annotations_router.post(
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


@annotations_router.get(
    "/{experiment_id}/traces/{trace_id}/spans/{span_id}/annotations",
    response_model=list[Annotation],
)
def get_span_annotations(
    experiment_id: str, trace_id: str, span_id: str
) -> list[Annotation]:
    return annotations_handler.get_span_annotations(experiment_id, trace_id, span_id)


@annotations_router.patch(
    "/{experiment_id}/span-annotations/{annotation_id}",
    response_model=Annotation,
)
def update_span_annotation(
    experiment_id: str, annotation_id: str, body: UpdateAnnotation
) -> Annotation:
    return annotations_handler.update_span_annotation(
        experiment_id, annotation_id, body
    )


@annotations_router.delete(
    "/{experiment_id}/span-annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_span_annotation(experiment_id: str, annotation_id: str) -> None:
    annotations_handler.delete_span_annotation(experiment_id, annotation_id)
