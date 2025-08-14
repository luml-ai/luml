import uuid
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from dataforce.experiments.backends import Backend, BackendRegistry
from dataforce.modelref import ArtifactMap, DiskArtifact, ModelReference


class ExperimentTracker:
    def __init__(self, connection_string: str = "sqlite://./experiments") -> None:
        self.backend = self._parse_connection_string(connection_string)
        self.current_experiment_id: str | None = None

    def _parse_connection_string(self, connection_string: str) -> Backend:
        if "://" not in connection_string:
            raise ValueError("Invalid connection string format. Use 'backend://config'")

        backend_type, config = connection_string.split("://", 1)

        return BackendRegistry.get_backend(backend_type)(config)

    def start_experiment(
        self,
        experiment_id: str | None = None,
        name: str | None = None,
        group: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        if experiment_id is None:
            experiment_id = str(uuid.uuid4())

        self.backend.initialize_experiment(experiment_id, name, group, tags)
        self.current_experiment_id = experiment_id
        return experiment_id

    def end_experiment(self, experiment_id: str | None = None) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment to end.")

        self.backend.end_experiment(exp_id)

        if exp_id == self.current_experiment_id:
            self.current_experiment_id = None

    def log_static(
        self,
        key: str,
        value: Any,  # noqa: ANN401
        experiment_id: str | None = None,
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_static(exp_id, key, value)

    def log_dynamic(
        self,
        key: str,
        value: int | float,
        step: int | None = None,
        experiment_id: str | None = None,
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_dynamic(exp_id, key, value, step)

    def log_span(
        self,
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
        experiment_id: str | None = None,
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_span(
            exp_id,
            trace_id,
            span_id,
            name,
            start_time_unix_nano,
            end_time_unix_nano,
            parent_span_id,
            kind,
            status_code,
            status_message,
            attributes,
            events,
            links,
            trace_flags,
        )

    def log_eval_sample(
        self,
        eval_id: str,
        dataset_id: str,
        inputs: dict[str, Any],  # noqa: ANN401
        outputs: dict[str, Any] | None = None,  # noqa: ANN401
        references: dict[str, Any] | None = None,  # noqa: ANN401
        scores: dict[str, Any] | None = None,  # noqa: ANN401
        metadata: dict[str, Any] | None = None,  # noqa: ANN401
        experiment_id: str | None = None,
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_eval_sample(
            exp_id,
            eval_id,
            dataset_id,
            inputs,
            outputs,
            references,
            scores,
            metadata,
        )

    def link_eval_sample_to_trace(
        self,
        eval_dataset_id: str,
        eval_id: str,
        trace_id: str,
        experiment_id: str | None = None,
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.link_eval_sample_to_trace(
            exp_id, eval_dataset_id, eval_id, trace_id
        )

    def log_attachment(
        self,
        name: str,
        data: Any,  # noqa: ANN401
        binary: bool = False,
        experiment_id: str | None = None,
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        self.backend.log_attachment(exp_id, name, data)

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:  # noqa: ANN401
        return self.backend.get_experiment_data(experiment_id)

    def get_attachment(self, name: str, experiment_id: str | None = None) -> Any:  # noqa: ANN401
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        return self.backend.get_attachment(exp_id, name)

    def list_experiments(self) -> list[dict[str, Any]]:  # noqa: ANN401
        return self.backend.list_experiments()

    def delete_experiment(self, experiment_id: str) -> None:
        self.backend.delete_experiment(experiment_id)

    def create_group(self, name: str, description: str | None = None) -> None:
        self.backend.create_group(name, description)

    def list_groups(self) -> list[dict[str, Any]]:  # noqa: ANN401
        return self.backend.list_groups()

    def link_to_model(
        self, model_reference: ModelReference, experiment_id: str | None = None
    ) -> None:
        exp_id = experiment_id or self.current_experiment_id
        if exp_id is None:
            raise ValueError("No active experiment. Call start_experiment() first.")
        exp_db = self.backend.get_experiment_db(exp_id)
        attachments_result = self.backend.get_attachments(exp_id)
        if attachments_result is None:
            raise ValueError(f"No attachments found for experiment {exp_id}")
        attachments, index = attachments_result
        tag = "dataforce.studio::experiment_snapshot:v1"
        with NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
            zip_path = temp_zip.name

        if isinstance(exp_db, DiskArtifact):
            path = exp_db.path
            with zipfile.ZipFile(
                zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1
            ) as zipf:
                zipf.write(path, "exp.db")
        else:
            raise NotImplementedError(
                "Only DiskArtifact is supported for exp_db at the moment."
            )

        zipped_exp_db = DiskArtifact(zip_path)

        model_reference._append_metadata(
            idx=None,
            tags=[tag],
            payload={},
            data=[
                ArtifactMap(artifact=zipped_exp_db, remote_path="exp.db.zip"),
                ArtifactMap(artifact=attachments, remote_path="attachments.tar"),
                ArtifactMap(artifact=index, remote_path="attachments.index.json"),
            ],
            prefix=tag,
        )

        Path(zip_path).unlink(missing_ok=True)
