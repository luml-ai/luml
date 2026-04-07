from abc import ABC, abstractmethod
from typing import Any, Literal

from luml.artifacts._base import _BaseFile
from luml.experiments.backends.data_types import (
    AnnotationKind,
    AnnotationRecord,
    AnnotationSummary,
    AnnotationValueType,
    AttachmentRecord,
    EvalColumns,
    EvalRecord,
    EvalTypedColumns,
    Experiment,
    ExperimentData,
    FileNode,
    Group,
    Model,
    PaginatedResponse,
    TraceColumns,
    TraceDetails,
    TraceRecord,
    TraceState,
    TraceTypedColumns,
)


class Backend(ABC):
    @abstractmethod
    def __init__(self, config: str) -> None:
        pass

    @abstractmethod
    def initialize_experiment(
        self,
        experiment_id: str,
        group: str,
        name: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    def log_static(self, experiment_id: str, key: str, value: Any) -> None:  # noqa: ANN401
        pass

    @abstractmethod
    def log_dynamic(
        self, experiment_id: str, key: str, value: int | float, step: int | None = None
    ) -> None:
        pass

    @abstractmethod
    def log_attachment(
        self,
        experiment_id: str,
        name: str,
        data: Any,  # noqa: ANN401
        binary: bool = False,  # noqa: ANN401
    ) -> None:
        pass

    @abstractmethod
    def log_span(
        self,
        experiment_id: str,
        trace_id: str,
        span_id: str,
        name: str,
        start_time_unix_nano: int,
        end_time_unix_nano: int,
        parent_span_id: str | None = None,
        kind: int = 0,
        status_code: int = 0,
        status_message: str | None = None,
        attributes: dict[str, Any] | None = None,  # noqa: ANN401
        events: list[dict[str, Any]] | None = None,  # noqa: ANN401
        links: list[dict[str, Any]] | None = None,  # noqa: ANN401
        trace_flags: int = 0,
    ) -> None:
        pass

    @abstractmethod
    def log_eval_sample(
        self,
        experiment_id: str,
        eval_id: str,
        dataset_id: str,
        inputs: dict[str, Any],  # noqa: ANN401
        outputs: dict[str, Any] | None = None,  # noqa: ANN401
        references: dict[str, Any] | None = None,  # noqa: ANN401
        scores: dict[str, Any] | None = None,  # noqa: ANN401
        metadata: dict[str, Any] | None = None,  # noqa: ANN401
    ) -> None:
        pass

    @abstractmethod
    def link_eval_sample_to_trace(
        self,
        experiment_id: str,
        eval_dataset_id: str,
        eval_id: str,
        trace_id: str,
    ) -> None:
        pass

    @abstractmethod
    def get_experiment_data(self, experiment_id: str) -> ExperimentData:
        pass

    @abstractmethod
    def get_attachment(self, experiment_id: str, name: str) -> bytes:
        pass

    @abstractmethod
    def list_attachments(self, experiment_id: str) -> list[AttachmentRecord]:
        pass

    @abstractmethod
    def list_attachments_tree(
        self, experiment_id: str, parent_path: str | None = None
    ) -> list[FileNode]:
        pass

    @abstractmethod
    def list_experiments(self) -> list[Experiment]:
        pass

    @abstractmethod
    def get_experiment(self, experiment_id: str) -> Experiment | None:
        pass

    @abstractmethod
    def delete_experiment(self, experiment_id: str) -> None:
        pass

    @abstractmethod
    def update_experiment(
        self,
        experiment_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Experiment | None:
        pass

    @abstractmethod
    def create_group(
        self,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Group:
        pass

    @abstractmethod
    def update_group(
        self,
        group_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Group | None:
        pass

    @abstractmethod
    def delete_group(self, group_id: str) -> None:
        pass

    @abstractmethod
    def list_groups(self) -> list[Group]:
        pass

    @abstractmethod
    def get_group(self, group_id: str) -> Group | None:
        pass

    @abstractmethod
    def list_groups_pagination(
        self,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        search: str | None = None,
    ) -> PaginatedResponse[Group]:
        pass

    @abstractmethod
    def list_group_experiments_pagination(
        self,
        group_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        search: str | None = None,
        json_sort_column: str | None = None,
    ) -> PaginatedResponse[Experiment]:
        pass

    @abstractmethod
    def list_groups_experiments_pagination(
        self,
        group_ids: list[str],
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        search: str | None = None,
        json_sort_column: str | None = None,
    ) -> PaginatedResponse[Experiment]:
        pass

    @abstractmethod
    def get_group_experiments_static_params_keys(self, group_id: str) -> list[str]:
        pass

    @abstractmethod
    def get_group_experiments_dynamic_metrics_keys(self, group_id: str) -> list[str]:
        pass

    @abstractmethod
    def resolve_experiment_sort_column(self, group_id: str, sort_by: str) -> str | None:
        pass

    @abstractmethod
    def resolve_groups_experiment_sort_column(
        self, group_ids: list[str], sort_by: str
    ) -> str | None:
        pass

    @abstractmethod
    def list_experiment_models(self, experiment_id: str) -> list[Model]:
        pass

    @abstractmethod
    def end_experiment(self, experiment_id: str) -> None:
        pass

    @abstractmethod
    def fail_experiment(self, experiment_id: str) -> None:
        pass

    @abstractmethod
    def log_model(
        self,
        experiment_id: str,
        model_path: str,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[Model, str]:
        pass

    @abstractmethod
    def get_models(self, experiment_id: str) -> list[Model]:
        pass

    @abstractmethod
    def get_model(self, model_id: str) -> Model:
        pass

    @abstractmethod
    def update_model(
        self,
        model_id: str,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> Model | None:
        pass

    @abstractmethod
    def delete_model(self, model_id: str) -> None:
        pass

    @abstractmethod
    def export_experiment_db(self, experiment_id: str) -> _BaseFile:
        pass

    @abstractmethod
    def export_attachments(
        self, experiment_id: str
    ) -> tuple[_BaseFile, _BaseFile] | None:
        pass

    @abstractmethod
    def get_experiment_metric_history(
        self, experiment_id: str, key: str
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_experiment_traces(
        self,
        experiment_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "execution_time",
        order: str = "desc",
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> PaginatedResponse[TraceRecord]:
        pass

    @abstractmethod
    def get_experiment_traces_all(
        self,
        experiment_id: str,
        sort_by: str = "execution_time",
        order: str = "desc",
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> list[TraceRecord]:
        pass

    @abstractmethod
    def get_trace(self, experiment_id: str, trace_id: str) -> TraceDetails | None:
        pass

    @abstractmethod
    def get_eval(self, experiment_id: str, eval_id: str) -> EvalRecord | None:
        pass

    @abstractmethod
    def get_experiment_evals(
        self,
        experiment_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        dataset_id: str | None = None,
        json_sort_column: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> PaginatedResponse[EvalRecord]:
        pass

    @abstractmethod
    def get_experiment_evals_all(
        self,
        experiment_id: str,
        sort_by: str = "created_at",
        order: str = "desc",
        dataset_id: str | None = None,
        json_sort_column: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> list[EvalRecord]:
        pass

    @abstractmethod
    def get_experiment_eval_columns(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> EvalColumns:
        pass

    @abstractmethod
    def get_experiment_eval_typed_columns(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> EvalTypedColumns:
        pass

    @abstractmethod
    def get_experiment_trace_columns(self, experiment_id: str) -> TraceColumns:
        pass

    @abstractmethod
    def get_experiment_trace_typed_columns(
        self, experiment_id: str
    ) -> TraceTypedColumns:
        pass

    @abstractmethod
    def get_experiment_eval_dataset_ids(self, experiment_id: str) -> list[str]:
        pass

    @abstractmethod
    def resolve_evals_sort_column(self, experiment_id: str, sort_by: str) -> str | None:
        pass

    @abstractmethod
    def log_eval_annotation(
        self,
        experiment_id: str,
        dataset_id: str,
        eval_id: str,
        name: str,
        annotation_kind: AnnotationKind,
        value_type: AnnotationValueType,
        value: int | bool | str,
        user: str,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        pass

    @abstractmethod
    def get_eval_annotations(
        self, experiment_id: str, dataset_id: str, eval_id: str
    ) -> list[AnnotationRecord]:
        pass

    @abstractmethod
    def log_span_annotation(
        self,
        experiment_id: str,
        trace_id: str,
        span_id: str,
        name: str,
        annotation_kind: AnnotationKind,
        value_type: AnnotationValueType,
        value: int | bool | str,
        user: str,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        pass

    @abstractmethod
    def get_span_annotations(
        self, experiment_id: str, trace_id: str, span_id: str
    ) -> list[AnnotationRecord]:
        pass

    @abstractmethod
    def update_annotation(
        self,
        experiment_id: str,
        annotation_id: str,
        target: Literal["eval", "span"],
        value: int | bool | str | None = None,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        pass

    @abstractmethod
    def delete_annotation(
        self, experiment_id: str, annotation_id: str, target: Literal["eval", "span"]
    ) -> None:
        pass

    @abstractmethod
    def get_eval_annotation_summary(
        self, experiment_id: str, dataset_id: str
    ) -> AnnotationSummary:
        pass

    @abstractmethod
    def get_trace_annotation_summary(
        self, experiment_id: str, trace_id: str
    ) -> AnnotationSummary:
        pass

    @abstractmethod
    def get_all_traces_annotation_summary(
        self, experiment_id: str
    ) -> AnnotationSummary:
        pass

    @abstractmethod
    def get_experiment_ddl_version(self, experiment_id: str) -> int:
        pass

    @abstractmethod
    def get_evals_average_scores(
        self,
        experiment_id: str,
        dataset_id: str | None = None,
    ) -> dict[str, float]:
        pass

    @abstractmethod
    def get_traces_annotation_summaries(
        self, experiment_id: str, trace_ids: list[str]
    ) -> dict[str, AnnotationSummary]:
        pass

    @abstractmethod
    def validate_experiments_search(self, search: str | None = None) -> None:
        pass

    @abstractmethod
    def validate_evals_filter(self, search: str | None = None) -> None:
        pass

    @abstractmethod
    def validate_traces_filter(self, search: str | None = None) -> None:
        pass

    @abstractmethod
    def get_evals_annotation_summaries(
        self, experiment_id: str, eval_ids: list[str]
    ) -> dict[str, AnnotationSummary]:
        pass
