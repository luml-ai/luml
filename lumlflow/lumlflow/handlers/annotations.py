from luml.experiments.tracker import ExperimentTracker

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.annotations import Annotation, CreateAnnotation
from lumlflow.settings import get_tracker


class AnnotationsHandler:
    def __init__(self, tracker: ExperimentTracker | None = None) -> None:
        self.tracker = tracker or get_tracker()

    def _check_experiment(self, experiment_id: str) -> None:
        if not self.tracker.get_experiment_record(experiment_id):
            raise NotFound("Experiment not found")

    def create_eval_annotation(
        self, experiment_id: str, dataset_id: str, eval_id: str, body: CreateAnnotation
    ) -> Annotation:
        self._check_experiment(experiment_id)
        try:
            record = self.tracker.log_eval_annotation(
                dataset_id=dataset_id,
                eval_id=eval_id,
                annotation_kind=body.annotation_kind,
                value_type=body.value_type,
                value=body.value,
                user=body.user,
                experiment_id=experiment_id,
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        return Annotation.model_validate(record, from_attributes=True)

    def get_eval_annotations(
        self, experiment_id: str, dataset_id: str, eval_id: str
    ) -> list[Annotation]:
        self._check_experiment(experiment_id)
        records = self.tracker.get_eval_annotations(experiment_id, dataset_id, eval_id)
        return [Annotation.model_validate(r, from_attributes=True) for r in records]

    def create_span_annotation(
        self, experiment_id: str, trace_id: str, span_id: str, body: CreateAnnotation
    ) -> Annotation:
        self._check_experiment(experiment_id)
        try:
            record = self.tracker.log_span_annotation(
                trace_id=trace_id,
                span_id=span_id,
                annotation_kind=body.annotation_kind,
                value_type=body.value_type,
                value=body.value,
                user=body.user,
                experiment_id=experiment_id,
            )
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e
        return Annotation.model_validate(record, from_attributes=True)

    def get_span_annotations(
        self, experiment_id: str, trace_id: str, span_id: str
    ) -> list[Annotation]:
        self._check_experiment(experiment_id)
        records = self.tracker.get_span_annotations(experiment_id, trace_id, span_id)
        return [Annotation.model_validate(r, from_attributes=True) for r in records]

    def delete_eval_annotation(
        self, experiment_id: str, annotation_id: str
    ) -> None:
        self._check_experiment(experiment_id)
        self.tracker.delete_annotation(experiment_id, annotation_id, "eval")

    def delete_span_annotation(
        self, experiment_id: str, annotation_id: str
    ) -> None:
        self._check_experiment(experiment_id)
        self.tracker.delete_annotation(experiment_id, annotation_id, "span")
